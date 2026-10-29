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
        MigrationExecutor(connection).migrate([("clientes", "0005_integrar_rut_dev")])

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
        self.comprobar_bloqueo(["DEMO-PEQUENO-001", "76.543.210-3"])

    def test_conversion_demo_conserva_ids_y_relaciones_tras_seed(self) -> None:
        from django.core.management import call_command

        demo = [
            ("DEMO-PEQUENO-001", "76543210-3", "Empresa Demo Pequeña SpA"),
            ("DEMO-MEDIANO-001", "77777777-7", "Empresa Demo Mediana SpA"),
            ("DEMO-ANUAL-001", "65123456-5", "Organización Demo Anual SpA"),
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

    def comprobar_actualizacion_ruta(self, ruta: str, rut: str, esquema_dev_original: bool) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([("clientes", ruta)])
        if esquema_dev_original:
            Modelo = executor.loader.project_state([("clientes", ruta)]).apps.get_model(
                "clientes", "Cliente"
            )
            campo = Modelo._meta.get_field("rut")
            estricto = campo.clone()
            estricto.set_attributes_from_name("rut")
            estricto.model = Modelo
            estricto.null = False
            estricto.max_length = 12
            # Reproduce físicamente la versión de dev que otros integrantes
            # pudieron aplicar antes de que se corrigiera el archivo histórico.
            with connection.schema_editor() as editor:
                editor.alter_field(Modelo, campo, estricto)

        cliente = self.Cliente.objects.create(
            rut=rut,
            razon_social="Empresa Demo Pequeña SpA",
            email_contacto="demo@ejemplo.invalid",
        )
        Portal = self.apps_anteriores.get_model("clientes", "UsuarioPortal")
        Instancia = self.apps_anteriores.get_model("instancias", "InstanciaMoodle")
        Suscripcion = self.apps_anteriores.get_model("planes", "Suscripcion")
        Plan = self.apps_anteriores.get_model("planes", "Plan")
        portal = Portal.objects.create(cliente=cliente)
        instancia = Instancia.objects.create(cliente=cliente, dominio="pequena.demo.invalid")
        plan = Plan.objects.create(nombre="Plan mensual demo")
        suscripcion = Suscripcion.objects.create(cliente=cliente, instancia=instancia, plan=plan)

        self.migrar()

        cliente.refresh_from_db()
        self.assertEqual(cliente.rut, "76543210-3")
        portal.refresh_from_db()
        instancia.refresh_from_db()
        suscripcion.refresh_from_db()
        self.assertEqual(portal.cliente_id, cliente.pk)
        self.assertEqual(instancia.cliente_id, cliente.pk)
        self.assertEqual(suscripcion.cliente_id, cliente.pk)
        self.assertEqual(suscripcion.instancia_id, instancia.pk)
        # Prueba el esquema real, no solo el estado que Django cree aplicado.
        self.Cliente.objects.create(rut=None)
        self.Cliente.objects.create(rut=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.Cliente.objects.create(rut="76543210-3")

        from django.core.management import call_command

        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(self.Cliente.objects.get(rut="76543210-3").pk, cliente.pk)
        self.assertFalse(self.Cliente.objects.filter(rut="90000001-4").exists())
        self.assertEqual(Instancia.objects.get(pk=instancia.pk).cliente_id, cliente.pk)
        self.assertEqual(Suscripcion.objects.get(pk=suscripcion.pk).cliente_id, cliente.pk)

    def test_actualiza_base_con_nuestra_0004_ya_aplicada(self) -> None:
        self.comprobar_actualizacion_ruta("0004_rut_unico", "90000001-4", False)

    def test_actualiza_base_con_0003_original_de_dev_ya_aplicada(self) -> None:
        self.comprobar_actualizacion_ruta("0003_rut_validado_y_unico", "76543210-3", True)

    def test_colision_entre_ambos_demos_no_fusiona_clientes(self) -> None:
        for rut in ("90000001-4", "76543210-3"):
            self.Cliente.objects.create(
                rut=rut,
                razon_social="Empresa Demo Pequeña SpA",
                email_contacto="demo@ejemplo.invalid",
            )
        antes = list(self.Cliente.objects.order_by("pk").values())
        with self.assertRaisesRegex(RuntimeError, "RUT equivalente"):
            self.migrar()
        self.assertEqual(antes, list(self.Cliente.objects.order_by("pk").values()))

    def test_rut_numerico_de_institucion_ajena_no_se_convierte_en_demo(self) -> None:
        cliente = self.Cliente.objects.create(rut="90000001-4", razon_social="Institución ajena")
        self.migrar()
        cliente.refresh_from_db()
        self.assertEqual(cliente.rut, "90000001-4")
