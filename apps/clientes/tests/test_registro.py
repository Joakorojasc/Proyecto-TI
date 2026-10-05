from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.forms import RegistroClienteForm
from apps.clientes.models import Cliente, UsuarioPortal


class RegistroClienteTests(TestCase):
    def test_pagina_login_carga_bien(self) -> None:
        """La página de login debe responder y usar el template de autenticación."""
        url = reverse("login")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")
        self.assertContains(response, "Iniciar Sesión en Edocere")

    def test_home_requiere_autenticacion(self) -> None:
        """La home debe redirigir a login si el usuario no está autenticado."""
        url = reverse("home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)  # type: ignore

    def test_pagina_registro_carga_bien(self) -> None:
        """Prueba que al entrar a la URL por GET, la página cargue correctamente (código 200)"""
        url = reverse("registro_cliente")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clientes/registro.html")

    def test_formulario_acepta_datos_correctos(self) -> None:
        """Prueba que el formulario entienda cuando le pasamos datos válidos"""
        datos = {
            "rut": "76.123.456-7",
            "razon_social": "Empresa Prueba",
            "giro": "Educación",
            "direccion_facturacion": "Avenida Siempre Viva 123",
            "email_contacto": "contacto@prueba.com",
        }
        form = RegistroClienteForm(data=datos)
        self.assertTrue(form.is_valid())

    def test_registro_guarda_en_base_de_datos(self) -> None:
        """Prueba que al enviar los datos por POST, se cree el Cliente en la BD"""
        url = reverse("registro_cliente")
        datos = {
            "rut": "76.123.456-7",
            "razon_social": "Empresa Prueba",
            "giro": "Educación",
            "direccion_facturacion": "Avenida Siempre Viva 123",
            "email_contacto": "contacto@prueba.com",
        }
        response = self.client.post(url, data=datos)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)
        cliente = Cliente.objects.first()
        assert cliente is not None
        self.assertEqual(cliente.rut, "76.123.456-7")


class RegistroUsuarioTests(TestCase):
    def setUp(self) -> None:
        self.url = reverse("registro")
        self.datos = {
            "username": "admin@demo.cl",
            "password1": "ClaveSegura123!",
            "password2": "ClaveSegura123!",
            "razon_social": "Empresa Demo",
            "rut": "76.987.654-3",
        }

    def test_pagina_registro_pide_correo(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Correo electrónico")

    def test_pagina_login_pide_correo(self) -> None:
        respuesta = self.client.get(reverse("login"))

        self.assertContains(respuesta, "Correo electrónico")

    def test_registro_crea_usuario_cliente_y_perfil_relacionados(self) -> None:
        respuesta = self.client.post(self.url, data=self.datos)

        self.assertEqual(respuesta.status_code, 302)
        auth_user = User.objects.get(username="admin@demo.cl")
        cliente = Cliente.objects.get(rut="76.987.654-3")
        usuario_portal = UsuarioPortal.objects.get(usuario=auth_user)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(UsuarioPortal.objects.count(), 1)
        self.assertEqual(usuario_portal.usuario, auth_user)
        self.assertEqual(auth_user.usuarioportal, usuario_portal)
        self.assertEqual(usuario_portal.cliente, cliente)

    def test_correo_se_guarda_como_usuario_y_como_contacto(self) -> None:
        self.client.post(self.url, data=self.datos)

        self.assertEqual(User.objects.get().email, "admin@demo.cl")
        self.assertEqual(Cliente.objects.get().email_contacto, "admin@demo.cl")
        self.assertEqual(UsuarioPortal.objects.get().email, "admin@demo.cl")

    def test_registro_inicia_sesion_y_lleva_a_mis_instancias(self) -> None:
        respuesta = self.client.post(self.url, data=self.datos)

        self.assertRedirects(respuesta, reverse("instancias:lista"))
        auth_user = User.objects.get()
        self.assertEqual(int(self.client.session["_auth_user_id"]), auth_user.pk)

    def test_mis_instancias_vacio_ofrece_crear_instancia(self) -> None:
        self.client.post(self.url, data=self.datos)
        cliente = Cliente.objects.get()

        respuesta = self.client.get(reverse("instancias:lista"))

        self.assertContains(respuesta, "Aún no tienes instancias Moodle asociadas.")
        self.assertContains(respuesta, reverse("seleccionar_plan", args=[cliente.pk]))

    def test_correo_se_normaliza_a_minusculas(self) -> None:
        self.client.post(self.url, data={**self.datos, "username": "Admin@Demo.CL"})

        self.assertEqual(User.objects.get().username, "admin@demo.cl")

    def test_rechaza_correo_invalido(self) -> None:
        respuesta = self.client.post(self.url, data={**self.datos, "username": "no-es-un-correo"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["user_form"].errors["username"])
        self.assertFalse(User.objects.exists())
        self.assertFalse(Cliente.objects.exists())

    def test_rechaza_correo_repetido_sin_importar_mayusculas(self) -> None:
        User.objects.create_user(username="admin@demo.cl", password="clave")

        respuesta = self.client.post(self.url, data={**self.datos, "username": "ADMIN@demo.cl"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["user_form"].errors["username"])
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(Cliente.objects.exists())

    def test_se_puede_iniciar_sesion_con_el_correo(self) -> None:
        self.client.post(self.url, data=self.datos)
        self.client.logout()

        self.assertTrue(self.client.login(username="admin@demo.cl", password="ClaveSegura123!"))
