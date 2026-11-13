from unittest.mock import Mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.clientes import terminos
from apps.clientes.models import Cliente, UsuarioPortal
from apps.planes.models import Plan, Suscripcion

from ..models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    InstanciaMoodle,
    SolicitudAprovisionamiento,
    TipoOperacion,
)
from ..services import (
    ACTOR_ASSERTION_HEADER,
    OPERATIONS_URL,
    SIMULATED_ACTOR_ASSERTION,
    AprovisionamientoError,
    AprovisionamientoService,
    RespuestaAprovisionamiento,
    SimuladorAprovisionamientoAPI,
)


class CrearInstanciaViewTests(TestCase):
    def setUp(self) -> None:
        self.cliente = Cliente.objects.create(rut="77020202-7", razon_social="Empresa Demo")
        self.otro_cliente = Cliente.objects.create(rut="77030303-6", razon_social="Otra Empresa")
        usuario = User.objects.create_user(
            username="propietario",
            email="propietario@demo.cl",
            first_name="Persona",
            last_name="Propietaria",
        )
        UsuarioPortal.objects.create(
            usuario=usuario,
            cliente=self.cliente,
            email="propietario@demo.cl",
        )
        terminos.registrar_aceptacion(self.cliente, usuario, terminos.VERSION_TERMINOS)
        self.client.force_login(usuario)
        self.plan = Plan.objects.create(nombre="Plan Mensual", tipo_plan="Mensual")
        self.url = reverse(
            "instancias:crear",
            kwargs={"cliente_id": self.cliente.id, "plan_id": self.plan.id},
        )

    def test_choices_incluyen_el_vocabulario_de_estado_y_operacion_rc3(self) -> None:
        estados_rc3 = {
            "PENDING",
            "ACTIVE",
            "FAILED",
            "DEPROVISIONED",
            "SUSPENDED",
            "RECOVERING",
            "RECOVERY_FAILED",
            "RESTORING",
            "RESTORE_FAILED",
            "PURGING",
            "PURGE_FAILED",
            "PURGED",
        }
        operaciones_rc3 = {
            "PROVISION",
            "DEPROVISION",
            "BACKUP",
            "RESTORE",
            "CLONE",
            "SUSPEND",
            "REACTIVATE",
            "RECOVER",
            "UPDATE_BRANDING",
        }

        self.assertTrue(estados_rc3.issubset({value for value, _ in EstadoInstancia.choices}))
        self.assertEqual(
            {value for value, _ in EstadoInstancia.choices},
            estados_rc3,
        )
        self.assertTrue(operaciones_rc3.issubset({value for value, _ in TipoOperacion.choices}))

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
        self.assertEqual(instancia.estado, EstadoInstancia.PENDING)
        solicitud = SolicitudAprovisionamiento.objects.get(instancia=instancia)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.PENDIENTE)
        self.assertIsNone(solicitud.operation_id)
        self.assertTrue(solicitud.idempotency_key)
        suscripcion = Suscripcion.objects.get(instancia=instancia)
        self.assertEqual(suscripcion.cliente, self.cliente)
        self.assertEqual(suscripcion.plan, self.plan)
        self.assertEqual(suscripcion.estado, "pendiente")
        self.assertIsNotNone(suscripcion.fecha_inicio)

    def test_servicio_envia_contrato_y_persiste_aceptacion(self) -> None:
        instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            dominio="https://campus.edocere.com",
        )
        solicitud = SolicitudAprovisionamiento.objects.create(instancia=instancia)
        proveedor = Mock()
        proveedor.enviar_solicitud.return_value = RespuestaAprovisionamiento(
            status_code=202,
            body={"operation_id": "SIM-42", "status": "PENDING"},
        )
        servicio = AprovisionamientoService(proveedor)
        password_hash = User.objects.get(username="propietario").password

        respuesta = servicio.enviar_solicitud(solicitud)
        llamada = proveedor.enviar_solicitud.call_args
        assert llamada is not None
        payload = llamada.args[0]

        self.assertEqual(
            {key: value for key, value in payload.items() if key != "manager"},
            {
                "operation_type": "PROVISION",
                "tenant_slug": f"tenant-{instancia.pk}",
                "hostname": "campus.edocere.com",
                "owner_ref": str(self.cliente.pk),
                "language": "es",
            },
        )
        manager = payload["manager"]
        self.assertIsInstance(manager, dict)
        assert isinstance(manager, dict)
        password = manager["password"]
        self.assertEqual(
            {key: value for key, value in manager.items() if key != "password"},
            {
                "username": "propietario",
                "firstname": "Persona",
                "lastname": "Propietaria",
                "email": "propietario@demo.cl",
            },
        )
        self.assertIsInstance(password, str)
        self.assertTrue(password)
        self.assertEqual(User.objects.get(username="propietario").password, password_hash)
        tenant_slug = payload["tenant_slug"]
        self.assertIsInstance(tenant_slug, str)
        assert isinstance(tenant_slug, str)
        self.assertLessEqual(len(tenant_slug), 63)
        self.assertRegex(tenant_slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        proveedor.enviar_solicitud.assert_called_once_with(
            payload,
            idempotency_key=str(solicitud.idempotency_key),
            url=OPERATIONS_URL,
            headers={ACTOR_ASSERTION_HEADER: SIMULATED_ACTOR_ASSERTION},
        )
        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(respuesta.body["status"], "PENDING")
        solicitud.refresh_from_db()
        instancia.refresh_from_db()
        self.assertEqual(solicitud.operation_id, "SIM-42")
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.PENDIENTE)
        self.assertEqual(instancia.estado, EstadoInstancia.PENDING)

    def test_rechaza_tenant_slug_mayor_a_63_caracteres(self) -> None:
        with self.assertRaises(AprovisionamientoError):
            AprovisionamientoService.construir_tenant_slug(10**63)

    def test_respuesta_no_202_no_persiste_una_operacion(self) -> None:
        instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            dominio="https://campus.edocere.com",
        )
        solicitud = SolicitudAprovisionamiento.objects.create(instancia=instancia)
        proveedor = Mock()
        proveedor.enviar_solicitud.return_value = RespuestaAprovisionamiento(
            status_code=503,
            body={"operation_id": "SIM-42", "status": "PENDING"},
        )

        with self.assertRaises(AprovisionamientoError):
            AprovisionamientoService(proveedor).enviar_solicitud(solicitud)

        solicitud.refresh_from_db()
        self.assertIsNone(solicitud.operation_id)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.PENDIENTE)

    def test_respuesta_202_mal_formada_no_persiste_una_operacion(self) -> None:
        instancia = InstanciaMoodle.objects.create(
            cliente=self.cliente,
            dominio="https://campus.edocere.com",
        )
        solicitud = SolicitudAprovisionamiento.objects.create(instancia=instancia)
        proveedor = Mock()
        proveedor.enviar_solicitud.return_value = RespuestaAprovisionamiento(
            status_code=202,
            body={"operation_id": "SIM-42", "status": "RUNNING"},
        )

        with self.assertRaises(AprovisionamientoError):
            AprovisionamientoService(proveedor).enviar_solicitud(solicitud)

        solicitud.refresh_from_db()
        self.assertIsNone(solicitud.operation_id)
        self.assertEqual(solicitud.estado, EstadoAprovisionamiento.PENDIENTE)

    def test_simulador_responde_con_aceptacion_asincrona(self) -> None:
        simulador = SimuladorAprovisionamientoAPI()
        respuesta = simulador.enviar_solicitud(
            {
                "operation_type": "PROVISION",
                "tenant_slug": "tenant-42",
                "hostname": "campus.edocere.com",
                "owner_ref": str(self.cliente.pk),
            },
            idempotency_key="test-key",
            url=OPERATIONS_URL,
            headers={ACTOR_ASSERTION_HEADER: SIMULATED_ACTOR_ASSERTION},
        )
        repeticion = simulador.enviar_solicitud(
            {
                "operation_type": "PROVISION",
                "tenant_slug": "tenant-99",
                "hostname": "otro.edocere.com",
                "owner_ref": str(self.cliente.pk),
            },
            idempotency_key="test-key",
            url=OPERATIONS_URL,
            headers={ACTOR_ASSERTION_HEADER: SIMULATED_ACTOR_ASSERTION},
        )

        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(
            respuesta.body,
            {"operation_id": "SIM-42", "status": "PENDING"},
        )
        self.assertIs(repeticion, respuesta)

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
