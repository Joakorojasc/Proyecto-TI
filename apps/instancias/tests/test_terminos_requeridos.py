from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes import terminos
from apps.clientes.models import Cliente, UsuarioPortal
from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Plan


class TerminosRequeridosParaCrearInstanciaTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(rut="76543210-3", razon_social="Empresa Test")
        self.usuario = User.objects.create_user(
            username="admin@test.cl", email="admin@test.cl", password="Clave-segura-123!"
        )
        UsuarioPortal.objects.create(
            usuario=self.usuario, cliente=self.cliente, email="admin@test.cl", rol="Admin"
        )
        self.plan = Plan.objects.create(
            nombre="Plan mensual", tipo_plan="mensual", precio_por_usuario=Decimal("1.50")
        )
        self.url = reverse("instancias:crear", args=[self.cliente.pk, self.plan.pk])

    def test_sin_aceptacion_redirige_a_terminos(self) -> None:
        self.client.force_login(self.usuario)
        respuesta = self.client.get(self.url)
        self.assertRedirects(respuesta, reverse("aceptar_terminos"))

    def test_sin_aceptacion_no_crea_instancia_por_post(self) -> None:
        self.client.force_login(self.usuario)
        respuesta = self.client.post(self.url, {"nombre": "X", "dominio": "https://x.edocere.com"})
        self.assertRedirects(respuesta, reverse("aceptar_terminos"))
        self.assertEqual(InstanciaMoodle.objects.count(), 0)

    def test_con_aceptacion_vigente_muestra_el_formulario(self) -> None:
        terminos.registrar_aceptacion(self.cliente, self.usuario, terminos.VERSION_TERMINOS)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_superadministrador_no_es_bloqueado(self) -> None:
        admin = User.objects.create_superuser("root@test.cl", "root@test.cl", "Clave-segura-123!")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)