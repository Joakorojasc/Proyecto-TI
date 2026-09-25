from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.planes.models import Plan, Suscripcion

from ..models import InstanciaMoodle


class ListaInstanciasViewTests(TestCase):
    def setUp(self) -> None:
        self.cliente_a = Cliente.objects.create(razon_social="Cliente A")
        self.cliente_b = Cliente.objects.create(razon_social="Cliente B")
        self.usuario_a = User.objects.create_user(username="usuario-a", password="clave")
        UsuarioPortal.objects.create(usuario=self.usuario_a, cliente=self.cliente_a)
        self.instancia_a = InstanciaMoodle.objects.create(
            cliente=self.cliente_a,
            dominio="a.example.com",
        )
        self.instancia_b = InstanciaMoodle.objects.create(
            cliente=self.cliente_b,
            dominio="b.example.com",
        )
        self.plan_a = Plan.objects.create(nombre="Plan Cliente A")
        self.plan_b = Plan.objects.create(nombre="Plan Cliente B")
        self.url = reverse("instancias:lista")

    def crear_suscripcion(
        self,
        instancia: InstanciaMoodle,
        plan: Plan,
        estado: str = "activa",
    ) -> Suscripcion:
        return Suscripcion.objects.create(
            cliente=instancia.cliente,
            instancia=instancia,
            plan=plan,
            estado=estado,
        )

    def test_usuario_no_autenticado_redirige_al_login(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, f"/login/?next={self.url}")

    def test_usuario_autenticado_con_cliente_recibe_respuesta_200(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)

    def test_cliente_a_ve_sus_instancias(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertEqual(list(respuesta.context["instancias"]), [self.instancia_a])

    def test_cliente_a_no_ve_instancias_del_cliente_b(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        assert self.instancia_b.dominio is not None
        self.assertNotContains(respuesta, self.instancia_b.dominio)

    def test_cliente_con_dos_instancias_ve_ambas(self) -> None:
        segunda_instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente_a,
            dominio="a-2.example.com",
        )
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertEqual(
            list(respuesta.context["instancias"]),
            [self.instancia_a, segunda_instancia],
        )

    def test_instancia_con_plan_activo_muestra_su_nombre(self) -> None:
        self.crear_suscripcion(self.instancia_a, self.plan_a)
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        assert self.plan_a.nombre is not None
        self.assertContains(respuesta, self.plan_a.nombre)

    def test_suscripcion_historica_no_reemplaza_al_plan_activo(self) -> None:
        plan_historico = Plan.objects.create(nombre="Plan Histórico")
        self.crear_suscripcion(self.instancia_a, plan_historico, estado="finalizada")
        self.crear_suscripcion(self.instancia_a, self.plan_a)
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        assert self.plan_a.nombre is not None
        self.assertContains(respuesta, self.plan_a.nombre)
        assert plan_historico.nombre is not None
        self.assertNotContains(respuesta, plan_historico.nombre)

    def test_instancia_sin_plan_activo_muestra_sin_plan_activo(self) -> None:
        self.crear_suscripcion(self.instancia_a, self.plan_a, estado="finalizada")
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "Sin plan activo")

    def test_instancia_con_dos_planes_activos_muestra_inconsistencia(self) -> None:
        otro_plan = Plan.objects.create(nombre="Plan Alternativo")
        self.crear_suscripcion(self.instancia_a, self.plan_a)
        self.crear_suscripcion(self.instancia_a, otro_plan)
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "Múltiples planes activos")
        assert self.plan_a.nombre is not None
        self.assertNotContains(respuesta, self.plan_a.nombre)
        assert otro_plan.nombre is not None
        self.assertNotContains(respuesta, otro_plan.nombre)

    def test_cliente_b_y_su_plan_no_aparecen_para_cliente_a(self) -> None:
        self.crear_suscripcion(self.instancia_b, self.plan_b)
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        assert self.instancia_b.dominio is not None
        self.assertNotContains(respuesta, self.instancia_b.dominio)
        assert self.plan_b.nombre is not None
        self.assertNotContains(respuesta, self.plan_b.nombre)

    def test_multiples_instancias_muestran_su_plan_correspondiente(self) -> None:
        segunda_instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente_a,
            dominio="a-2.example.com",
        )
        segundo_plan = Plan.objects.create(nombre="Plan Cliente A 2")
        self.crear_suscripcion(self.instancia_a, self.plan_a)
        self.crear_suscripcion(segunda_instancia, segundo_plan)
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        assert self.instancia_a.dominio is not None
        self.assertContains(respuesta, self.instancia_a.dominio)
        assert self.plan_a.nombre is not None
        self.assertContains(respuesta, self.plan_a.nombre)
        assert segunda_instancia.dominio is not None
        self.assertContains(respuesta, segunda_instancia.dominio)
        assert segundo_plan.nombre is not None
        self.assertContains(respuesta, segundo_plan.nombre)

    def test_usuario_sin_usuario_portal_recibe_lista_vacia(self) -> None:
        usuario = User.objects.create_user(username="sin-perfil", password="clave")
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url)

        self.assertEqual(list(respuesta.context["instancias"]), [])

    def test_usuario_portal_sin_cliente_recibe_lista_vacia(self) -> None:
        usuario = User.objects.create_user(username="sin-cliente", password="clave")
        UsuarioPortal.objects.create(usuario=usuario)
        self.client.force_login(usuario)

        respuesta = self.client.get(self.url)

        self.assertEqual(list(respuesta.context["instancias"]), [])
