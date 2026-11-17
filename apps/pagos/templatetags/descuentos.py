from typing import Any

from django import template

from apps.pagos.models import CodigoDescuento
from apps.planes.models import Plan

register = template.Library()


@register.filter
def tiene_codigos(plan: Plan) -> bool:
    """True si el plan tiene al menos un código de descuento activo."""
    return CodigoDescuento.objects.filter(plan=plan, activo=True).exists()


@register.filter
def codigo_ingresado(datos: Any, plan_id: int) -> str:
    """Lo que el cliente escribió como código para ese plan (para no perderlo si hay error)."""
    return str(datos.get(f"codigo_{plan_id}", ""))
