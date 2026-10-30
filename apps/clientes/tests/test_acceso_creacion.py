"""Regresión del acceso por cliente_id a planes y creación de instancias."""

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.test import Client
from django.urls import reverse

from apps.clientes.models import Cliente, UsuarioPortal
from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Plan, Suscripcion

pytestmark = pytest.mark.django_db


def solicitud(navegador: Client, operacion: str, metodo: str, cliente: Cliente, plan: Plan) -> int:
    if operacion == "crear":
        url = reverse("instancias:crear", args=[cliente.pk, plan.pk])
        datos = {"nombre": "Campus Prueba", "tipo_dominio": "edocere", "subdominio": "campus"}
    else:
        url = reverse("planes:seleccionar_plan", args=[cliente.pk])
        datos = {"plan": str(plan.pk)}
    respuesta = getattr(navegador, metodo)(url, datos if metodo == "post" else {})
    if respuesta.status_code == 302 and "_auth_user_id" not in navegador.session:
        assert respuesta["Location"] == f"{reverse('login')}?next={url}"
    return respuesta.status_code


@pytest.mark.parametrize("operacion", ["seleccionar", "crear"])
@pytest.mark.parametrize("metodo", ["get", "post"])
@pytest.mark.parametrize(
    "actor",
    [
        "anonimo",
        "ajeno",
        "sin-portal",
        "sin-cliente",
        "staff-sin-portal",
        "staff-sin-cliente",
        "staff-ajeno",
        "rol-superadmin",
        "grupo-y-permisos",
    ],
)
def test_acceso_denegado_no_expone_ni_crea_datos(
    client: Client, usuario_cliente: User, operacion: str, metodo: str, actor: str
) -> None:
    ajena = Cliente.objects.create(rut="76987654-5", razon_social="Institución Ajena")
    plan = Plan.objects.create(nombre="Plan Base", tipo_plan="Mensual")
    if actor in ("ajeno", "staff-ajeno", "rol-superadmin", "grupo-y-permisos"):
        if actor == "staff-ajeno":
            usuario_cliente.is_staff = True
            usuario_cliente.save(update_fields=["is_staff"])
        elif actor == "rol-superadmin":
            perfil = usuario_cliente.usuarioportal
            perfil.rol = "Superadmin"
            perfil.save(update_fields=["rol"])
        elif actor == "grupo-y-permisos":
            usuario_cliente.groups.add(Group.objects.create(name="Superadministradores"))
            usuario_cliente.user_permissions.add(*Permission.objects.all())
        client.force_login(usuario_cliente)
    elif actor != "anonimo":
        usuario = User.objects.create_user(
            username="sin-asociacion", is_staff=actor.startswith("staff-")
        )
        if actor.endswith("sin-cliente"):
            UsuarioPortal.objects.create(usuario=usuario, cliente=None)
        client.force_login(usuario)

    modelos = (Cliente, Plan, InstanciaMoodle, Suscripcion)
    inicial = [list(modelo.objects.order_by("pk").values()) for modelo in modelos]
    estado = solicitud(client, operacion, metodo, ajena, plan)

    assert estado == (302 if actor == "anonimo" else 404)
    assert [list(modelo.objects.order_by("pk").values()) for modelo in modelos] == inicial


@pytest.mark.parametrize("operacion", ["seleccionar", "crear"])
@pytest.mark.parametrize("metodo", ["get", "post"])
@pytest.mark.parametrize(
    "actor", ["propietario", "staff-propietario", "superusuario", "superusuario-asociado"]
)
def test_acceso_permitido_respeta_los_permisos_existentes(
    client: Client, usuario_cliente: User, operacion: str, metodo: str, actor: str
) -> None:
    cliente = usuario_cliente.usuarioportal.cliente
    assert cliente is not None
    if actor.startswith("superusuario"):
        usuario = User.objects.create_user(
            username="administrador",
            is_staff=True,
            is_superuser=True,
        )
        if actor == "superusuario-asociado":
            otra = Cliente.objects.create(rut="76987654-5", razon_social="Otra Institución")
            UsuarioPortal.objects.create(usuario=usuario, cliente=otra)
    else:
        usuario = usuario_cliente
        if actor == "staff-propietario":
            usuario.is_staff = True
            usuario.save(update_fields=["is_staff"])
    client.force_login(usuario)
    plan = Plan.objects.create(nombre="Plan Base", tipo_plan="Mensual")

    assert solicitud(client, operacion, metodo, cliente, plan) == (200 if metodo == "get" else 302)
    if operacion == "crear" and metodo == "post":
        suscripcion_pendiente = Suscripcion.objects.get()
        client.post(
            reverse(
                "pagos:checkout",
                kwargs={"suscripcion_id": suscripcion_pendiente.pk},
            ),
            {
                "ultimos_4_digitos": "4242",
                "marca_tarjeta": "Visa",
                "resultado": "aprobado",
            },
        )
        instancia = InstanciaMoodle.objects.get()
        suscripcion = Suscripcion.objects.get()
        assert instancia.cliente_id == cliente.pk
        assert suscripcion.cliente_id == cliente.pk
        assert suscripcion.instancia_id == instancia.pk
        assert suscripcion.plan_id == plan.pk
    else:
        assert not Plan.objects.filter(cliente=cliente).exists()
        assert not InstanciaMoodle.objects.exists()
        assert not Suscripcion.objects.exists()
