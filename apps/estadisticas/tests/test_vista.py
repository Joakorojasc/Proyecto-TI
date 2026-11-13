"""Pantalla de estadísticas.

Lo más delicado es el aislamiento: un usuario nunca ve números de otro cliente.
El resto fija los casos sin datos, porque todos los campos de una medición pueden
venir vacíos.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.estadisticas.models import MedicionUsoMensual
from apps.estadisticas.views import _nombre_periodo
from apps.instancias.models import EstadoInstancia, InstanciaMoodle

URL = "/estadisticas/"


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


def crear_instancia(cliente: Cliente, nombre: str) -> InstanciaMoodle:
    return InstanciaMoodle.objects.create(
        cliente=cliente,
        nombre=nombre,
        dominio=f"https://{nombre.lower().replace(' ', '-')}.demo.invalid",
        estado=EstadoInstancia.ACTIVE,
    )


def medir(
    instancia: InstanciaMoodle,
    anio: int | None = 2026,
    mes: int | None = 3,
    usuarios: int | None = 120,
    cursos: int | None = 15,
    categorias: int | None = 4,
    inscritos: int | None = 150,
    matriculas: int | None = 300,
) -> MedicionUsoMensual:
    return MedicionUsoMensual.objects.create(
        instancia=instancia,
        anio=anio,
        mes=mes,
        usuarios_activos=usuarios,
        cantidad_cursos=cursos,
        cantidad_categorias=categorias,
        usuarios_inscritos=inscritos,
        total_matriculas=matriculas,
    )


class AccesoTests(TestCase):
    def test_sin_sesion_redirige_al_login(self) -> None:
        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_la_url_conserva_su_nombre(self) -> None:
        # La usan la barra lateral, la portada y la tabla de migas.
        self.assertEqual(reverse("seccion_estadisticas"), URL)


class AislamientoTests(TestCase):
    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Propio", "76543210-3")
        medir(crear_instancia(self.cliente, "Campus Propio"))

        _, self.ajeno = crear_usuario_con_cliente("Ajeno", "76055555-K")
        self.instancia_ajena = crear_instancia(self.ajeno, "Campus Ajeno")
        medir(
            self.instancia_ajena,
            usuarios=9999,
            cursos=777,
            categorias=555,
            inscritos=3333,
            matriculas=2222,
        )
        # Un período más nuevo no debe mover el período informado del otro cliente.
        medir(self.instancia_ajena, anio=2030, mes=11, usuarios=8888, cursos=666, categorias=444)

    def assert_sin_rastros_del_ajeno(self, url: str) -> None:
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        datos_ajenos = (
            "Campus Ajeno",
            "Colegio Ajeno",
            "9999",
            "8888",
            "777",
            "666",
            "555",
            "444",
            "3333",
            "2222",
        )
        for dato in datos_ajenos:
            with self.subTest(dato=dato):
                self.assertNotContains(respuesta, dato)
        self.assertNotContains(respuesta, "2030")

    def test_no_muestra_datos_de_otro_cliente(self) -> None:
        self.client.force_login(self.usuario)

        self.assert_sin_rastros_del_ajeno(URL)
        respuesta = self.client.get(URL)
        self.assertContains(respuesta, "Campus Propio")
        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 120)
        self.assertEqual(respuesta.context["resumen"].periodo, "Marzo 2026")

    def test_no_se_puede_pedir_otro_cliente_por_la_url(self) -> None:
        self.client.force_login(self.usuario)

        self.assert_sin_rastros_del_ajeno(f"{URL}?cliente_id={self.ajeno.pk}")

    def test_un_superusuario_sin_cliente_tampoco_ve_datos_ajenos(self) -> None:
        admin = User.objects.create_superuser(username="admin", password="clave-segura")
        self.client.force_login(admin)

        self.assert_sin_rastros_del_ajeno(URL)


class EstadosDeLaPantallaTests(TestCase):
    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Uno", "76543210-3")
        self.client.force_login(self.usuario)

    def test_cuenta_sin_cliente(self) -> None:
        suelto = User.objects.create_user(username="suelto", password="clave-segura")
        self.client.force_login(suelto)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no está asociada a una institución")
        self.assertNotContains(respuesta, "instances-table")

    def test_cliente_sin_instancias(self) -> None:
        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "todavía no tienes instancias")
        self.assertNotContains(respuesta, "instances-table")

    def test_instancias_sin_mediciones(self) -> None:
        crear_instancia(self.cliente, "Campus Uno")
        crear_instancia(self.cliente, "Campus Dos")

        respuesta = self.client.get(URL)

        self.assertContains(respuesta, "Campus Uno")
        self.assertContains(respuesta, "Campus Dos")
        # Cinco métricas por cada una de las dos instancias.
        self.assertContains(respuesta, "Sin datos", count=10)
        self.assertContains(respuesta, "Todavía no hay mediciones")
        self.assertNotIn("resumen", respuesta.context)
        self.assertNotContains(respuesta, "Historial")

    def test_con_mediciones(self) -> None:
        medir(crear_instancia(self.cliente, "Campus Uno"))

        respuesta = self.client.get(URL)

        self.assertContains(respuesta, "Marzo 2026")
        self.assertContains(respuesta, "Historial")
        self.assertNotContains(respuesta, "Sin datos")
        self.assertEqual(respuesta.context["resumen"].usuarios_inscritos, 150)
        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 120)
        self.assertEqual(respuesta.context["resumen"].cantidad_cursos, 15)
        self.assertEqual(respuesta.context["resumen"].matriculados_por_curso, 20.0)
        self.assertEqual(respuesta.context["resumen"].cantidad_categorias, 4)
        self.assertEqual(respuesta.context["con_datos"], 1)
        self.assertEqual(respuesta.context["sin_datos"], 0)


class PeriodoInformadoTests(TestCase):
    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Uno", "76543210-3")
        self.client.force_login(self.usuario)
        self.uno = crear_instancia(self.cliente, "Campus Uno")
        self.dos = crear_instancia(self.cliente, "Campus Dos")

    def test_informa_el_ultimo_periodo_y_no_la_suma_de_todos(self) -> None:
        medir(self.uno, mes=2, usuarios=50)
        medir(self.uno, mes=3, usuarios=70)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].periodo, "Marzo 2026")
        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 70)

    def test_el_anio_manda_sobre_el_mes(self) -> None:
        medir(self.uno, anio=2025, mes=12, usuarios=50)
        medir(self.uno, anio=2026, mes=1, usuarios=70)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].periodo, "Enero 2026")

    def test_suma_las_instancias_del_periodo(self) -> None:
        medir(self.uno, usuarios=100, cursos=10, categorias=1)
        medir(self.dos, usuarios=20, cursos=5, categorias=2)

        resumen = self.client.get(URL).context["resumen"]

        self.assertEqual(resumen.usuarios_activos, 120)
        self.assertEqual(resumen.cantidad_cursos, 15)
        self.assertEqual(resumen.cantidad_categorias, 3)

    def test_una_instancia_atrasada_queda_sin_datos_y_fuera_de_la_suma(self) -> None:
        medir(self.uno, mes=2, usuarios=50)
        medir(self.dos, mes=3, usuarios=70)

        respuesta = self.client.get(URL)
        por_nombre = {fila.instancia.nombre: fila for fila in respuesta.context["filas"]}

        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 70)
        self.assertFalse(por_nombre["Campus Uno"].con_datos)
        self.assertIsNone(por_nombre["Campus Uno"].del_periodo.usuarios_activos)
        self.assertEqual(len(por_nombre["Campus Uno"].historial), 1)
        self.assertEqual(respuesta.context["con_datos"], 1)
        self.assertEqual(respuesta.context["sin_datos"], 1)

    def test_el_historial_va_del_mas_nuevo_al_mas_viejo(self) -> None:
        medir(self.uno, mes=1)
        medir(self.uno, mes=3)
        medir(self.uno, mes=2)

        respuesta = self.client.get(URL)
        fila = next(f for f in respuesta.context["filas"] if f.instancia == self.uno)

        self.assertEqual(
            [paso.periodo for paso in fila.historial],
            ["Marzo 2026", "Febrero 2026", "Enero 2026"],
        )


class DatosIncompletosTests(TestCase):
    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Uno", "76543210-3")
        self.client.force_login(self.usuario)
        self.uno = crear_instancia(self.cliente, "Campus Uno")

    def test_una_metrica_vacia_no_rompe_la_pantalla(self) -> None:
        medir(self.uno, usuarios=None)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["resumen"].usuarios_activos)
        self.assertEqual(respuesta.context["resumen"].cantidad_cursos, 15)
        self.assertContains(respuesta, "Sin datos")

    def test_la_suma_ignora_las_metricas_vacias(self) -> None:
        medir(self.uno, usuarios=None)
        medir(crear_instancia(self.cliente, "Campus Dos"), usuarios=20)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 20)

    def test_un_cero_se_muestra_como_cero(self) -> None:
        medir(self.uno, usuarios=0, cursos=5, categorias=0, inscritos=0, matriculas=0)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].usuarios_activos, 0)
        self.assertEqual(respuesta.context["resumen"].matriculados_por_curso, 0.0)
        self.assertNotContains(respuesta, "Sin datos")

    def test_una_medicion_sin_periodo_no_se_informa(self) -> None:
        medir(self.uno, anio=None, mes=None, usuarios=9999)

        respuesta = self.client.get(URL)

        self.assertNotIn("resumen", respuesta.context)
        self.assertNotContains(respuesta, "9999")

    def test_un_mes_invalido_no_rompe_la_pantalla(self) -> None:
        medir(self.uno, mes=13)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"].periodo, "13/2026")

    def test_el_nombre_de_un_periodo_incompleto_no_falla(self) -> None:
        self.assertEqual(_nombre_periodo(2026, None), "Sin período")
        self.assertEqual(_nombre_periodo(None, 3), "Sin período")


class MatriculadosPorCursoTests(TestCase):
    """El promedio sale de las matrículas y nunca de los usuarios activos."""

    def setUp(self) -> None:
        self.usuario, self.cliente = crear_usuario_con_cliente("Uno", "76543210-3")
        self.client.force_login(self.usuario)
        self.uno = crear_instancia(self.cliente, "Campus Uno")
        self.dos = crear_instancia(self.cliente, "Campus Dos")

    def test_se_calcula_con_las_matriculas_y_no_con_los_activos(self) -> None:
        medir(self.uno, usuarios=999, cursos=10, matriculas=250)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].matriculados_por_curso, 25.0)
        self.assertContains(respuesta, "25,0")

    def test_se_redondea_a_un_decimal(self) -> None:
        medir(self.uno, cursos=3, matriculas=10)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.context["resumen"].matriculados_por_curso, 3.3)

    def test_sin_cursos_no_divide_por_cero(self) -> None:
        medir(self.uno, cursos=0, matriculas=50)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["resumen"].matriculados_por_curso)
        self.assertContains(respuesta, "Sin datos")

    def test_una_medicion_antigua_sin_las_metricas_nuevas_dice_sin_datos(self) -> None:
        medir(self.uno, inscritos=None, matriculas=None)

        respuesta = self.client.get(URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.context["resumen"].usuarios_inscritos)
        self.assertIsNone(respuesta.context["resumen"].matriculados_por_curso)
        self.assertEqual(respuesta.context["resumen"].cantidad_cursos, 15)

    def test_el_resumen_no_es_un_promedio_de_promedios(self) -> None:
        medir(self.uno, cursos=10, matriculas=100)
        medir(self.dos, cursos=2, matriculas=300)

        resumen = self.client.get(URL).context["resumen"]

        # 400 matrículas en 12 cursos. Promediar 10 y 150 daría 80.
        self.assertEqual(resumen.matriculados_por_curso, 33.3)
        self.assertEqual(resumen.total_matriculas, 400)

    def test_una_instancia_sin_matriculas_no_baja_el_promedio(self) -> None:
        medir(self.uno, cursos=10, matriculas=100)
        medir(self.dos, cursos=90, matriculas=None)

        resumen = self.client.get(URL).context["resumen"]

        self.assertEqual(resumen.matriculados_por_curso, 10.0)
        self.assertEqual(resumen.cantidad_cursos, 100)

    def test_el_historial_trae_el_promedio_de_cada_mes(self) -> None:
        medir(self.uno, mes=2, cursos=10, matriculas=100)
        medir(self.uno, mes=3, cursos=10, matriculas=200)

        respuesta = self.client.get(URL)
        fila = next(f for f in respuesta.context["filas"] if f.instancia == self.uno)

        self.assertEqual([paso.matriculados_por_curso for paso in fila.historial], [20.0, 10.0])
