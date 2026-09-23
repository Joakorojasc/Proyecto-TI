import pytest
from django.http import HttpResponseRedirect
from django.test import Client
from django.urls import reverse

from apps.clientes.models import Cliente
from apps.planes.models import Plan, Suscripcion


@pytest.mark.django_db
def test_registro_redirige_a_seleccionar_plan(client: Client) -> None:
    data = {
        "username": "admin_demo",
        "password1": "Password123!",
        "password2": "Password123!",
        "razon_social": "Empresa Demo",
        "rut": "76.123.456-7",
    }

    response = client.post(reverse("registro"), data=data)

    assert response.status_code == 302
    assert isinstance(response, HttpResponseRedirect)

    cliente = Cliente.objects.get(razon_social="Empresa Demo")
    assert response.url == reverse("seleccionar_plan", kwargs={"cliente_id": cliente.id})


@pytest.mark.django_db
def test_seleccionar_plan_crea_suscripcion(client: Client) -> None:
    cliente = Cliente.objects.create(
        rut="76.123.456-7",
        razon_social="Empresa Demo",
        giro="Educación",
        direccion_facturacion="Avenida Siempre Viva 123",
        email_contacto="contacto@demo.cl",
    )
    plan = Plan.objects.create(
        nombre="Plan Pro",
        tipo_plan="Mensual",
        precio_base=50000,
        precio_por_usuario=2000,
        limite_usuarios=20,
    )

    response = client.post(
        reverse("seleccionar_plan", kwargs={"cliente_id": cliente.id}),
        {"plan": plan.id},
    )

    assert response.status_code == 302
    assert isinstance(response, HttpResponseRedirect)
    assert response.url == reverse("home")
    assert Suscripcion.objects.filter(cliente=cliente, plan=plan).count() == 1
