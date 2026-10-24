from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.clientes.models import Cliente, UsuarioPortal
from apps.clientes.validators import normalizar_rut
from apps.estadisticas.models import MedicionUsoMensual
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

        for cliente in Cliente.objects.all():
            assert cliente.rut is not None
            self.assertEqual(cliente.rut, normalizar_rut(cliente.rut))

    def test_seed_actualiza_rut_historico_sin_recrear_clientes_o_relaciones(self) -> None:
        call_command("seed_demo", verbosity=0)
        cliente = Cliente.objects.get(rut="90000001-4")
        usuario = User.objects.create_user(username="admin-demo")
        UsuarioPortal.objects.create(usuario=usuario, cliente=cliente)
        ids = dict(Cliente.objects.values_list("rut", "pk"))
        consultas = [
            UsuarioPortal.objects.all(),
            InstanciaMoodle.objects.all(),
            Suscripcion.objects.all(),
            MedicionUsoMensual.objects.all(),
        ]
        relaciones = [list(consulta.order_by("pk").values()) for consulta in consultas]
        anteriores = {
            "90000001-4": "DEMO-PEQUENO-001",
            "90000002-2": "DEMO-MEDIANO-001",
            "90000003-0": "DEMO-ANUAL-001",
        }
        # Reproduce el contenido histórico sin pasar por el save() nuevo.
        for rut, anterior in anteriores.items():
            Cliente.objects.filter(rut=rut).update(rut=anterior)

        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)

        self.assertEqual(dict(Cliente.objects.values_list("rut", "pk")), ids)
        self.assertEqual(
            relaciones, [list(consulta.order_by("pk").values()) for consulta in consultas]
        )

    def test_seed_no_sobrescribe_institucion_que_ocupa_rut_demo(self) -> None:
        cliente = Cliente.objects.create(
            rut="90000001-4", razon_social="Institución ajena", email_contacto="ajena@demo.cl"
        )

        with self.assertRaisesRegex(CommandError, "No se sobrescribirán"):
            call_command("seed_demo", verbosity=0)

        cliente.refresh_from_db()
        self.assertEqual(cliente.razon_social, "Institución ajena")
        self.assertEqual(cliente.email_contacto, "ajena@demo.cl")
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertFalse(InstanciaMoodle.objects.exists())
        self.assertFalse(Suscripcion.objects.exists())

    def test_seed_no_fusiona_cliente_historico_y_nuevo(self) -> None:
        call_command("seed_demo", verbosity=0)
        Cliente.objects.bulk_create([Cliente(rut="DEMO-PEQUENO-001", razon_social="Histórico")])
        antes = list(Cliente.objects.order_by("pk").values())

        with self.assertRaisesRegex(CommandError, "no se fusionarán"):
            call_command("seed_demo", verbosity=0)

        self.assertEqual(list(Cliente.objects.order_by("pk").values()), antes)
