from django.test import TestCase

from apps.clientes.models import Cliente
from apps.planes.models import Plan, Suscripcion

from ..models import DocumentoTributario, MedioPago, Pago


class PagoModelTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(razon_social="Empresa Demo")
        plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="mensual")
        self.suscripcion = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=plan,
            estado="activa",
        )

    def test_medio_pago_guarda_solo_datos_simulados(self) -> None:
        medio = MedioPago.objects.create(
            cliente=self.cliente,
            ultimos_4_digitos="4242",
            marca_tarjeta="Visa",
            token_simulado="tok_demo_4242",
        )

        self.assertEqual(medio.ultimos_4_digitos, "4242")
        self.assertNotIn("numero", {field.name for field in MedioPago._meta.fields})
        self.assertNotIn("cvv", {field.name for field in MedioPago._meta.fields})

    def test_pago_usa_estados_admitidos_y_comprobante_unico(self) -> None:
        pago = Pago.objects.create(
            suscripcion=self.suscripcion,
            monto="16.50",
            estado=Pago.ESTADO_APROBADO,
        )
        comprobante = DocumentoTributario.objects.create(
            pago=pago,
            tipo_documento="factura simulada",
            folio=1001,
        )

        self.assertEqual(pago.estado, "aprobado")
        self.assertEqual(pago.suscripcion, self.suscripcion)
        self.assertEqual(comprobante.pago_id, pago.id)
        self.assertEqual(comprobante.folio, 1001)
