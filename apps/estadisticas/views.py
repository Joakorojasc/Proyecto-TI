"""Estadísticas de uso del cliente conectado."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.formats import date_format

from apps.clientes.permisos import obtener_cliente_propio
from apps.instancias.models import InstanciaMoodle

from .models import MedicionUsoMensual


@dataclass(frozen=True)
class Metricas:
    """Los números de un período. None significa que no hay dato."""

    periodo: str = ""
    usuarios_activos: int | None = None
    cantidad_cursos: int | None = None
    cantidad_categorias: int | None = None


@dataclass(frozen=True)
class FilaInstancia:
    """Una instancia con sus números del período informado y su historial."""

    instancia: InstanciaMoodle
    del_periodo: Metricas
    con_datos: bool
    historial: list[Metricas]


def _nombre_periodo(anio: int | None, mes: int | None) -> str:
    """El período en palabras, como "Marzo 2026". Un mes inválido se muestra tal cual."""
    if anio is None or mes is None:
        return "Sin período"
    try:
        return date_format(date(anio, mes, 1), "F Y").capitalize()
    except ValueError:
        return f"{mes}/{anio}"


def _metricas(medicion: MedicionUsoMensual) -> Metricas:
    return Metricas(
        periodo=_nombre_periodo(medicion.anio, medicion.mes),
        usuarios_activos=medicion.usuarios_activos,
        cantidad_cursos=medicion.cantidad_cursos,
        cantidad_categorias=medicion.cantidad_categorias,
    )


def _suma(valores: Iterable[int | None]) -> int | None:
    """Suma lo que haya. Si no hay ningún dato devuelve None, para no informar un cero falso."""
    presentes = [valor for valor in valores if valor is not None]
    return sum(presentes) if presentes else None


@login_required(login_url="/login/")
def estadisticas(request: HttpRequest) -> HttpResponse:
    """Uso de las instancias del cliente de la sesión.

    El cliente sale siempre de la sesión y nunca de la URL, para que nadie pueda
    pedir los datos de otro.
    """
    cliente = obtener_cliente_propio(request)
    if cliente is None:
        return render(request, "estadisticas.html", {"cliente": None})

    instancias = InstanciaMoodle.objects.filter(cliente=cliente).order_by("nombre", "dominio")
    # Una medición sin período no se puede ubicar en el tiempo, así que no se informa.
    mediciones = list(
        MedicionUsoMensual.objects.filter(
            instancia__cliente=cliente, anio__isnull=False, mes__isnull=False
        ).order_by("-anio", "-mes", "-pk")
    )

    por_instancia: defaultdict[int, list[MedicionUsoMensual]] = defaultdict(list)
    for medicion in mediciones:
        por_instancia[medicion.instancia_id].append(medicion)

    # Se informa el último período medido y no el mes actual, porque el consolidado
    # de Edocere corre de noche y puede ir un mes atrás.
    ultimo = (mediciones[0].anio, mediciones[0].mes) if mediciones else None

    filas = []
    for instancia in instancias:
        propias = por_instancia[instancia.pk]
        midio = bool(propias) and (propias[0].anio, propias[0].mes) == ultimo
        filas.append(
            FilaInstancia(
                instancia=instancia,
                del_periodo=_metricas(propias[0]) if midio else Metricas(),
                con_datos=midio,
                historial=[_metricas(medicion) for medicion in propias],
            )
        )

    contexto = {"cliente": cliente, "filas": filas}
    if ultimo is not None:
        contexto["resumen"] = Metricas(
            periodo=_nombre_periodo(*ultimo),
            usuarios_activos=_suma(fila.del_periodo.usuarios_activos for fila in filas),
            cantidad_cursos=_suma(fila.del_periodo.cantidad_cursos for fila in filas),
            cantidad_categorias=_suma(fila.del_periodo.cantidad_categorias for fila in filas),
        )
        contexto["con_datos"] = sum(fila.con_datos for fila in filas)
        contexto["sin_datos"] = sum(not fila.con_datos for fila in filas)
    return render(request, "estadisticas.html", contexto)
