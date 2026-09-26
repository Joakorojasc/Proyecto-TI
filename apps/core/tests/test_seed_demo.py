from django.core.management import call_command
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Suscripcion


class SeedDemoTests(TestCase):
    def test_seed_crea_suscripciones_por_instancia_y_es_idempotente(self) -> None:
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)

        self.assertEqual(Cliente.objects.count(), 3)
        self.assertEqual(InstanciaMoodle.objects.count(), 4)
        self.assertEqual(Suscripcion.objects.count(), 4)

        dominios = {
            "pequena.demo.invalid",
            "mediana.demo.invalid",
            "anual-principal.demo.invalid",
            "anual-secundaria.demo.invalid",
        }
        instancias = InstanciaMoodle.objects.filter(dominio__in=dominios)
        self.assertEqual(instancias.count(), 4)

        for instancia in instancias:
            suscripciones = instancia.suscripciones.filter(estado="activa")
            self.assertEqual(suscripciones.count(), 1)
            suscripcion = suscripciones.get()
            self.assertIsNotNone(suscripcion.instancia_id)
            self.assertEqual(suscripcion.cliente_id, instancia.cliente_id)
