from decimal import Decimal

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


@pytest.mark.django_db
def test_plan_personalizado_se_crea_por_cliente_sin_suscripcion(client: Client) -> None:
    clientes = [
        Cliente.objects.create(
            rut=f"76.123.456-{digito}",
            razon_social=f"Empresa Demo {digito}",
            giro="Educación",
            direccion_facturacion="Avenida Siempre Viva 123",
            email_contacto="contacto@demo.cl",
        )
        for digito in (1, 2, 3)
    ]

    response = client.get(reverse("seleccionar_plan", kwargs={"cliente_id": clientes[0].id}))
    assert response.status_code == 200
    assert b"Tengo un plan personalizado" in response.content

    for cliente in clientes[:2]:
        response = client.post(
            reverse("seleccionar_plan", kwargs={"cliente_id": cliente.id}),
            {"personalized_plan": "1"},
        )
        assert response.status_code == 302
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == reverse("home")

    planes_cliente = [Plan.objects.get(cliente=cliente) for cliente in clientes[:2]]
    assert [plan.cliente for plan in planes_cliente] == clientes[:2]
    assert planes_cliente[0].pk != planes_cliente[1].pk
    assert not Suscripcion.objects.filter(cliente__in=clientes[:2]).exists()

    planes_cliente[0].precio_base = Decimal("800.00")
    planes_cliente[0].save()
    planes_cliente[1].precio_base = Decimal("400.00")
    planes_cliente[1].save()
    planes_cliente[0].refresh_from_db()
    planes_cliente[1].refresh_from_db()
    assert planes_cliente[0].precio_base == Decimal("800.00")
    assert planes_cliente[1].precio_base == Decimal("400.00")

    response = client.post(
        reverse("seleccionar_plan", kwargs={"cliente_id": clientes[2].id}),
        {"plan": planes_cliente[0].id},
    )
    assert response.status_code == 200
    assert not Suscripcion.objects.filter(cliente=clientes[2]).exists()
    assert not Plan.objects.filter(cliente=clientes[2]).exists()
