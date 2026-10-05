from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal

from ..models import InstanciaMoodle


class EditarInstanciaViewTests(TestCase):
    def setUp(self) -> None:
        self.cliente_a = Cliente.objects.create(razon_social="Cliente A")
        self.cliente_b = Cliente.objects.create(razon_social="Cliente B")
        self.usuario_a = User.objects.create_user(username="usuario-a", password="clave")
        UsuarioPortal.objects.create(usuario=self.usuario_a, cliente=self.cliente_a)
        self.instancia_a = InstanciaMoodle.objects.create(
            cliente=self.cliente_a,
            nombre="Campus A",
            dominio="https://a.edocere.com",
            logo_url="https://a.cl/logo.png",
            version="5.2",
            estado="activa",
        )
        self.instancia_b = InstanciaMoodle.objects.create(
            cliente=self.cliente_b,
            nombre="Campus B",
            dominio="https://b.edocere.com",
        )
        self.url = reverse("instancias:editar", args=[self.instancia_a.pk])

    def test_usuario_no_autenticado_redirige_al_login(self) -> None:
        respuesta = self.client.get(self.url)

        self.assertRedirects(respuesta, f"/login/?next={self.url}")

    def test_muestra_formulario_con_datos_actuales_y_dominio_bloqueado(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Campus A")
        self.assertContains(respuesta, "https://a.cl/logo.png")
        self.assertContains(respuesta, "a.edocere.com")
        self.assertContains(respuesta, "El dominio no se puede modificar por ahora.")

    def test_guarda_nombre_y_logo_y_vuelve_al_detalle(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.post(
            self.url,
            {"nombre": "Campus Nuevo", "logo_url": "https://a.cl/nuevo.png"},
        )

        self.assertRedirects(respuesta, reverse("instancias:detalle", args=[self.instancia_a.pk]))
        self.instancia_a.refresh_from_db()
        self.assertEqual(self.instancia_a.nombre, "Campus Nuevo")
        self.assertEqual(self.instancia_a.logo_url, "https://a.cl/nuevo.png")

    def test_logo_es_opcional(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.post(self.url, {"nombre": "Campus A", "logo_url": ""})

        self.assertEqual(respuesta.status_code, 302)
        self.instancia_a.refresh_from_db()
        self.assertFalse(self.instancia_a.logo_url)

    def test_no_modifica_dominio_version_ni_estado(self) -> None:
        self.client.force_login(self.usuario_a)

        self.client.post(
            self.url,
            {
                "nombre": "Campus A",
                "logo_url": "",
                "dominio": "https://otro.com",
                "version": "9.9",
                "estado": "archivada",
            },
        )

        self.instancia_a.refresh_from_db()
        self.assertEqual(self.instancia_a.dominio, "https://a.edocere.com")
        self.assertEqual(self.instancia_a.version, "5.2")
        self.assertEqual(self.instancia_a.estado, "activa")

    def test_nombre_es_obligatorio(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.post(self.url, {"nombre": "", "logo_url": ""})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors["nombre"])
        self.instancia_a.refresh_from_db()
        self.assertEqual(self.instancia_a.nombre, "Campus A")

    def test_rechaza_logo_invalido(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.post(self.url, {"nombre": "Campus A", "logo_url": "no es url"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors["logo_url"])
        self.instancia_a.refresh_from_db()
        self.assertEqual(self.instancia_a.logo_url, "https://a.cl/logo.png")

    def test_no_puede_editar_instancia_de_otro_cliente(self) -> None:
        self.client.force_login(self.usuario_a)
        url_ajena = reverse("instancias:editar", args=[self.instancia_b.pk])

        respuesta_get = self.client.get(url_ajena)
        respuesta_post = self.client.post(url_ajena, {"nombre": "Hackeada", "logo_url": ""})

        self.assertEqual(respuesta_get.status_code, 404)
        self.assertEqual(respuesta_post.status_code, 404)
        self.instancia_b.refresh_from_db()
        self.assertEqual(self.instancia_b.nombre, "Campus B")

    def test_detalle_muestra_boton_editar_logo_y_direccion(self) -> None:
        self.client.force_login(self.usuario_a)

        respuesta = self.client.get(reverse("instancias:detalle", args=[self.instancia_a.pk]))

        self.assertContains(respuesta, self.url)
        self.assertContains(respuesta, "https://a.cl/logo.png")
        self.assertContains(respuesta, "Dirección web: a.edocere.com")
