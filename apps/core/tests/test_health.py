import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_health_responde_ok(client: Client) -> None:
    """El endpoint de salud responde 200 cuando la base de datos está viva."""
    respuesta = client.get(reverse("core:health"))

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"


@pytest.mark.django_db
def test_health_reporta_base_de_datos(client: Client) -> None:
    """La respuesta incluye el estado de la base de datos."""
    respuesta = client.get(reverse("core:health"))

    assert respuesta.json()["base_datos"] == "ok"
