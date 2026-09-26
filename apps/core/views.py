from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Página principal del portal, accesible solo para usuarios autenticados."""
    return render(request, "base.html")


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
