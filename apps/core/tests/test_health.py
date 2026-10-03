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


@pytest.mark.django_db
def test_health_responde_503_si_la_base_no_contesta(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si la base de datos se cae, el endpoint lo reporta y no responde 200.

    Responder cuando todo está bien es lo fácil. Lo que hace útil este endpoint
    es que avise cuando la base no contesta, porque ahí el portal sigue en pie
    pero no puede hacer nada.
    """

    class BaseCaida:
        def cursor(self) -> None:
            raise RuntimeError("la base no responde")

    monkeypatch.setattr("apps.core.views.connection", BaseCaida())

    respuesta = client.get(reverse("core:health"))

    assert respuesta.status_code == 503
    assert respuesta.json()["estado"] == "degradado"
    assert respuesta.json()["base_datos"] == "sin conexion"
