from typing import Any

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionRutTests(TransactionTestCase):
    """Usa modelos históricos: reproduce datos que existían antes de la validación."""

    def setUp(self) -> None:
        super().setUp()
        executor = MigrationExecutor(connection)
        self.destinos = executor.loader.graph.leaf_nodes()
        executor.migrate([("clientes", "0002_usuarioportal_usuario")])
        executor = MigrationExecutor(connection)
        self.apps_anteriores = executor.loader.project_state(
            list(executor.loader.applied_migrations)
        ).apps
        self.Cliente = self.apps_anteriores.get_model("clientes", "Cliente")

    def tearDown(self) -> None:
        # Limpieza exclusiva del test: permite restaurar el esquema incluso si
        # el escenario dejó a propósito registros incompatibles con la migración.
        self.Cliente.objects.update(rut=None)
        MigrationExecutor(connection).migrate(self.destinos)
        super().tearDown()

    def migrar(self) -> None:
        MigrationExecutor(connection).migrate([("clientes", "0004_rut_unico")])

    def test_normaliza_datos_sin_perder_clientes_ni_relaciones(self) -> None:
        cliente = self.Cliente.objects.create(
            rut="76.123.456-0",
            razon_social="Institución histórica",
            email_contacto="historia@demo.cl",
        )
        con_k = self.Cliente.objects.create(rut="0.000.006-k")
        vacio = self.Cliente.objects.create(rut="")
        nulo = self.Cliente.objects.create(rut=None)
        Usuario = self.apps_anteriores.get_model("auth", "User")
        Portal = self.apps_anteriores.get_model("clientes", "UsuarioPortal")
        Instancia = self.apps_anteriores.get_model("instancias", "InstanciaMoodle")
        Plan = self.apps_anteriores.get_model("planes", "Plan")
        Suscripcion = self.apps_anteriores.get_model("planes", "Suscripcion")
        usuario = Usuario.objects.create(username="historico")
        portal = Portal.objects.create(usuario=usuario, cliente=cliente)
        instancia = Instancia.objects.create(cliente=cliente, dominio="https://historica.invalid")
        plan = Plan.objects.create(cliente=cliente, nombre="Plan histórico")
        suscripcion = Suscripcion.objects.create(cliente=cliente, instancia=instancia, plan=plan)
        relaciones = [
            (Portal, portal.pk),
            (Instancia, instancia.pk),
            (Plan, plan.pk),
            (Suscripcion, suscripcion.pk),
            (Usuario, usuario.pk),
        ]
        antes = [modelo.objects.values().get(pk=pk) for modelo, pk in relaciones]

        self.migrar()

        self.assertEqual(self.Cliente.objects.count(), 4)
        cliente.refresh_from_db()
        self.assertEqual(cliente.rut, "76123456-0")
        self.assertEqual(cliente.razon_social, "Institución histórica")
        self.assertEqual(cliente.email_contacto, "historia@demo.cl")
        self.assertEqual(self.Cliente.objects.get(pk=con_k.pk).rut, "6-K")
        self.assertIsNone(self.Cliente.objects.get(pk=vacio.pk).rut)
        self.assertIsNone(self.Cliente.objects.get(pk=nulo.pk).rut)
        self.assertEqual(antes, [modelo.objects.values().get(pk=pk) for modelo, pk in relaciones])
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.Cliente.objects.create(rut="76123456-0")
        self.Cliente.objects.create(rut=None)

    def comprobar_bloqueo(self, ruts: list[str]) -> None:
        for rut in ["12.345.678-5", *ruts]:
            self.Cliente.objects.create(rut=rut)
        antes = list(self.Cliente.objects.order_by("pk").values())

        with self.assertRaisesRegex(RuntimeError, "No se modificó ningún cliente") as error:
            self.migrar()

        self.assertIn("ID", str(error.exception))
        self.assertEqual(antes, list(self.Cliente.objects.order_by("pk").values()))
        self.assertNotIn(
            ("clientes", "0003_normalizar_rut"),
            MigrationExecutor(connection).loader.applied_migrations,
        )

    def test_duplicados_equivalentes_bloquean_sin_escribir(self) -> None:
        self.comprobar_bloqueo(["76.123.456-0", "76123456-0"])

    def test_k_minuscula_y_ceros_no_ocultan_duplicados(self) -> None:
        self.comprobar_bloqueo(["6-K", "0006-k"])

    def test_rut_invalido_bloquea_sin_corregir_digito(self) -> None:
        self.comprobar_bloqueo(["76.123.456-7"])

    def test_colision_demo_bloquea_sin_fusionar(self) -> None:
        self.comprobar_bloqueo(["DEMO-PEQUENO-001", "90.000.001-4"])

    def test_conversion_demo_conserva_ids_y_relaciones_tras_seed(self) -> None:
        from django.core.management import call_command

        demo = [
            ("DEMO-PEQUENO-001", "90000001-4", "Empresa Demo Pequeña SpA"),
            ("DEMO-MEDIANO-001", "90000002-2", "Empresa Demo Mediana SpA"),
            ("DEMO-ANUAL-001", "90000003-0", "Organización Demo Anual SpA"),
        ]
        ids: dict[str, Any] = {}
        for anterior, nuevo, nombre in demo:
            ids[nuevo] = self.Cliente.objects.create(
                rut=anterior, razon_social=nombre, email_contacto="demo@ejemplo.invalid"
            ).pk

        self.migrar()
        call_command("seed_demo", verbosity=0)
        Instancia = self.apps_anteriores.get_model("instancias", "InstanciaMoodle")
        Suscripcion = self.apps_anteriores.get_model("planes", "Suscripcion")
        instancias = list(Instancia.objects.order_by("pk").values())
        suscripciones = list(Suscripcion.objects.order_by("pk").values())
        call_command("seed_demo", verbosity=0)

        self.assertEqual(dict(self.Cliente.objects.values_list("rut", "pk")), ids)
        self.assertEqual(list(Instancia.objects.order_by("pk").values()), instancias)
        self.assertEqual(list(Suscripcion.objects.order_by("pk").values()), suscripciones)

    def test_revertir_restriccion_no_borra_clientes(self) -> None:
        cliente = self.Cliente.objects.create(rut="76.123.456-0")
        self.migrar()
        MigrationExecutor(connection).migrate([("clientes", "0002_usuarioportal_usuario")])
        cliente.refresh_from_db()
        self.assertEqual(cliente.rut, "76123456-0")
        self.assertEqual(self.Cliente.objects.count(), 1)
