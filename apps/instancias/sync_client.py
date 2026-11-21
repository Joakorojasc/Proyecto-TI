"""Cliente HTTP de solo lectura para los endpoints v1 de tenantctl."""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]


class TenantctlReadError(Exception):
    """Error de configuración, transporte o respuesta de la API tenantctl."""


class TenantctlReadClient:
    """Cliente HTTP pequeño configurado mediante variables de entorno."""

    timeout_seconds = 30
    max_page_size = 200

    def __init__(self) -> None:
        base_url = os.environ.get("TENANTCTL_API_BASE_URL", "").strip()
        self._service_token = os.environ.get("TENANTCTL_SERVICE_TOKEN", "").strip()
        self._actor_assertion = os.environ.get("TENANTCTL_ACTOR_ASSERTION", "").strip()

        try:
            parsed_url = urlsplit(base_url)
            hostname = parsed_url.hostname
            _ = parsed_url.port
        except ValueError as error:
            raise TenantctlReadError(
                "TENANTCTL_API_BASE_URL debe ser el origen HTTP(S) válido de tenantctl."
            ) from error

        if (
            not base_url
            or parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or not hostname
            or any(character.isspace() for character in hostname)
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise TenantctlReadError(
                "TENANTCTL_API_BASE_URL debe ser el origen HTTP(S) de tenantctl, sin ruta."
            )
        if parsed_url.scheme == "http" and hostname.lower() not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise TenantctlReadError("TENANTCTL_API_BASE_URL debe usar HTTPS para hosts remotos.")
        if not self._service_token:
            raise TenantctlReadError("Configura TENANTCTL_SERVICE_TOKEN.")

        self._base_url = base_url.rstrip("/")

    def _get(
        self,
        path: str,
        params: dict[str, str | int | None] | None = None,
        *,
        usage_endpoint: bool = False,
    ) -> JsonObject | None:
        query = urlencode(
            {key: value for key, value in (params or {}).items() if value is not None}
        )
        url = f"{self._base_url}/api/v1{path}"
        if query:
            url = f"{url}?{query}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._service_token}",
        }
        # PUNTO DE INTEGRACIÓN EDOCERE: enviar assertion solo en contexto de actor humano.
        if self._actor_assertion:
            headers["X-Panel-Actor-Assertion"] = self._actor_assertion
        request = Request(url, headers=headers, method="GET")

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as error:
            error_body: JsonObject = {}
            try:
                decoded_error = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                decoded_error = None
            if isinstance(decoded_error, dict):
                error_body = decoded_error
            if error.code == 404:
                return None
            if (
                usage_endpoint
                and error.code == 409
                and error_body.get("error") == "USAGE_DATA_UNAVAILABLE"
            ):
                return None
            raise TenantctlReadError(
                f"GET {path} respondió HTTP {error.code}: "
                f"{error_body.get('message', 'error sin detalle')}."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise TenantctlReadError(f"No se pudo consultar tenantctl: {error}.") from error

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TenantctlReadError(f"GET {path} no devolvió JSON válido.") from error
        if not isinstance(payload, dict):
            raise TenantctlReadError(f"GET {path} no devolvió un objeto JSON.")
        return payload

    @classmethod
    def _page_params(cls, limit: int, cursor: str | None) -> dict[str, str | int | None]:
        if type(limit) is not int or not 1 <= limit <= cls.max_page_size:
            raise TenantctlReadError(f"limit debe estar entre 1 y {cls.max_page_size}.")
        if cursor is not None and (not cursor or len(cursor) > 512):
            raise TenantctlReadError("El cursor no cumple el formato permitido.")
        return {"limit": limit, "cursor": cursor}

    def list_tenants(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        owner_ref: str | None = None,
    ) -> JsonObject | None:
        params = self._page_params(limit, cursor)
        params["owner_ref"] = owner_ref
        return self._get("/tenants", params)

    def get_tenant(self, tenant_slug: str) -> JsonObject | None:
        slug = quote(tenant_slug, safe="")
        return self._get(f"/tenants/{slug}")

    def list_operations(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        operation_type: str | None = None,
    ) -> JsonObject | None:
        params = self._page_params(limit, cursor)
        if operation_type is not None:
            params["operation_type"] = operation_type
        return self._get("/operations", params)

    def get_monthly_usage(self, tenant_slug: str, month: str) -> JsonObject | None:
        slug = quote(tenant_slug, safe="")
        return self._get(
            f"/tenants/{slug}/usage",
            {"month": month},
            usage_endpoint=True,
        )

    def list_usage_courses(
        self,
        tenant_slug: str,
        month: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> JsonObject | None:
        slug = quote(tenant_slug, safe="")
        params = self._page_params(limit, cursor)
        params["month"] = month
        return self._get(
            f"/tenants/{slug}/usage/courses",
            params,
            usage_endpoint=True,
        )
