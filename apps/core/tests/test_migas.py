"""Migas de pan.

La ruta se deduce de la URL con la tabla de apps/core/migas.py. Estas pruebas
fijan dos cosas: que cada pantalla muestre la ruta que le corresponde, y que
ninguna URL con nombre quede sin decidir. Lo segundo es lo que evita que una
pantalla nueva aparezca sin migas sin que nadie se entere.
"""

import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import get_resolver, reverse
from django.urls.resolvers import URLResolver

from apps.clientes import terminos
from apps.clientes.models import Cliente, UsuarioPortal
from apps.core.migas import RUTAS, SIN_MIGAS
from apps.instancias.models import EstadoInstancia, InstanciaMoodle
from apps.planes.models import Plan, Suscripcion

MIGAS = re.compile(r'<nav class="migas".*?</nav>', re.S)
ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S)

# El admin es de Django y trae su propia navegación. No lo cubre esta tabla.
NAMESPACES_AJENOS = frozenset({"admin"})


def ruta_de(html: str) -> list[str]:
    """Los textos de la miga, en orden."""
    bloque = MIGAS.search(html)
    if bloque is None:
        return []
    return [re.sub(r"<[^>]+>", "", item).strip() for item in ITEM.findall(bloque.group())]


def pagina_actual(html: str) -> str | None:
    """El paso marcado como página actual, que va sin enlace."""
    bloque = MIGAS.search(html)
    if bloque is None:
        return None
    marcado = re.search(r'<li aria-current="page">(.*?)</li>', bloque.group(), re.S)
    return re.sub(r"<[^>]+>", "", marcado.group(1)).strip() if marcado else None


def urls_del_portal() -> dict[str, frozenset[str]]:
    """Cada URL con nombre del portal, con los parámetros de su patrón.

    Usa groupindex y no converters porque funciona igual con path() y con
    re_path().
    """
    encontradas: dict[str, frozenset[str]] = {}

    def recorrer(resolver: URLResolver, heredados: frozenset[str], namespace: str | None) -> None:
        for patron in resolver.url_patterns:
            propios = heredados | frozenset(patron.pattern.regex.groupindex)
            if isinstance(patron, URLResolver):
                espacio = patron.namespace or namespace
                if espacio in NAMESPACES_AJENOS:
                    continue
                recorrer(patron, propios, espacio)
            elif patron.name:
                nombre = f"{namespace}:{patron.name}" if namespace else patron.name
                encontradas[nombre] = propios

    recorrer(get_resolver(), frozenset(), None)
    return encontradas


class TablaDeMigasTests(TestCase):
    """La tabla se revisa sola, sin pedir ninguna pantalla."""

    def test_toda_url_con_nombre_esta_decidida(self) -> None:
        sin_decidir = sorted(set(urls_del_portal()) - set(RUTAS) - SIN_MIGAS)

        self.assertEqual(
            sin_decidir,
            [],
            "Estas URLs no tienen ruta de navegación. Agregá cada una a RUTAS en "
            "apps/core/migas.py, o a SIN_MIGAS si la pantalla no debe llevar "
            f"migas: {sin_decidir}",
        )

    def test_la_tabla_no_nombra_urls_que_no_existen(self) -> None:
        reales = set(urls_del_portal())

        self.assertEqual(sorted(set(RUTAS) - reales), [])
        self.assertEqual(sorted(SIN_MIGAS - reales), [])

    def test_cada_padre_esta_en_la_tabla(self) -> None:
        for nombre, paso in RUTAS.items():
            if paso.padre is not None:
                with self.subTest(url=nombre):
                    self.assertIn(paso.padre, RUTAS)

    def test_ningun_paso_cuelga_de_si_mismo(self) -> None:
        for nombre in RUTAS:
            vistos: set[str] = set()
            actual: str | None = nombre
            while actual is not None:
                with self.subTest(url=nombre):
                    self.assertNotIn(actual, vistos)
                vistos.add(actual)
                actual = RUTAS[actual].padre

    def test_los_argumentos_declarados_son_los_del_patron(self) -> None:
        reales = urls_del_portal()
        for nombre, paso in RUTAS.items():
            with self.subTest(url=nombre):
                self.assertEqual(set(paso.argumentos), set(reales[nombre]))

    def test_el_padre_no_pide_argumentos_que_el_hijo_no_tenga(self) -> None:
        # Si los pidiera, el enlace al antecesor no se podría construir.
        for nombre, paso in RUTAS.items():
            if paso.padre is not None:
                with self.subTest(url=nombre):
                    self.assertLessEqual(set(RUTAS[paso.padre].argumentos), set(paso.argumentos))


class ClienteConSesionTestCase(TestCase):
    """Un cliente con instancia, plan y suscripción, con su sesión iniciada."""

    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(rut="76543210-3", razon_social="Colegio Demo")
        self.usuario = User.objects.create_user(username="cliente", password="clave-segura")
        UsuarioPortal.objects.create(
            usuario=self.usuario,
            cliente=self.cliente,
            nombre=self.usuario.username,
            rol="Admin",
        )
        self.instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            nombre="Campus Uno",
            dominio="https://uno.demo.invalid",
            estado=EstadoInstancia.ACTIVE,
        )
        self.plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="mensual")
        self.suscripcion = Suscripcion.objects.create(
            cliente=self.cliente, plan=self.plan, estado="pendiente"
        )
        self.client.force_login(self.usuario)
        terminos.registrar_aceptacion(self.cliente, self.usuario, terminos.VERSION_TERMINOS)


class MigasTests(ClienteConSesionTestCase):
    def test_la_portada_no_lleva_migas(self) -> None:
        # Es la raíz: no hay nada por encima a lo que volver.
        respuesta = self.client.get(reverse("home"))

        self.assertEqual(ruta_de(respuesta.content.decode()), [])

    def test_las_secciones_cuelgan_de_inicio(self) -> None:
        esperado = {
            "seccion_perfil": "Perfil de Institución",
            "seccion_suscripciones": "Suscripciones y Planes",
            "seccion_facturacion": "Facturación y Pagos",
            "seccion_estadisticas": "Estadísticas",
        }
        for nombre, titulo in esperado.items():
            with self.subTest(seccion=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(ruta_de(respuesta.content.decode()), ["Inicio", titulo])

    def test_el_detalle_cuelga_del_listado(self) -> None:
        respuesta = self.client.get(reverse("instancias:detalle", args=[self.instancia.pk]))

        self.assertEqual(
            ruta_de(respuesta.content.decode()), ["Inicio", "Mis Instancias", "Campus Uno"]
        )

    def test_editar_cuelga_del_detalle(self) -> None:
        respuesta = self.client.get(reverse("instancias:editar", args=[self.instancia.pk]))

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Mis Instancias", "Campus Uno", "Editar"],
        )

    def test_la_pagina_actual_no_es_un_enlace(self) -> None:
        respuesta = self.client.get(reverse("instancias:detalle", args=[self.instancia.pk]))

        self.assertEqual(pagina_actual(respuesta.content.decode()), "Campus Uno")
        self.assertNotContains(
            respuesta,
            f'<li aria-current="page"><a href="{reverse("instancias:detalle", args=[self.instancia.pk])}"',
        )

    def test_los_antecesores_si_son_enlaces(self) -> None:
        respuesta = self.client.get(reverse("instancias:editar", args=[self.instancia.pk]))

        self.assertContains(respuesta, f'href="{reverse("home")}">Inicio</a>')
        self.assertContains(respuesta, f'href="{reverse("instancias:lista")}">Mis Instancias</a>')
        self.assertContains(
            respuesta,
            f'href="{reverse("instancias:detalle", args=[self.instancia.pk])}">Campus Uno</a>',
        )

    def test_una_instancia_sin_nombre_usa_su_dominio(self) -> None:
        sin_nombre = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            dominio="https://dos.demo.invalid",
            estado=EstadoInstancia.ACTIVE,
        )

        respuesta = self.client.get(reverse("instancias:detalle", args=[sin_nombre.pk]))

        self.assertEqual(pagina_actual(respuesta.content.decode()), "dos.demo.invalid")


class PantallasQueNoTenianMigasTests(ClienteConSesionTestCase):
    """Las seis pantallas que quedaron sin ruta y que ahora la deducen."""

    def test_seleccionar_plan_cuelga_de_mis_instancias(self) -> None:
        url = reverse("planes:seleccionar_plan", kwargs={"cliente_id": self.cliente.pk})

        respuesta = self.client.get(url)

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Mis Instancias", "Seleccionar plan"],
        )

    def test_crear_instancia_cuelga_de_seleccionar_plan(self) -> None:
        url = reverse(
            "instancias:crear",
            kwargs={"cliente_id": self.cliente.pk, "plan_id": self.plan.pk},
        )

        respuesta = self.client.get(url)

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Mis Instancias", "Seleccionar plan", "Configurar instancia"],
        )

    def test_crear_instancia_enlaza_al_paso_anterior_con_su_cliente(self) -> None:
        # El enlace del antecesor se arma con el cliente_id de la URL actual.
        url = reverse(
            "instancias:crear",
            kwargs={"cliente_id": self.cliente.pk, "plan_id": self.plan.pk},
        )
        anterior = reverse("planes:seleccionar_plan", kwargs={"cliente_id": self.cliente.pk})

        respuesta = self.client.get(url)

        self.assertContains(respuesta, f'href="{anterior}">Seleccionar plan</a>')

    def test_contacto_cuelga_de_suscripciones(self) -> None:
        respuesta = self.client.get(reverse("planes:contacto_plan_personalizado"))

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Suscripciones y Planes", "Plan personalizado"],
        )

    def test_checkout_cuelga_de_facturacion(self) -> None:
        url = reverse("pagos:checkout", kwargs={"suscripcion_id": self.suscripcion.pk})

        respuesta = self.client.get(url)

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Facturación y Pagos", "Pago de suscripción"],
        )

    def test_terminos_cuelga_del_perfil(self) -> None:
        respuesta = self.client.get(reverse("aceptar_terminos"))

        self.assertEqual(
            ruta_de(respuesta.content.decode()),
            ["Inicio", "Perfil de Institución", "Términos y condiciones"],
        )


class CuentaSinInstitucionTests(TestCase):
    """La pantalla de cuenta sin institución hereda la ruta de la URL que la sirve."""

    def test_el_perfil_de_una_cuenta_suelta_igual_muestra_su_ruta(self) -> None:
        usuario = User.objects.create_user(username="suelto", password="clave-segura")
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("seccion_perfil"))

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(ruta_de(respuesta.content.decode()), ["Inicio", "Perfil de Institución"])
