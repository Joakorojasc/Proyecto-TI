import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.planes.models import Plan


@pytest.mark.django_db
def test_pestana_suscripciones_muestra_planes_publicos_por_periodicidad(
    client: Client,
) -> None:
    usuario = User.objects.create_user(username="cliente", password="clave-segura")
    client.force_login(usuario)

    Plan.objects.create(
        nombre="Plan mensual básico",
        tipo_plan="Mensual",
        precio_por_usuario=1500,
        limite_usuarios=25,
    )
    Plan.objects.create(
        nombre="Plan anual institucional",
        tipo_plan="Anual",
        precio_base=120000,
        limite_usuarios=100,
    )
    cliente = Cliente.objects.create(rut="76.123.456-7", razon_social="Institución")
    Plan.objects.create(
        nombre="Plan privado",
        tipo_plan="Mensual",
        precio_por_usuario=500,
        cliente=cliente,
    )

    respuesta = client.get(reverse("seccion_suscripciones"))

    assert respuesta.status_code == 200
    assert b"Suscripciones y Planes" in respuesta.content
    assert b"Plan mensual b\xc3\xa1sico" in respuesta.content
    assert b"$1,500.00/usuario/mes" in respuesta.content
    assert b"Hasta 25 usuarios activos" in respuesta.content
    assert b"Plan anual institucional" in respuesta.content
    assert b"$120,000/a\xc3\xb1o" in respuesta.content
    assert b"Hasta 100 usuarios activos" in respuesta.content
    assert b"Plan privado" not in respuesta.content
    assert b"previamente con Edocere" in respuesta.content


@pytest.mark.django_db
def test_pestana_suscripciones_requiere_autenticacion(client: Client) -> None:
    respuesta = client.get(reverse("seccion_suscripciones"))

    assert respuesta.status_code == 302
    assert "/login/" in respuesta.headers.get("Location", "")
