from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.clientes.models import Cliente
from apps.instancias.models import InstanciaMoodle

from ..models import Plan, Suscripcion


class SuscripcionModelTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(razon_social="Cliente Uno")
        self.otro_cliente = Cliente.objects.create(razon_social="Cliente Dos")
        self.instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            dominio="uno.example.com",
        )
        self.plan_mensual = Plan.objects.create(
            nombre="Plan Mensual",
            tipo_plan="Mensual",
        )
        self.plan_anual = Plan.objects.create(
            nombre="Plan Anual",
            tipo_plan="Anual",
        )

    def test_suscripcion_puede_asociarse_a_una_instancia(self) -> None:
        suscripcion = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
        )

        self.assertEqual(suscripcion.instancia, self.instancia)

    def test_instancia_devuelve_suscripciones_asociadas(self) -> None:
        suscripcion = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
        )

        self.assertQuerySetEqual(self.instancia.suscripciones.all(), [suscripcion])

    def test_instancia_puede_tener_multiples_suscripciones_historicas(self) -> None:
        primera = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
            estado="finalizada",
        )
        segunda = Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_anual,
            instancia=self.instancia,
            estado="activa",
        )

        self.assertQuerySetEqual(
            self.instancia.suscripciones.order_by("id"),
            [primera, segunda],
        )

    def test_suscripciones_de_una_instancia_pueden_usar_planes_distintos(self) -> None:
        Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
        )
        Suscripcion.objects.create(
            cliente=self.cliente,
            plan=self.plan_anual,
            instancia=self.instancia,
        )

        self.assertQuerySetEqual(
            self.instancia.suscripciones.order_by("id").values_list("plan_id", flat=True),
            [self.plan_mensual.id, self.plan_anual.id],
        )

    def test_clean_acepta_cliente_coincidente(self) -> None:
        suscripcion = Suscripcion(
            cliente=self.cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
            estado="activa",
            fecha_inicio=timezone.now(),
        )

        suscripcion.full_clean()

    def test_clean_rechaza_cliente_diferente(self) -> None:
        suscripcion = Suscripcion(
            cliente=self.otro_cliente,
            plan=self.plan_mensual,
            instancia=self.instancia,
            estado="activa",
            fecha_inicio=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            suscripcion.full_clean()

    def test_suscripcion_antigua_sin_instancia_sigue_siendo_valida(self) -> None:
        suscripcion = Suscripcion(
            cliente=self.cliente,
            plan=self.plan_mensual,
            estado="activa",
            fecha_inicio=timezone.now(),
        )

        suscripcion.full_clean()
