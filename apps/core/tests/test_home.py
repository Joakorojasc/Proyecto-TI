from html.parser import HTMLParser

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class HomeCardLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        clases = (atributos.get("class") or "").split()
        href = atributos.get("href")
        if tag == "a" and "home-card" in clases and href is not None:
            self.hrefs.append(href)


class HomeTests(TestCase):
    def test_home_muestra_tarjetas_con_accesos_a_secciones(self) -> None:
        usuario = User.objects.create_user(username="cliente", password="clave-segura")
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "inicio.html")

        parser = HomeCardLinkParser()
        parser.feed(respuesta.content.decode())
        self.assertCountEqual(
            parser.hrefs,
            [
                reverse("seccion_perfil"),
                reverse("instancias:lista"),
                reverse("seccion_suscripciones"),
                reverse("seccion_facturacion"),
                reverse("seccion_estadisticas"),
            ],
        )
