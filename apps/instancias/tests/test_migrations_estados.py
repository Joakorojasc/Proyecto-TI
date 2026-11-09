from typing import Any

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionEstadoInstanciaTests(TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        executor = MigrationExecutor(connection)
        self.destinos = executor.loader.graph.leaf_nodes()
        self.migracion_inicial = ("instancias", "0004_instanciamoodle_created_at")
        executor.migrate([self.migracion_inicial])
        executor = MigrationExecutor(connection)
        apps_anteriores = executor.loader.project_state([self.migracion_inicial]).apps
        self.cliente_model: Any = apps_anteriores.get_model("clientes", "Cliente")
        self.instancia_model: Any = apps_anteriores.get_model("instancias", "InstanciaMoodle")

    def tearDown(self) -> None:
        MigrationExecutor(connection).migrate(self.destinos)
        super().tearDown()

    def test_migra_estados_heredados_al_vocabulario_rc3(self) -> None:
        cliente = self.cliente_model.objects.create(rut="77020202-7")
        for dominio, estado in (
            ("pendiente.example.com", "pendiente"),
            ("activa.example.com", "activa"),
            ("archivada.example.com", "archivada"),
            ("sin-estado.example.com", None),
        ):
            self.instancia_model.objects.create(
                cliente=cliente,
                dominio=dominio,
                estado=estado,
            )

        MigrationExecutor(connection).migrate([("instancias", "0005_aprovisionamiento")])
        apps_intermedias = (
            MigrationExecutor(connection)
            .loader.project_state([("instancias", "0005_aprovisionamiento")])
            .apps
        )
        instancia_intermedia: Any = apps_intermedias.get_model("instancias", "InstanciaMoodle")
        estados_intermedios = dict(instancia_intermedia.objects.values_list("dominio", "estado"))
        self.assertEqual(
            estados_intermedios,
            {
                "pendiente.example.com": "pendiente",
                "activa.example.com": "activa",
                "archivada.example.com": "archivada",
                "sin-estado.example.com": "pendiente",
            },
        )

        MigrationExecutor(connection).migrate([("instancias", "0007_alter_instanciamoodle_estado")])
        apps_actuales = MigrationExecutor(connection).loader.project_state(self.destinos).apps
        instancia_actual: Any = apps_actuales.get_model("instancias", "InstanciaMoodle")

        estados = dict(instancia_actual.objects.values_list("dominio", "estado"))
        self.assertEqual(
            estados,
            {
                "pendiente.example.com": "PENDING",
                "activa.example.com": "ACTIVE",
                "archivada.example.com": "DEPROVISIONED",
                "sin-estado.example.com": "PENDING",
            },
        )
