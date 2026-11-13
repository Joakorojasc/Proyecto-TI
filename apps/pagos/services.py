from typing import Literal

from .models import Pago

EstadoAccesoInstancia = Literal["aprobada", "pendiente", "rechazada"]


def estado_cliente_para_instancia(
    cliente_id: int,
    suscripcion_id: int | None = None,
    plan_id: int | None = None,
) -> EstadoAccesoInstancia:
    """Contrato interno para que Instancias consulte el acceso de un cliente.

    El estado se determina por el último intento de pago de la suscripción.
    """
    del plan_id
    if suscripcion_id is None:
        return "pendiente"

    pago = (
        Pago.objects.filter(
            suscripcion_id=suscripcion_id,
            suscripcion__cliente_id=cliente_id,
        )
        .order_by("-id")
        .first()
    )
    if pago is None or pago.estado == Pago.ESTADO_PENDIENTE:
        return "pendiente"
    if pago.estado == Pago.ESTADO_APROBADO:
        return "aprobada"
    return "rechazada"
