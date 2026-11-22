"""Ayudas compartidas por los tests que pasan por la aceptación de términos."""

from django.test import Client
from django.urls import reverse

from apps.clientes import terminos


def abrir_documento_terminos(client: Client) -> None:
    """Pide el PDF, que es lo que deja en la sesión la marca de documento leído.

    El formulario de registro y el de aceptación la exigen, así que los tests
    que llegan a enviarlos tienen que pasar antes por acá.
    """
    client.get(reverse("documento_terminos", kwargs={"version": terminos.VERSION_TERMINOS}))
