from datetime import date
from typing import Any

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.formats import date_format

from apps.estadisticas.models import MedicionUsoMensual
from apps.instancias.models import EstadoInstancia, InstanciaMoodle
from apps.planes.models import Suscripcion


def _variacion(actual: int | None, previo: int | None) -> int | None:
    """Cambio porcentual entre dos períodos, redondeado.

    Devuelve None cuando falta alguno de los dos o cuando el período anterior
    fue cero, porque ahí el porcentaje no significa nada.
    """
    if actual is None or not previo:
        return None
    return round((actual - previo) / previo * 100)


@login_required(login_url="/login/")
def home(request: HttpRequest) -> HttpResponse:
    """Portada del portal: el estado de la cuenta de un vistazo.

    Solo muestra datos del cliente al que pertenece el usuario conectado. Si la
    cuenta no tiene cliente asociado, no se muestra nada en vez de mostrar algo
    de otro.
    """
    usuario_portal = getattr(request.user, "usuarioportal", None)
    cliente = usuario_portal.cliente if usuario_portal is not None else None

    if cliente is None:
        return render(request, "inicio.html", {"cliente": None})

    instancias = InstanciaMoodle.objects.filter(cliente=cliente)
    activas = instancias.filter(estado=EstadoInstancia.ACTIVA)

    contexto: dict[str, Any] = {
        "cliente": cliente,
        "instancias": activas.order_by("nombre", "dominio"),
        "total_activas": activas.count(),
        "total_archivadas": instancias.filter(estado=EstadoInstancia.ARCHIVADA).count(),
        "planes": [
            suscripcion.plan
            for suscripcion in Suscripcion.objects.filter(cliente=cliente).select_related("plan")
        ],
    }

    # El uso se informa del último período medido, no del mes actual, porque el
    # consolidado de Edocere corre de noche y puede ir un mes atrás.
    mediciones = MedicionUsoMensual.objects.filter(instancia__cliente=cliente)
    ultimo = mediciones.order_by("-anio", "-mes").first()
    if ultimo is not None:
        del_periodo = mediciones.filter(anio=ultimo.anio, mes=ultimo.mes)
        totales = del_periodo.aggregate(
            usuarios=Sum("usuarios_activos"),
            cursos=Sum("cantidad_cursos"),
        )
        contexto["periodo_mes"] = ultimo.mes
        contexto["periodo_anio"] = ultimo.anio
        if ultimo.mes and ultimo.anio:
            # "Marzo 2026" se lee mejor que "3/2026" para quien recibe el portal.
            contexto["periodo"] = date_format(date(ultimo.anio, ultimo.mes, 1), "F Y").capitalize()
        contexto["usuarios_activos"] = totales["usuarios"]
        contexto["cursos"] = totales["cursos"]

        # El período anterior permite mostrar la variación. Sale de las mismas
        # mediciones, no hay que calcular ni pedir nada nuevo.
        anterior = (
            mediciones.exclude(anio=ultimo.anio, mes=ultimo.mes).order_by("-anio", "-mes").first()
        )
        if anterior is not None:
            previos = mediciones.filter(anio=anterior.anio, mes=anterior.mes).aggregate(
                usuarios=Sum("usuarios_activos"),
                cursos=Sum("cantidad_cursos"),
            )
            if anterior.mes and anterior.anio:
                contexto["periodo_previo"] = date_format(
                    date(anterior.anio, anterior.mes, 1), "F Y"
                ).capitalize()
            contexto["usuarios_previos"] = previos["usuarios"]
            contexto["cursos_previos"] = previos["cursos"]
            contexto["variacion_usuarios"] = _variacion(totales["usuarios"], previos["usuarios"])

    return render(request, "inicio.html", contexto)


def health(request: HttpRequest) -> JsonResponse:
    """Endpoint de salud.

    Lo consulta el pipeline después de cada despliegue y el monitoreo del
    servidor. Verifica que la aplicación responde y que la base de datos
    está accesible.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        base_datos = "ok"
        estado = 200
    except Exception:
        base_datos = "sin conexion"
        estado = 503

    return JsonResponse(
        {"estado": "ok" if estado == 200 else "degradado", "base_datos": base_datos},
        status=estado,
    )
