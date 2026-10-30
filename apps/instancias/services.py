import re
from dataclasses import dataclass
from typing import Protocol

from django.db import transaction

from .models import (
    EstadoAprovisionamiento,
    EstadoInstancia,
    SolicitudAprovisionamiento,
)


@dataclass(frozen=True)
class RespuestaAprovisionamiento:
    status_code: int
    body: dict[str, str]


class ProveedorAprovisionamiento(Protocol):
    def enviar_solicitud(
        self,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> RespuestaAprovisionamiento: ...


class SimuladorAprovisionamientoAPI:
    def enviar_solicitud(
        self,
        payload: dict[str, str],
        idempotency_key: str,
    ) -> RespuestaAprovisionamiento:
        del idempotency_key
        tenant_id = payload["tenant_slug"].removeprefix("tenant-")
        return RespuestaAprovisionamiento(
            status_code=202,
            body={
                "operation_id": f"SIM-{tenant_id}",
                "status": "PENDING",
            },
        )


class AprovisionamientoError(Exception):
    pass


class AprovisionamientoService:
    def __init__(self, proveedor: ProveedorAprovisionamiento | None = None) -> None:
        self.proveedor = proveedor or SimuladorAprovisionamientoAPI()

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

    def construir_payload(self, solicitud: SolicitudAprovisionamiento) -> dict[str, str]:
        instancia = solicitud.instancia
        return {
            "operation_type": "PROVISION",
            "tenant_slug": self.construir_tenant_slug(instancia.pk),
            "hostname": instancia.dominio_host,
            "owner_ref": str(instancia.cliente_id),
        }

    def enviar_solicitud(
        self,
        solicitud: SolicitudAprovisionamiento,
    ) -> RespuestaAprovisionamiento:
        payload = self.construir_payload(solicitud)
        respuesta = self.proveedor.enviar_solicitud(
            payload,
            idempotency_key=str(solicitud.idempotency_key),
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
            instancia.estado = EstadoInstancia.PENDIENTE
            instancia.save(update_fields=["estado"])

        return respuesta
