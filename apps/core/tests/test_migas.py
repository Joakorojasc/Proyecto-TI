"""Migas de pan.

El mecanismo vive en el bloque `migas` de base.html y cada pantalla declara su
propia ruta. Estas pruebas fijan que la ruta exista, que los antecesores sean
enlaces y que la página actual no lo sea.
"""

import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.instancias.models import EstadoInstancia, InstanciaMoodle

MIGAS = re.compile(r'<nav class="migas".*?</nav>', re.S)
ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S)


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


class MigasTests(TestCase):
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
            estado=EstadoInstancia.ACTIVA,
        )
        self.client.force_login(self.usuario)

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
            estado=EstadoInstancia.ACTIVA,
        )

        respuesta = self.client.get(reverse("instancias:detalle", args=[sin_nombre.pk]))

        self.assertEqual(pagina_actual(respuesta.content.decode()), "dos.demo.invalid")
