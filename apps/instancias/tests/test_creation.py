from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.planes.models import Plan, Suscripcion

from ..models import InstanciaMoodle


class CrearInstanciaViewTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(razon_social="Empresa Demo")
        self.otro_cliente = Cliente.objects.create(razon_social="Otra Empresa")
        self.plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="Mensual")
        self.url = reverse(
            "instancias:crear",
            kwargs={"cliente_id": self.cliente.id, "plan_id": self.plan.id},
        )

    def test_muestra_formulario_con_datos_del_cliente_y_plan(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "URL del dominio de la instancia")
        self.assertContains(response, "URL del logo")
        self.assertContains(response, self.cliente.razon_social)
        self.assertContains(response, self.plan.nombre)

    def test_crea_instancia_activa_y_suscripcion_del_cliente(self) -> None:
        response = self.client.post(
            self.url,
            {
                "dominio": "https://aula.empresa.cl",
                "logo_url": "https://empresa.cl/logo.png",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        instancia = InstanciaMoodle.objects.get()
        self.assertEqual(instancia.cliente, self.cliente)
        self.assertEqual(instancia.dominio, "https://aula.empresa.cl")
        self.assertEqual(instancia.logo_url, "https://empresa.cl/logo.png")
        self.assertEqual(instancia.estado, "activa")
        suscripcion = Suscripcion.objects.get(instancia=instancia)
        self.assertEqual(suscripcion.cliente, self.cliente)
        self.assertEqual(suscripcion.plan, self.plan)
        self.assertEqual(suscripcion.estado, "activa")
        self.assertIsNotNone(suscripcion.fecha_inicio)

    def test_logo_es_opcional(self) -> None:
        response = self.client.post(
            self.url,
            {
                "dominio": "https://aula.empresa.cl",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
        self.assertFalse(InstanciaMoodle.objects.get().logo_url)

    def test_rechaza_urls_invalidas_sin_crear_instancia(self) -> None:
        response = self.client.post(
            self.url,
            {
                "dominio": "not a valid url",
                "logo_url": "not a valid url",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["dominio"])
        self.assertTrue(response.context["form"].errors["logo_url"])
        self.assertFalse(InstanciaMoodle.objects.exists())
        self.assertFalse(Suscripcion.objects.exists())

    def test_no_permite_usar_el_plan_personalizado_de_otro_cliente(self) -> None:
        plan_ajeno = Plan.objects.create(
            nombre="Plan exclusivo",
            cliente=self.otro_cliente,
        )
        url = reverse(
            "instancias:crear",
            kwargs={"cliente_id": self.cliente.id, "plan_id": plan_ajeno.id},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
