import re
import secrets
from dataclasses import dataclass
from typing import Protocol

from django.db import transaction

from apps.clientes.models import UsuarioPortal

from .models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    SolicitudAprovisionamiento,
)

OPERATIONS_URL = "/api/v1/operations"
ACTOR_ASSERTION_HEADER = "X-Panel-Actor-Assertion"
SIMULATED_ACTOR_ASSERTION = "jwt-simulado-eddsa"


@dataclass(frozen=True)
class RespuestaAprovisionamiento:
    status_code: int
    body: dict[str, str]


class ProveedorAprovisionamiento(Protocol):
    def enviar_solicitud(
        self,
        payload: dict[str, object],
        idempotency_key: str,
        *,
        url: str,
        headers: dict[str, str],
    ) -> RespuestaAprovisionamiento: ...


class SimuladorAprovisionamientoAPI:
    def __init__(self) -> None:
        self.respuestas_por_clave: dict[str, RespuestaAprovisionamiento] = {}

    def enviar_solicitud(
        self,
        payload: dict[str, object],
        idempotency_key: str,
        *,
        url: str,
        headers: dict[str, str],
    ) -> RespuestaAprovisionamiento:
        del url, headers
        if idempotency_key in self.respuestas_por_clave:
            return self.respuestas_por_clave[idempotency_key]

        tenant_slug = payload["tenant_slug"]
        if not isinstance(tenant_slug, str):
            raise AprovisionamientoError("El tenant_slug debe ser una cadena.")
        tenant_id = tenant_slug.removeprefix("tenant-")
        respuesta = RespuestaAprovisionamiento(
            status_code=202,
            body={
                "operation_id": f"SIM-{tenant_id}",
                "status": "PENDING",
            },
        )
        self.respuestas_por_clave[idempotency_key] = respuesta
        return respuesta


class AprovisionamientoError(Exception):
    pass


class AprovisionamientoService:
    def __init__(self, proveedor: ProveedorAprovisionamiento | None = None) -> None:
        self.proveedor = proveedor if proveedor is not None else _SIMULADOR_APROVISIONAMIENTO

    @staticmethod
    def construir_tenant_slug(instancia_id: int) -> str:
        tenant_slug = f"tenant-{instancia_id}"
        if len(tenant_slug) > 63 or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*",
            tenant_slug,
        ):
            raise AprovisionamientoError(
                "El tenant_slug no cumple el contrato de aprovisionamiento."
            )
        return tenant_slug

    def construir_payload(self, solicitud: SolicitudAprovisionamiento) -> dict[str, object]:
        instancia = solicitud.instancia
        perfil = (
            UsuarioPortal.objects.filter(cliente_id=instancia.cliente_id, usuario__isnull=False)
            .select_related("usuario")
            .order_by("pk")
            .first()
        )
        if perfil is None or perfil.usuario is None:
            raise AprovisionamientoError(
                "La institución necesita un usuario de portal para aprovisionar al gestor."
            )

        usuario = perfil.usuario
        nombre_perfil = (perfil.nombre or "").split(maxsplit=1)
        firstname = usuario.first_name.strip() or (nombre_perfil[0] if nombre_perfil else "")
        lastname = usuario.last_name.strip() or (nombre_perfil[1] if len(nombre_perfil) > 1 else "")
        email = perfil.email or usuario.email or instancia.cliente.email_contacto or ""
        username = usuario.username.strip().lower()
        if not username or not firstname or not lastname or not email:
            raise AprovisionamientoError(
                "El usuario de portal debe tener username, nombre, apellido y correo "
                "para aprovisionar al gestor."
            )

        return {
            "operation_type": "PROVISION",
            "tenant_slug": self.construir_tenant_slug(instancia.pk),
            "hostname": instancia.dominio_host,
            "owner_ref": str(instancia.cliente_id),
            "language": "es",
            "manager": {
                "username": username,
                "firstname": firstname,
                "lastname": lastname,
                "email": email,
                "password": secrets.token_urlsafe(32),
            },
        }

    def enviar_solicitud(
        self,
        solicitud: SolicitudAprovisionamiento,
    ) -> RespuestaAprovisionamiento:
        payload = self.construir_payload(solicitud)
        respuesta = self.proveedor.enviar_solicitud(
            payload,
            idempotency_key=str(solicitud.idempotency_key),
            url=OPERATIONS_URL,
            headers={ACTOR_ASSERTION_HEADER: SIMULATED_ACTOR_ASSERTION},
        )
        if respuesta.status_code != 202:
            raise AprovisionamientoError(
                f"El proveedor respondió con HTTP {respuesta.status_code}; se esperaba 202."
            )

        operation_id = respuesta.body.get("operation_id")
        estado = respuesta.body.get("status")
        if not operation_id or estado != "PENDING":
            raise AprovisionamientoError(
                "La respuesta de aceptación debe incluir operation_id y estado PENDING."
            )

        with transaction.atomic():
            solicitud.operation_id = operation_id
            solicitud.estado = EstadoAprovisionamiento.PENDIENTE
            solicitud.save(update_fields=["operation_id", "estado", "updated_at"])

            instancia = solicitud.instancia
            instancia.estado = EstadoInstancia.PENDING
            instancia.save(update_fields=["estado"])

        return respuesta


_SIMULADOR_APROVISIONAMIENTO = SimuladorAprovisionamientoAPI()
