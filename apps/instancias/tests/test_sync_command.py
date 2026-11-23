import json
import os
from email.message import Message
from functools import partial
from io import BytesIO, StringIO
from unittest.mock import MagicMock, call, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.clientes.models import Cliente
from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    InstanciaMoodle,
    SolicitudAprovisionamiento,
)

from ..sync_client import TenantctlReadClient, TenantctlReadError


def _http_response(payload: dict[str, object]) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


def _http_error(code: int, payload: dict[str, object]) -> HTTPError:
    return HTTPError(
        "https://tenantctl.example.cl/api/v1/tenants/tenant/usage",
        code,
        "HTTP error",
        Message(),
        BytesIO(json.dumps(payload).encode("utf-8")),
    )


class TenantctlReadClientTests(TestCase):
    def create_client(
        self,
        *,
        base_url: str = "https://tenantctl.example.cl",
        service_token: str | None = "service-token",
        actor_assertion: str | None = None,
    ) -> TenantctlReadClient:
        environment = {"TENANTCTL_API_BASE_URL": base_url}
        if service_token is not None:
            environment["TENANTCTL_SERVICE_TOKEN"] = service_token
        if actor_assertion is not None:
            environment["TENANTCTL_ACTOR_ASSERTION"] = actor_assertion
        with patch.dict(os.environ, environment, clear=True):
            return TenantctlReadClient()

    def test_construye_endpoints_cabeceras_y_parametros(self) -> None:
        client = self.create_client()
        requests_to_make = [
            partial(client.list_tenants, limit=17, cursor="cursor-2", owner_ref="owner-1"),
            partial(client.get_tenant, "tenant/one"),
            partial(client.list_operations, limit=9, cursor="operations-2"),
            partial(client.get_monthly_usage, "tenant-one", "2026-10"),
            partial(
                client.list_usage_courses,
                "tenant-one",
                "2026-10",
                limit=3,
                cursor="courses-2",
            ),
        ]
        with patch(
            "apps.instancias.sync_client.urlopen",
            side_effect=[_http_response({}) for _ in requests_to_make],
        ) as urlopen:
            for request in requests_to_make:
                request()

        requests = [item.args[0] for item in urlopen.call_args_list]
        self.assertEqual(
            [urlsplit(request.full_url).path for request in requests],
            [
                "/api/v1/tenants",
                "/api/v1/tenants/tenant%2Fone",
                "/api/v1/operations",
                "/api/v1/tenants/tenant-one/usage",
                "/api/v1/tenants/tenant-one/usage/courses",
            ],
        )
        self.assertEqual(
            parse_qs(urlsplit(requests[0].full_url).query),
            {"limit": ["17"], "cursor": ["cursor-2"], "owner_ref": ["owner-1"]},
        )
        self.assertEqual(
            parse_qs(urlsplit(requests[2].full_url).query),
            {"limit": ["9"], "cursor": ["operations-2"]},
        )
        self.assertEqual(
            parse_qs(urlsplit(requests[4].full_url).query),
            {"limit": ["3"], "cursor": ["courses-2"], "month": ["2026-10"]},
        )
        for request in requests:
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(headers["authorization"], "Bearer service-token")
            self.assertNotIn("x-panel-actor-assertion", headers)

    def test_agrega_actor_assertion_solo_cuando_se_configura(self) -> None:
        client = self.create_client(actor_assertion="human-assertion")
        with patch(
            "apps.instancias.sync_client.urlopen",
            return_value=_http_response({}),
        ) as urlopen:
            client.list_operations()

        request = urlopen.call_args.args[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["x-panel-actor-assertion"], "human-assertion")

    def test_valida_https_hostname_y_loopback(self) -> None:
        for base_url in (
            "https://tenantctl.example.cl",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://[::1]:8000",
        ):
            with self.subTest(base_url=base_url):
                self.create_client(base_url=base_url)

        for base_url in (
            "",
            "http://tenantctl.example.cl",
            "https:///api",
            "https://",
            "https://tenantctl.example.cl/api/v1",
            "https://tenantctl.example.cl:invalid",
            "https://[::1",
        ):
            with self.subTest(base_url=base_url), self.assertRaises(TenantctlReadError):
                self.create_client(base_url=base_url)

        with self.assertRaises(TenantctlReadError):
            self.create_client(service_token="")

    def test_404_y_usage_data_unavailable_son_falta_de_datos(self) -> None:
        client = self.create_client()
        with patch(
            "apps.instancias.sync_client.urlopen",
            side_effect=_http_error(404, {"error": "NOT_FOUND"}),
        ):
            self.assertIsNone(client.get_tenant("missing"))

        with patch(
            "apps.instancias.sync_client.urlopen",
            side_effect=_http_error(409, {"error": "USAGE_DATA_UNAVAILABLE"}),
        ):
            self.assertIsNone(client.get_monthly_usage("tenant-one", "2026-10"))

    def test_otros_409_generan_error(self) -> None:
        client = self.create_client()
        for usage_endpoint in (False, True):
            with self.subTest(usage_endpoint=usage_endpoint):
                error = _http_error(
                    409,
                    {"error": "TENANT_STATE_CONFLICT"}
                    if usage_endpoint
                    else {"error": "USAGE_DATA_UNAVAILABLE"},
                )
                with (
                    patch("apps.instancias.sync_client.urlopen", side_effect=error),
                    self.assertRaises(TenantctlReadError),
                ):
                    if usage_endpoint:
                        client.get_monthly_usage("tenant-one", "2026-10")
                    else:
                        client.list_operations()


class SincronizarAprovisionamientoTests(TestCase):
    def setUp(self) -> None:
        self.client_record = Cliente.objects.create(
            rut="76123456-0",
            razon_social="Cliente local",
        )
        self.instance = InstanciaMoodle.objects.create(
            cliente=self.client_record,
            dominio="https://campus.example.cl",
            nombre="Nombre anterior",
            version="4.4",
            estado=EstadoInstancia.PENDING,
        )
        self.tenant = {
            "tenant_slug": "campus",
            "owner_ref": str(self.client_record.pk),
            "primary_hostname": "campus.example.cl",
            "status": "ACTIVE",
        }
        self.tenant_detail = {
            **self.tenant,
            "moodle_version": "5.1.1",
            "branding": {"site_name": "Campus Edocere"},
        }
        self.usage = {
            "tenant_slug": "campus",
            "period": "2026-10",
            "period_timezone": "America/Santiago",
            "activity_definition_version": "moodle-course-participation-v1",
            "snapshot_id": "snapshot-campus-2026-10",
            "revision": 1,
            "status": "CLOSED",
            "evidence_complete": True,
            "billable_users": 28,
        }
        self.course_metadata = {
            key: self.usage[key]
            for key in (
                "tenant_slug",
                "period",
                "period_timezone",
                "activity_definition_version",
                "snapshot_id",
                "revision",
                "status",
            )
        }

    def configure_client(self, client: MagicMock) -> None:
        client.list_tenants.return_value = {
            "items": [self.tenant],
            "next_cursor": None,
        }
        client.get_tenant.return_value = self.tenant_detail
        client.list_operations.return_value = {
            "items": [
                {
                    "operation_id": "operation-123",
                    "operation_type": "PROVISION",
                    "tenant_slug": "campus",
                    "status": "FAILED",
                    "attempt_count": 2,
                    "error": {"code": "EXECUTION_ERROR", "message": "Fallo de aprovisionamiento."},
                },
                {
                    "operation_id": "backup-456",
                    "operation_type": "BACKUP",
                    "tenant_slug": "campus",
                    "status": "COMPLETED",
                },
            ],
            "next_cursor": None,
        }
        client.get_monthly_usage.return_value = self.usage
        client.list_usage_courses.return_value = {
            **self.course_metadata,
            "items": [
                {"course_ref": "course-a", "qualifying_event_count": 2},
                {"course_ref": "course-b", "qualifying_event_count": 5},
            ],
            "next_cursor": None,
        }

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_actualiza_modelos_existentes_y_preserva_metricas_complementarias(
        self, client_class: MagicMock
    ) -> None:
        client = client_class.return_value
        self.configure_client(client)
        MedicionUsoMensual.objects.create(
            instancia=self.instance,
            anio=2026,
            mes=10,
            usuarios_activos=4,
            cantidad_cursos=1,
            cantidad_categorias=9,
            usuarios_inscritos=16,
            total_matriculas=75,
        )

        call_command(
            "sincronizar_aprovisionamiento",
            month="2026-10",
            stdout=StringIO(),
            stderr=StringIO(),
        )

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.nombre, "Campus Edocere")
        self.assertEqual(self.instance.version, "5.1.1")
        self.assertEqual(self.instance.estado, EstadoInstancia.ACTIVE)
        request = SolicitudAprovisionamiento.objects.get(operation_id="operation-123")
        self.assertEqual(request.instancia, self.instance)
        self.assertEqual(request.estado, EstadoAprovisionamiento.FALLIDA)
        self.assertFalse(
            SolicitudAprovisionamiento.objects.filter(operation_id="backup-456").exists()
        )
        measurement = MedicionUsoMensual.objects.get(
            instancia=self.instance,
            anio=2026,
            mes=10,
        )
        self.assertEqual(measurement.usuarios_activos, 28)
        self.assertEqual(measurement.cantidad_cursos, 2)
        self.assertEqual(measurement.usuarios_inscritos, 16)
        self.assertEqual(measurement.total_matriculas, 75)
        self.assertEqual(measurement.cantidad_categorias, 9)

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_recorrida_paginas_de_tenants_operaciones_y_cursos(
        self, client_class: MagicMock
    ) -> None:
        client = client_class.return_value
        self.configure_client(client)
        client.list_tenants.side_effect = [
            {"items": [self.tenant], "next_cursor": "tenants-next"},
            {"items": [], "next_cursor": None},
        ]
        client.list_operations.side_effect = [
            {"items": [], "next_cursor": "operations-next"},
            {
                "items": [
                    {
                        "operation_id": "operation-paged",
                        "operation_type": "PROVISION",
                        "tenant_slug": "campus",
                        "status": "COMPLETED",
                    }
                ],
                "next_cursor": None,
            },
        ]
        client.list_usage_courses.side_effect = [
            {
                **self.course_metadata,
                "items": [
                    {"course_ref": "course-a", "qualifying_event_count": 1},
                ],
                "next_cursor": "courses-next",
            },
            {
                **self.course_metadata,
                "items": [
                    {"course_ref": "course-b", "qualifying_event_count": 2},
                ],
                "next_cursor": None,
            },
        ]

        call_command(
            "sincronizar_aprovisionamiento",
            month="2026-10",
            stdout=StringIO(),
            stderr=StringIO(),
        )

        self.assertEqual(
            client.list_tenants.call_args_list,
            [
                call(limit=200, cursor=None, owner_ref=None),
                call(limit=200, cursor="tenants-next", owner_ref=None),
            ],
        )
        self.assertEqual(
            client.list_operations.call_args_list,
            [
                call(limit=200, cursor=None, operation_type="PROVISION"),
                call(limit=200, cursor="operations-next", operation_type="PROVISION"),
            ],
        )
        self.assertEqual(
            [call.kwargs["cursor"] for call in client.list_usage_courses.call_args_list],
            [None, "courses-next"],
        )
        self.assertTrue(
            SolicitudAprovisionamiento.objects.filter(operation_id="operation-paged").exists()
        )
        measurement = MedicionUsoMensual.objects.get(instancia=self.instance)
        self.assertEqual(measurement.cantidad_cursos, 2)

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_dry_run_no_escribe_en_la_base_de_datos(self, client_class: MagicMock) -> None:
        client = client_class.return_value
        self.configure_client(client)

        output = StringIO()
        call_command(
            "sincronizar_aprovisionamiento",
            month="2026-10",
            dry_run=True,
            stdout=output,
            stderr=StringIO(),
        )

        self.instance.refresh_from_db()
        self.assertEqual(self.instance.nombre, "Nombre anterior")
        self.assertFalse(SolicitudAprovisionamiento.objects.exists())
        self.assertFalse(MedicionUsoMensual.objects.exists())
        self.assertIn("no se escribió", output.getvalue())

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_uso_no_disponible_no_crea_medicion_con_ceros(self, client_class: MagicMock) -> None:
        client = client_class.return_value
        self.configure_client(client)
        client.list_usage_courses.return_value = None

        call_command(
            "sincronizar_aprovisionamiento",
            month="2026-10",
            solo_uso=True,
            stdout=StringIO(),
            stderr=StringIO(),
        )

        self.assertFalse(MedicionUsoMensual.objects.exists())

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_command_error_ante_error_de_lectura_o_tenants_none(
        self, client_class: MagicMock
    ) -> None:
        client = client_class.return_value
        client.list_tenants.side_effect = TenantctlReadError("servicio no disponible")
        with self.assertRaises(CommandError):
            call_command(
                "sincronizar_aprovisionamiento",
                month="2026-10",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        client.list_tenants.side_effect = None
        client.list_tenants.return_value = None
        with self.assertRaises(CommandError):
            call_command(
                "sincronizar_aprovisionamiento",
                month="2026-10",
                stdout=StringIO(),
                stderr=StringIO(),
            )

    @patch("apps.core.management.commands.sincronizar_aprovisionamiento.TenantctlReadClient")
    def test_command_error_si_operations_no_disponible(self, client_class: MagicMock) -> None:
        client = client_class.return_value
        self.configure_client(client)
        client.list_operations.return_value = None

        with self.assertRaises(CommandError):
            call_command(
                "sincronizar_aprovisionamiento",
                month="2026-10",
                solo_instancias=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )
