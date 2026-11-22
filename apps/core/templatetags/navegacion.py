"""Tags de la navegación común del portal."""

from typing import Any

from django import template

from apps.core.migas import Eslabon, ruta

register = template.Library()


@register.inclusion_tag("_migas.html", takes_context=True)
def migas(context: Any) -> dict[str, list[Eslabon]]:
    """Dibuja la ruta de la pantalla actual, deducida de la URL.

    base.html lo llama una vez. Lo que se muestra sale de la tabla de
    apps/core/migas.py, así que las plantillas no declaran nada.
    """
    peticion = context.get("request")
    coincidencia = getattr(peticion, "resolver_match", None)
    if coincidencia is None:
        return {"ruta": []}
    return {"ruta": ruta(coincidencia.view_name, coincidencia.kwargs, context)}
