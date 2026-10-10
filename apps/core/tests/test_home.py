from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class HomeTests(TestCase):
    def test_home_muestra_bienvenida_y_accesos_a_secciones(self) -> None:
        usuario = User.objects.create_user(username="cliente", password="clave-segura")
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "inicio.html")
        self.assertContains(respuesta, "Bienvenido al portal de instancias")
        self.assertContains(respuesta, reverse("seccion_perfil"))
        self.assertContains(respuesta, reverse("instancias:lista"))
        self.assertContains(respuesta, reverse("seccion_suscripciones"))
        self.assertContains(respuesta, reverse("seccion_facturacion"))
        self.assertContains(respuesta, reverse("seccion_estadisticas"))
        self.assertContains(respuesta, "Próximamente")
