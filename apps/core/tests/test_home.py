from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clientes.models import Cliente, UsuarioPortal
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import EstadoInstancia, InstanciaMoodle


def crear_usuario_con_cliente(sufijo: str, rut: str) -> tuple[User, Cliente]:
    cliente = Cliente.objects.create(rut=rut, razon_social=f"Colegio {sufijo}")
    usuario = User.objects.create_user(username=f"cliente-{sufijo}", password="clave-segura")
    UsuarioPortal.objects.create(
        usuario=usuario,
        cliente=cliente,
        nombre=usuario.username,
        rol="Admin",
    )
    return usuario, cliente


class PortadaSinClienteTests(TestCase):
    def test_usuario_sin_institucion_no_ve_datos_de_nadie(self) -> None:
        usuario = User.objects.create_user(username="suelto", password="clave-segura")
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "inicio.html")
        self.assertContains(respuesta, "no está asociada a una institución")


class PortadaConClienteTests(TestCase):
    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Uno", "76543210-3")

        self.activa = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            nombre="Campus Principal",
            dominio="https://principal.demo.invalid",
            estado=EstadoInstancia.ACTIVA,
        )
        InstanciaMoodle.objects.create(
            cliente=self.cliente,
            nombre="Campus Viejo",
            dominio="https://viejo.demo.invalid",
            estado=EstadoInstancia.ARCHIVADA,
        )
        MedicionUsoMensual.objects.create(
            instancia=self.activa,
            mes=3,
            anio=2026,
            usuarios_activos=120,
            cantidad_cursos=18,
        )
        # Un período anterior, para comprobar que se informa el último y no la suma.
        MedicionUsoMensual.objects.create(
            instancia=self.activa,
            mes=2,
            anio=2026,
            usuarios_activos=90,
            cantidad_cursos=15,
        )
        self.client.force_login(self.usuario)

    def test_muestra_la_institucion_sin_el_rut(self) -> None:
        # El RUT se consulta en el perfil. En la portada solo estorbaba.
        respuesta = self.client.get(reverse("home"))

        self.assertContains(respuesta, "Colegio Uno")
        self.assertNotContains(respuesta, "76.543.210-3")

    def test_cuenta_las_instancias_por_estado(self) -> None:
        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.context["total_activas"], 1)
        self.assertEqual(respuesta.context["total_archivadas"], 1)

    def test_informa_el_uso_del_ultimo_periodo_medido(self) -> None:
        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.context["periodo_mes"], 3)
        self.assertEqual(respuesta.context["periodo_anio"], 2026)
        self.assertEqual(respuesta.context["usuarios_activos"], 120)
        self.assertEqual(respuesta.context["cursos"], 18)

    def test_lista_solo_las_instancias_activas(self) -> None:
        respuesta = self.client.get(reverse("home"))

        self.assertContains(respuesta, "Campus Principal")
        self.assertNotContains(respuesta, "Campus Viejo")

    def test_ofrece_los_accesos_a_las_secciones(self) -> None:
        respuesta = self.client.get(reverse("home"))

        for nombre in (
            "seccion_perfil",
            "seccion_suscripciones",
            "seccion_facturacion",
            "seccion_estadisticas",
        ):
            self.assertContains(respuesta, f'href="{reverse(nombre)}"')
        self.assertContains(respuesta, f'href="{reverse("instancias:lista")}"')


class PortadaAislamientoTests(TestCase):
    """La portada no puede filtrar datos de otro cliente."""

    def setUp(self) -> None:
        self.usuario_uno, self.cliente_uno = crear_usuario_con_cliente("Uno", "76543210-3")
        _, self.cliente_dos = crear_usuario_con_cliente("Dos", "77777777-7")

        InstanciaMoodle.objects.create(
            cliente=self.cliente_uno,
            nombre="Campus Propio",
            dominio="https://propio.demo.invalid",
            estado=EstadoInstancia.ACTIVA,
        )
        self.ajena = InstanciaMoodle.objects.create(
            cliente=self.cliente_dos,
            nombre="Campus Ajeno",
            dominio="https://ajeno.demo.invalid",
            estado=EstadoInstancia.ACTIVA,
        )
        MedicionUsoMensual.objects.create(
            instancia=self.ajena,
            mes=3,
            anio=2026,
            usuarios_activos=9999,
            cantidad_cursos=777,
        )

    def test_no_muestra_instancias_de_otro_cliente(self) -> None:
        self.client.force_login(self.usuario_uno)

        respuesta = self.client.get(reverse("home"))

        self.assertContains(respuesta, "Campus Propio")
        self.assertNotContains(respuesta, "Campus Ajeno")
        self.assertEqual(respuesta.context["total_activas"], 1)

    def test_no_suma_el_uso_de_otro_cliente(self) -> None:
        self.client.force_login(self.usuario_uno)

        respuesta = self.client.get(reverse("home"))

        self.assertNotContains(respuesta, "9999")
        self.assertIsNone(respuesta.context.get("usuarios_activos"))

    def test_no_muestra_la_razon_social_de_otro_cliente(self) -> None:
        self.client.force_login(self.usuario_uno)

        respuesta = self.client.get(reverse("home"))

        self.assertContains(respuesta, "Colegio Uno")
        self.assertNotContains(respuesta, "Colegio Dos")


class PortadaRequiereSesionTests(TestCase):
    def test_sin_sesion_redirige_al_login(self) -> None:
        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta.headers["Location"])


class PortadaSinInstanciasTests(TestCase):
    def test_invita_a_crear_la_primera_instancia(self) -> None:
        usuario, cliente = crear_usuario_con_cliente("Nuevo", "65123456-5")
        cliente.created_at = timezone.now()
        cliente.save()
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("home"))

        self.assertContains(respuesta, "Todavía no tienes instancias")
        self.assertEqual(respuesta.context["total_activas"], 0)
