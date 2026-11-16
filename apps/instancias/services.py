from django.db import transaction

from .models import EstadoAprovisionamiento, EstadoInstancia, SolicitudAprovisionamiento


class AprovisionamientoError(Exception):
    pass


class AprovisionamientoService:
    def procesar_simulado(
        self,
        solicitud: SolicitudAprovisionamiento,
        fallos: int,
    ) -> bool:
        with transaction.atomic():
            solicitud = (
                SolicitudAprovisionamiento.objects.select_for_update()
                .select_related("instancia")
                .get(pk=solicitud.pk)
            )
            if solicitud.estado != EstadoAprovisionamiento.PENDIENTE:
                return solicitud.estado == EstadoAprovisionamiento.ACTIVA

            solicitud.intentos += 1
            instancia = solicitud.instancia
            if solicitud.intentos <= fallos:
                solicitud.estado = (
                    EstadoAprovisionamiento.FALLIDA
                    if solicitud.intentos >= 3
                    else EstadoAprovisionamiento.PENDIENTE
                )
                if solicitud.estado == EstadoAprovisionamiento.FALLIDA:
                    instancia.estado = EstadoInstancia.FALLIDA
                    instancia.save(update_fields=["estado"])
                solicitud.save(update_fields=["intentos", "estado", "updated_at"])
                return False

            solicitud.estado = EstadoAprovisionamiento.ACTIVA
            solicitud.operation_id = f"SIM-{instancia.pk}-{solicitud.intentos}"
            instancia.estado = EstadoInstancia.ACTIVA
            instancia.save(update_fields=["estado"])
            solicitud.save(update_fields=["intentos", "estado", "operation_id", "updated_at"])
            return True
