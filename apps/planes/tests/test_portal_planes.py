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
    cliente = Cliente.objects.create(rut="76123456-0", razon_social="Institución")
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
    assert b"USD 1,500.00/usuario/mes, m\xc3\xa1s IVA" in respuesta.content
    assert b"Hasta 25 usuarios activos" in respuesta.content
    assert (
        b"Los primeros 10 usuarios son gratuitos. A partir del usuario 11, "
        b"se cobrar\xc3\xa1 USD 1,50 por la totalidad de los usuarios activos." in respuesta.content
    )
    assert b"Plan anual institucional" in respuesta.content
    assert b"USD 120,000.00/a\xc3\xb1o, m\xc3\xa1s IVA" in respuesta.content
    assert b"Hasta 100 usuarios activos" in respuesta.content
    assert b"Plan privado" not in respuesta.content
    assert b"previamente con Edocere" in respuesta.content
    assert b'href="/planes/contacto/"' in respuesta.content
    assert b"Contactar para solicitarlo" in respuesta.content


@pytest.mark.django_db
def test_pestana_suscripciones_requiere_autenticacion(client: Client) -> None:
    respuesta = client.get(reverse("seccion_suscripciones"))

    assert respuesta.status_code == 302
    assert "/login/" in respuesta.headers.get("Location", "")


@pytest.mark.django_db
def test_contacto_plan_personalizado_muestra_y_procesa_formulario(client: Client) -> None:
    usuario = User.objects.create(username="contacto", email="contacto@demo.cl")
    client.force_login(usuario)

    respuesta = client.get(reverse("planes:contacto_plan_personalizado"))

    assert respuesta.status_code == 200
    assert b"Solicitar un plan personalizado" in respuesta.content
    assert b"Enviar solicitud" in respuesta.content

    respuesta = client.post(
        reverse("planes:contacto_plan_personalizado"),
        {
            "nombre": "Institución Demo",
            "correo": "contacto@demo.cl",
            "mensaje": "Necesitamos un plan para más de 3.000 usuarios.",
        },
    )

    assert respuesta.status_code == 200
    assert b"Recibimos tu solicitud" in respuesta.content
