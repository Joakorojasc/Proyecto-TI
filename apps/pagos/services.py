from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from django.http import HttpRequest

from apps.planes.models import Plan

from .models import CodigoDescuento, Pago

EstadoAccesoInstancia = Literal["aprobada", "pendiente", "rechazada"]

CENTAVOS = Decimal("0.01")
CLAVE_SESION_CODIGO = "codigo_descuento"


@dataclass(frozen=True)
class PrecioConDescuento:
    precio_original: Decimal
    descuento: Decimal
    precio_final: Decimal
    codigo: CodigoDescuento | None


def precio_de_referencia(plan: Plan) -> Decimal:
    """Precio del plan sobre el que se aplica el descuento.

    Mensual: precio por usuario al mes. Anual y otros: precio base.
    """
    if (plan.tipo_plan or "").lower() == "mensual":
        return plan.precio_por_usuario or Decimal("0.00")
    return plan.precio_base or Decimal("0.00")


def buscar_codigo(texto: str | None, plan: Plan) -> CodigoDescuento | None:
    """Devuelve el código activo de ese plan que corresponde al texto, o None."""
    normalizado = (texto or "").strip().upper()
    if not normalizado:
        return None
    return CodigoDescuento.objects.filter(codigo=normalizado, activo=True, plan=plan).first()


def recordar_codigo(request: HttpRequest, plan: Plan, codigo: CodigoDescuento) -> None:
    """Guarda en la sesión el código elegido, para usarlo al crear la suscripción."""
    request.session[CLAVE_SESION_CODIGO] = {"plan_id": plan.pk, "codigo": codigo.codigo}


def olvidar_codigo(request: HttpRequest) -> None:
    request.session.pop(CLAVE_SESION_CODIGO, None)


def codigo_recordado(request: HttpRequest, plan: Plan) -> CodigoDescuento | None:
    """El código guardado en la sesión, solo si sigue siendo válido para ese plan."""
    guardado = request.session.get(CLAVE_SESION_CODIGO)
    if not isinstance(guardado, dict) or guardado.get("plan_id") != plan.pk:
        return None
    return buscar_codigo(guardado.get("codigo"), plan)


def aplicar_descuento(precio: Decimal, codigo: CodigoDescuento | None) -> PrecioConDescuento:
    if codigo is None:
        return PrecioConDescuento(precio, Decimal("0.00"), precio, None)
    descuento = (precio * codigo.porcentaje / Decimal(100)).quantize(CENTAVOS, ROUND_HALF_UP)
    return PrecioConDescuento(precio, descuento, precio - descuento, codigo)


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
