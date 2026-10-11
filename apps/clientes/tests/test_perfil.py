from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal


class PerfilInstitucionTests(TestCase):
    def setUp(self) -> None:
        self.usuario = User.objects.create_user(
            username="admin@demo.cl",
            email="admin@demo.cl",
            password="ClaveSegura123!",
        )
        self.cliente = Cliente.objects.create(
            rut="76.123.456-7",
            razon_social="Institución Original",
            giro="Educación",
            direccion_facturacion="Calle Original 123",
            email_contacto="contacto@original.cl",
        )
        UsuarioPortal.objects.create(usuario=self.usuario, cliente=self.cliente)
        self.client.force_login(self.usuario)
        self.url = reverse("seccion_perfil")

    def test_perfil_muestra_datos_editables_y_rut_no_editable(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "perfil.html")
        self.assertContains(respuesta, "Perfil de Institución")
        self.assertContains(respuesta, "Institución Original")
        self.assertContains(respuesta, "Calle Original 123")
        self.assertContains(respuesta, "76.123.456-7")
        self.assertNotContains(respuesta, 'name="rut"')
        self.assertContains(respuesta, 'name="confirmacion_contrasena"')

    def test_actualiza_datos_solo_con_contrasena_correcta(self) -> None:
        respuesta = self.client.post(
            self.url,
            {
                "razon_social": "Institución Actualizada",
                "giro": "Tecnología",
                "direccion_facturacion": "Calle Nueva 456",
                "email_contacto": "contacto@nueva.cl",
                "confirmacion_contrasena": "ClaveSegura123!",
            },
            follow=True,
        )

        self.assertEqual(respuesta.redirect_chain, [(self.url, 302)])
        self.assertContains(
            respuesta,
            "Los cambios del perfil se guardaron correctamente.",
        )
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.razon_social, "Institución Actualizada")
        self.assertEqual(self.cliente.giro, "Tecnología")
        self.assertEqual(self.cliente.direccion_facturacion, "Calle Nueva 456")
        self.assertEqual(self.cliente.email_contacto, "contacto@nueva.cl")

    def test_contrasena_incorrecta_no_guarda_cambios(self) -> None:
        respuesta = self.client.post(
            self.url,
            {
                "razon_social": "No debe guardarse",
                "giro": "Tecnología",
                "direccion_facturacion": "Calle Nueva 456",
                "email_contacto": "contacto@nueva.cl",
                "confirmacion_contrasena": "incorrecta",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La contraseña ingresada no es correcta.")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.razon_social, "Institución Original")

    def test_contrasena_es_obligatoria_para_guardar(self) -> None:
        respuesta = self.client.post(
            self.url,
            {
                "razon_social": "No debe guardarse",
                "giro": "Tecnología",
                "direccion_facturacion": "Calle Nueva 456",
                "email_contacto": "contacto@nueva.cl",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ingresa tu contraseña para confirmar los cambios.",
        )
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.razon_social, "Institución Original")

    def test_rechaza_correo_de_contacto_invalido(self) -> None:
        respuesta = self.client.post(
            self.url,
            {
                "razon_social": "Institución Original",
                "giro": "Educación",
                "direccion_facturacion": "Calle Original 123",
                "email_contacto": "correo-invalido",
                "confirmacion_contrasena": "ClaveSegura123!",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ingresa un correo electrónico válido.")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email_contacto, "contacto@original.cl")

    def test_requiere_usuario_autenticado(self) -> None:
        self.client.logout()

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta.headers.get("Location", ""))
