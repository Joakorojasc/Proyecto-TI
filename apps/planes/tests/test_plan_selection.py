import pytest
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.test import Client
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.planes.models import Plan, Suscripcion


@pytest.mark.django_db
def test_registro_redirige_a_mis_instancias(client: Client) -> None:
    data = {
        "username": "admin@demo.cl",
        "password1": "Password123!",
        "password2": "Password123!",
        "razon_social": "Empresa Demo",
        "rut": "76.123.456-7",
    }

    response = client.post(reverse("registro"), data=data)

    assert response.status_code == 302
    assert isinstance(response, HttpResponseRedirect)
    assert response.url == reverse("instancias:lista")
    assert Cliente.objects.filter(razon_social="Empresa Demo").exists()


@pytest.mark.django_db
def test_seleccionar_plan_crea_suscripcion(client: Client) -> None:
    cliente = Cliente.objects.create(
        rut="76.123.456-7",
        razon_social="Empresa Demo",
        giro="Educación",
        direccion_facturacion="Avenida Siempre Viva 123",
        email_contacto="contacto@demo.cl",
    )
    usuario = User.objects.create_user(username="cliente", password="Password123!")
    UsuarioPortal.objects.create(usuario=usuario, cliente=cliente)
    client.force_login(usuario)
    plan = Plan.objects.create(
        nombre="Plan Pro",
        tipo_plan="Mensual",
        precio_base=50000,
        precio_por_usuario=2000,
        limite_usuarios=20,
    )

    response = client.post(
        reverse("planes:seleccionar_plan", kwargs={"cliente_id": cliente.id}),
        {"plan": plan.id},
    )

    assert response.status_code == 302
    assert isinstance(response, HttpResponseRedirect)
    assert response.url == reverse(
        "instancias:crear",
        kwargs={"cliente_id": cliente.id, "plan_id": plan.id},
    )
    assert not Suscripcion.objects.filter(cliente=cliente, plan=plan).exists()


@pytest.mark.django_db
def test_seleccion_plan_muestra_precio_mensual_y_limite_de_usuarios(client: Client) -> None:
    cliente = Cliente.objects.create(
        rut="76.123.456-7",
        razon_social="Empresa Demo",
    )
    usuario = User.objects.create_user(username="cliente", password="Password123!")
    UsuarioPortal.objects.create(usuario=usuario, cliente=cliente)
    client.force_login(usuario)
    Plan.objects.create(
        nombre="Plan Demo",
        tipo_plan="Mensual",
        precio_por_usuario=0,
        limite_usuarios=10,
    )

    response = client.get(reverse("planes:seleccionar_plan", kwargs={"cliente_id": cliente.id}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Plan Demo · USD 0.00/usuario/mes, más IVA" in content
    assert "Hasta 10 usuarios activos" in content


@pytest.mark.django_db
def test_plan_personalizado_requiere_contacto_y_no_se_autocrea(client: Client) -> None:
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

    usuario = User.objects.create_user(username="cliente", password="Password123!")
    UsuarioPortal.objects.create(usuario=usuario, cliente=clientes[0])
    client.force_login(usuario)

    response = client.get(reverse("planes:seleccionar_plan", kwargs={"cliente_id": clientes[0].id}))
    assert response.status_code == 200
    assert b"Contactar para solicitarlo" in response.content
    assert b'href="/planes/contacto/"' in response.content

    response = client.post(
        reverse("planes:seleccionar_plan", kwargs={"cliente_id": clientes[0].id}),
        {"personalized_plan": "1"},
    )
    assert response.status_code == 200
    assert not Plan.objects.filter(cliente=clientes[0]).exists()

    plan_personalizado = Plan.objects.create(
        cliente=clientes[0],
        nombre="Plan especial",
        tipo_plan="personalizado",
    )
    response = client.get(
        reverse("planes:seleccionar_plan", kwargs={"cliente_id": clientes[0].id})
    )
    assert response.status_code == 200
    assert "Plan especial" in response.content.decode()

    response = client.post(
        reverse("planes:seleccionar_plan", kwargs={"cliente_id": clientes[0].id}),
        {"plan": plan_personalizado.id},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == reverse(
        "instancias:crear",
        kwargs={"cliente_id": clientes[0].id, "plan_id": plan_personalizado.id},
    )

    response = client.post(
        reverse("planes:seleccionar_plan", kwargs={"cliente_id": clientes[1].id}),
        {"plan": plan_personalizado.id},
    )
    assert response.status_code == 404
