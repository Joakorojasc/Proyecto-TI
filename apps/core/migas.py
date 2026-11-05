"""Migas de pan del portal.

La ruta de cada pantalla se deduce de su URL. Acá está la única tabla que hay
que editar: cada nombre de URL dice su título y de qué paso cuelga. Las
plantillas no declaran nada.

Una URL con nombre que no esté en RUTAS ni en SIN_MIGAS hace fallar
apps/core/tests/test_migas.py. Para que una pantalla quede sin migas hay que
declararlo a mano.
"""

from dataclasses import dataclass
from typing import Any

from django.urls import NoReverseMatch, reverse


@dataclass(frozen=True)
class Paso:
    """Un eslabón de la ruta, tal como se declara en la tabla.

    titulo: el texto fijo.
    padre: nombre de la URL del paso anterior. None cuelga directo de Inicio.
    argumentos: los parámetros que pide el patrón de esta URL. Sirven para
        construir el enlace cuando este paso aparece como antecesor de otro.
    titulo_desde: variable del contexto que manda el texto, para las pantallas
        cuyo título depende del objeto que muestran.
    """

    titulo: str
    padre: str | None = None
    argumentos: tuple[str, ...] = ()
    titulo_desde: str | None = None


@dataclass(frozen=True)
class Eslabon:
    """Un paso ya resuelto, listo para dibujar. url en None es la página actual."""

    titulo: str
    url: str | None


TITULO_INICIO = "Inicio"

RUTAS: dict[str, Paso] = {
    "seccion_perfil": Paso("Perfil de Institución"),
    "aceptar_terminos": Paso("Términos y condiciones", padre="seccion_perfil"),
    "instancias:lista": Paso("Mis Instancias"),
    "instancias:detalle": Paso(
        "Instancia",
        padre="instancias:lista",
        argumentos=("pk",),
        titulo_desde="instancia",
    ),
    "instancias:editar": Paso("Editar", padre="instancias:detalle", argumentos=("pk",)),
    # A seleccionar plan se entra por el botón "Crear instancia" de la portada y
    # del listado, así que cuelga de Mis Instancias.
    "planes:seleccionar_plan": Paso(
        "Seleccionar plan", padre="instancias:lista", argumentos=("cliente_id",)
    ),
    "instancias:crear": Paso(
        "Configurar instancia",
        padre="planes:seleccionar_plan",
        argumentos=("cliente_id", "plan_id"),
    ),
    "seccion_suscripciones": Paso("Suscripciones y Planes"),
    "planes:contacto_plan_personalizado": Paso("Plan personalizado", padre="seccion_suscripciones"),
    "seccion_facturacion": Paso("Facturación y Pagos"),
    "pagos:checkout": Paso(
        "Pago de suscripción", padre="seccion_facturacion", argumentos=("suscripcion_id",)
    ),
    "seccion_estadisticas": Paso("Estadísticas"),
}

SIN_MIGAS = frozenset(
    {
        "home",  # es la raíz, no hay nada por encima a lo que volver
        "login",
        "logout",
        "registro",
        "registro_cliente",
        "documento_terminos",  # devuelve un PDF, no una pantalla del portal
        "health",
        "core:home",
        "core:health",
    }
)


def _titulo(paso: Paso, contexto: Any) -> str:
    """El texto del paso. Si depende del contexto y no está, usa el fijo."""
    if paso.titulo_desde is None:
        return paso.titulo
    try:
        objeto = contexto[paso.titulo_desde]
    except (KeyError, TypeError):
        return paso.titulo
    return str(objeto) if objeto else paso.titulo


def _enlace(nombre: str, paso: Paso, parametros: dict[str, Any]) -> str | None:
    """El href del antecesor, armado con los parámetros de la URL actual.

    Devuelve None si no se puede construir, para dibujar el paso sin enlace en
    vez de tirar un error 500.
    """
    try:
        return reverse(nombre, kwargs={clave: parametros[clave] for clave in paso.argumentos})
    except (KeyError, NoReverseMatch):
        return None


def ruta(nombre_vista: str, parametros: dict[str, Any], contexto: Any) -> list[Eslabon]:
    """La ruta de la pantalla actual, desde Inicio hasta ella.

    Devuelve lista vacía para las pantallas sin migas. El último eslabón va sin
    url porque es la página en la que está el usuario.
    """
    if nombre_vista not in RUTAS:
        return []

    cadena: list[tuple[str, Paso]] = []
    nombre: str | None = nombre_vista
    vistos: set[str] = set()
    while nombre is not None and nombre in RUTAS and nombre not in vistos:
        vistos.add(nombre)
        cadena.append((nombre, RUTAS[nombre]))
        nombre = RUTAS[nombre].padre
    cadena.reverse()

    resultado = [Eslabon(TITULO_INICIO, reverse("home"))]
    ultimo = len(cadena) - 1
    for posicion, (nombre_paso, paso) in enumerate(cadena):
        resultado.append(
            Eslabon(
                titulo=_titulo(paso, contexto),
                url=None if posicion == ultimo else _enlace(nombre_paso, paso, parametros),
            )
        )
    return resultado
