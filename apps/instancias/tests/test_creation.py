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
        self.assertContains(response, "Nombre de la instancia")
        self.assertContains(response, "Usar una dirección de Edocere")
        self.assertContains(response, "Usar mi propio dominio")
        self.assertContains(response, "URL del logo")
        assert self.cliente.razon_social is not None
        assert self.plan.nombre is not None
        self.assertContains(response, self.cliente.razon_social)
        self.assertContains(response, self.plan.nombre)

    def test_crea_instancia_con_direccion_de_edocere(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Campus Duoc",
                "tipo_dominio": "edocere",
                "subdominio": "duoc",
                "dominio_propio": "",
                "logo_url": "https://empresa.cl/logo.png",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("instancias:lista"))
        instancia = InstanciaMoodle.objects.get()
        self.assertEqual(instancia.cliente, self.cliente)
        self.assertEqual(instancia.nombre, "Campus Duoc")
        self.assertEqual(instancia.dominio, "https://duoc.edocere.com")
        self.assertEqual(instancia.logo_url, "https://empresa.cl/logo.png")
        self.assertEqual(instancia.estado, "activa")
        suscripcion = Suscripcion.objects.get(instancia=instancia)
        self.assertEqual(suscripcion.cliente, self.cliente)
        self.assertEqual(suscripcion.plan, self.plan)
        self.assertEqual(suscripcion.estado, "activa")
        self.assertIsNotNone(suscripcion.fecha_inicio)

    def test_crea_instancia_con_dominio_propio(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Aula Duoc",
                "tipo_dominio": "propio",
                "subdominio": "",
                "dominio_propio": "aula.duoc.cl",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        instancia = InstanciaMoodle.objects.get()
        self.assertEqual(instancia.nombre, "Aula Duoc")
        self.assertEqual(instancia.dominio, "https://aula.duoc.cl")

    def test_dominio_propio_acepta_https_y_barra_final(self) -> None:
        self.client.post(
            self.url,
            {
                "nombre": "Aula Duoc",
                "tipo_dominio": "propio",
                "dominio_propio": "HTTPS://Aula.Duoc.cl/",
                "logo_url": "",
            },
        )

        self.assertEqual(InstanciaMoodle.objects.get().dominio, "https://aula.duoc.cl")

    def test_logo_es_opcional(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Campus Duoc",
                "tipo_dominio": "edocere",
                "subdominio": "duoc",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("instancias:lista"))
        self.assertFalse(InstanciaMoodle.objects.get().logo_url)

    def test_nombre_es_obligatorio(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "",
                "tipo_dominio": "edocere",
                "subdominio": "duoc",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["nombre"])
        self.assertFalse(InstanciaMoodle.objects.exists())
        self.assertFalse(Suscripcion.objects.exists())

    def test_rechaza_subdominio_invalido_sin_crear_instancia(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Campus Duoc",
                "tipo_dominio": "edocere",
                "subdominio": "Mi Empresa!",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["subdominio"])
        self.assertFalse(InstanciaMoodle.objects.exists())
        self.assertFalse(Suscripcion.objects.exists())

    def test_rechaza_dominio_propio_invalido_sin_crear_instancia(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Aula Duoc",
                "tipo_dominio": "propio",
                "dominio_propio": "not a valid url",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["dominio_propio"])
        self.assertFalse(InstanciaMoodle.objects.exists())
        self.assertFalse(Suscripcion.objects.exists())

    def test_rechaza_dominio_propio_que_es_de_edocere(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Aula Duoc",
                "tipo_dominio": "propio",
                "dominio_propio": "algo.edocere.com",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["dominio_propio"])
        self.assertFalse(InstanciaMoodle.objects.exists())

    def test_rechaza_dominio_repetido(self) -> None:
        InstanciaMoodle.objects.create(
            cliente=self.otro_cliente,
            dominio="https://duoc.edocere.com",
        )

        response = self.client.post(
            self.url,
            {
                "nombre": "Campus Duoc",
                "tipo_dominio": "edocere",
                "subdominio": "duoc",
                "logo_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["subdominio"])
        self.assertEqual(InstanciaMoodle.objects.count(), 1)
        self.assertFalse(Suscripcion.objects.exists())

    def test_rechaza_logo_invalido_sin_crear_instancia(self) -> None:
        response = self.client.post(
            self.url,
            {
                "nombre": "Campus Duoc",
                "tipo_dominio": "edocere",
                "subdominio": "duoc",
                "logo_url": "not a valid url",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["logo_url"])
        self.assertFalse(InstanciaMoodle.objects.exists())

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
