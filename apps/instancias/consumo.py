from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from django.db.models import F, Prefetch, Q, QuerySet
from django.utils.formats import date_format

from apps.estadisticas.models import MedicionUsoMensual
from apps.planes.models import Suscripcion

if TYPE_CHECKING:
    from .models import InstanciaMoodle


@dataclass(frozen=True)
class ConsumoUsuarios:
    activos: int | None
    periodo: str | None
    limite: int | None
    mensaje_plan: str
    porcentaje: float | None = None
    disponibles: int | None = None
    estado: str = ""
    etiqueta: str = ""

    @property
    def valor_barra(self) -> int | None:
        if self.activos is None or self.limite is None:
            return None
        return min(self.activos, self.limite)


def con_datos_consumo(queryset: QuerySet["InstanciaMoodle"]) -> QuerySet["InstanciaMoodle"]:
    suscripciones = Suscripcion.objects.filter(
        Q(plan__cliente__isnull=True) | Q(plan__cliente_id=F("instancia__cliente_id")),
        estado="activa",
        cliente_id=F("instancia__cliente_id"),
    ).select_related("plan")
    mediciones = MedicionUsoMensual.objects.filter(anio__range=(1, 9999), mes__range=(1, 12))
    return queryset.prefetch_related(
        Prefetch("suscripciones", queryset=suscripciones, to_attr="suscripciones_activas"),
        Prefetch(
            "medicionusomensual_set",
            queryset=mediciones.order_by("-anio", "-mes", "-pk")[:1],
            to_attr="mediciones_consumo",
        ),
    )


def calcular_consumo(
    medicion: MedicionUsoMensual | None, suscripciones: list[Suscripcion]
) -> ConsumoUsuarios:
    activos = medicion.usuarios_activos if medicion else None
    if activos is not None and activos < 0:
        activos = None
    periodo = (
        date_format(date(medicion.anio, medicion.mes, 1), "F Y")
        if medicion
        and medicion.anio
        and 1 <= medicion.anio <= 9999
        and medicion.mes
        and 1 <= medicion.mes <= 12
        else None
    )

    if not suscripciones:
        return ConsumoUsuarios(activos, periodo, None, "Sin suscripción activa")
    if len(suscripciones) > 1:
        return ConsumoUsuarios(activos, periodo, None, "Múltiples planes activos")

    plan = suscripciones[0].plan
    limite = plan.limite_usuarios
    # El plan mensual gratuito de la demo guarda su tramo de facturación en este campo.
    tramo_gratuito = (plan.tipo_plan or "").lower() == "mensual" and limite == 10
    if limite is None or limite <= 0 or tramo_gratuito:
        return ConsumoUsuarios(activos, periodo, None, "Sin límite de capacidad definido")
    if activos is None:
        return ConsumoUsuarios(activos, periodo, limite, "")

    # Truncar a un decimal evita mostrar 80 % o 100 % antes de alcanzar el umbral.
    porcentaje = (activos * 1000 // limite) / 10
    if porcentaje >= 100:
        estado = "limite"
        etiqueta = "Límite alcanzado" if activos == limite else "Límite superado"
    elif porcentaje >= 80:
        estado, etiqueta = "advertencia", "Cerca del límite"
    else:
        estado, etiqueta = "normal", "Dentro del límite"
    return ConsumoUsuarios(
        activos, periodo, limite, "", porcentaje, max(limite - activos, 0), estado, etiqueta
    )
