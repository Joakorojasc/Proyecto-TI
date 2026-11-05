from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.planes.models import Plan, Suscripcion

from ..models import DocumentoTributario, MedioPago, Pago
from ..services import estado_cliente_para_instancia


class CheckoutViewTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(razon_social="Empresa Demo")
        self.otro_cliente = Cliente.objects.create(razon_social="Otra Empresa")
        usuario = User.objects.create_user(username="cliente", password="Password123!")
        UsuarioPortal.objects.create(usuario=usuario, cliente=self.cliente)
        self.client.force_login(usuario)
        plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="mensual")
        self.suscripcion = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=plan,
            estado="pendiente",
        )
        self.url = reverse(
            "pagos:checkout",
            kwargs={"suscripcion_id": self.suscripcion.id},
        )
        self.data = {
            "ultimos_4_digitos": "4242",
            "marca_tarjeta": "Visa",
            "token_simulado": "tok_checkout",
        }

    def test_pago_aprobado_genera_comprobante_y_activa_suscripcion(self) -> None:
        response = self.client.post(
            self.url,
            {key: value for key, value in self.data.items() if key != "token_simulado"}
            | {"resultado": "aprobado"},
        )

        self.assertRedirects(
            response,
            reverse("instancias:lista"),
        )
        self.assertEqual(MedioPago.objects.count(), 1)
        pago = Pago.objects.get()
        self.assertEqual(pago.estado, Pago.ESTADO_APROBADO)
        self.assertTrue(DocumentoTributario.objects.filter(pago=pago).exists())
        self.suscripcion.refresh_from_db()
        self.assertEqual(self.suscripcion.estado, "activa")
        self.assertEqual(
            estado_cliente_para_instancia(self.cliente.id, self.suscripcion.id),
            "aprobada",
        )

    def test_pago_rechazado_deja_suscripcion_pendiente_y_permite_reintento(self) -> None:
        response = self.client.post(self.url, {**self.data, "resultado": "rechazado"})

        self.assertRedirects(
            response,
            self.url,
        )
        self.assertEqual(Pago.objects.get().estado, Pago.ESTADO_RECHAZADO)
        self.assertFalse(DocumentoTributario.objects.exists())
        self.suscripcion.refresh_from_db()
        self.assertEqual(self.suscripcion.estado, "pendiente")
        self.assertEqual(
            estado_cliente_para_instancia(self.cliente.id, self.suscripcion.id),
            "rechazada",
        )

    def test_checkout_no_expone_suscripcion_de_otro_cliente(self) -> None:
        plan = Plan.objects.create(nombre="Otro plan", tipo_plan="mensual")
        otra_suscripcion = Suscripcion.objects.create(
            cliente=self.otro_cliente,
            plan=plan,
            estado="pendiente",
        )

        response = self.client.get(
            reverse("pagos:checkout", kwargs={"suscripcion_id": otra_suscripcion.id})
        )

        self.assertEqual(response.status_code, 404)

    def test_facturacion_muestra_solo_pagos_del_cliente_actual(self) -> None:
        otro_plan = Plan.objects.create(nombre="Plan Otro", tipo_plan="mensual")
        otra_suscripcion = Suscripcion.objects.create(
            cliente=self.otro_cliente,
            plan=otro_plan,
            estado="activa",
        )
        pago = Pago.objects.create(
            suscripcion=self.suscripcion,
            monto="16.50",
            estado=Pago.ESTADO_APROBADO,
        )
        DocumentoTributario.objects.create(
            pago=pago,
            tipo_documento="comprobante simulado",
            folio=2001,
        )
        Pago.objects.create(
            suscripcion=otra_suscripcion,
            monto="99.00",
            estado=Pago.ESTADO_APROBADO,
        )

        response = self.client.get(reverse("seccion_facturacion"))

        self.assertContains(response, "USD 16.50")
        self.assertContains(
            response,
            "Comprobante simulado - No válido como documento tributario (DTE)",
        )
        self.assertNotContains(response, "99.00")

    def test_suscripciones_muestra_historial_del_cliente_actual(self) -> None:
        Pago.objects.create(
            suscripcion=self.suscripcion,
            monto="16.50",
            estado=Pago.ESTADO_RECHAZADO,
        )

        response = self.client.get(reverse("seccion_suscripciones"))

        self.assertContains(response, "USD 16.50")
        self.assertContains(response, "Rechazado")
