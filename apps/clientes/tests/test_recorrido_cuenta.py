"""Recorridos HTTP que conectan registro, términos, perfil y sesiones reales."""

from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.clientes.models import AceptacionTerminos, Cliente, UsuarioPortal
from apps.clientes.terminos import VERSION_TERMINOS

pytestmark = pytest.mark.django_db

CLAVE = "ClaveSegura123!"


def datos_registro(
    correo: str = "cuenta@recorrido.cl",
    rut: str = "76.123.456-0",
    nombre: str = "Institución Recorrido",
) -> dict[str, str]:
    return {
        "username": correo,
        "password1": CLAVE,
        "password2": CLAVE,
        "razon_social": nombre,
        "rut": rut,
        "acepta_terminos": "on",
        "version_terminos": VERSION_TERMINOS,
    }


def registrar(navegador: Client, datos: dict[str, str]) -> tuple[User, Cliente]:
    respuesta = navegador.post(reverse("registro"), datos)
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("instancias:lista")
    usuario = User.objects.get(username=datos["username"].lower())
    perfil = UsuarioPortal.objects.get(usuario=usuario)
    assert perfil.cliente is not None
    assert int(navegador.session["_auth_user_id"]) == usuario.pk
    aceptacion = AceptacionTerminos.objects.get(cliente=perfil.cliente)
    assert aceptacion.usuario_id == usuario.pk
    assert aceptacion.version_documento == VERSION_TERMINOS
    assert aceptacion.fecha_aceptacion is not None
    return usuario, perfil.cliente


def cerrar_sesion(navegador: Client) -> None:
    respuesta = navegador.post(reverse("logout"))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("login")
    assert "_auth_user_id" not in navegador.session


def iniciar_sesion(navegador: Client, usuario: User) -> None:
    respuesta = navegador.post(reverse("login"), {"username": usuario.username, "password": CLAVE})
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("home")
    assert int(navegador.session["_auth_user_id"]) == usuario.pk


def estado_cuentas() -> dict[str, list[Mapping[str, object]]]:
    """Fotografía de los cuatro modelos; last_login cambia al autenticar."""
    return {
        "usuarios": list(
            User.objects.order_by("pk").values(
                "id", "username", "email", "password", "is_active", "is_staff", "is_superuser"
            )
        ),
        "clientes": list(Cliente.objects.order_by("pk").values()),
        "perfiles": list(UsuarioPortal.objects.order_by("pk").values()),
        "aceptaciones": list(AceptacionTerminos.objects.order_by("pk").values()),
    }


def datos_edicion() -> dict[str, str]:
    return {
        "razon_social": "Institución Actualizada",
        "giro": "Educación",
        "direccion_facturacion": "Calle Nueva 456",
        "email_contacto": "contacto@actualizada.cl",
        "confirmacion_contrasena": CLAVE,
    }


def comprobar_perfil(navegador: Client, cliente: Cliente) -> None:
    respuesta = navegador.get(reverse("seccion_perfil"))
    assert respuesta.status_code == 200
    assert respuesta.context["cliente"].pk == cliente.pk
    for campo in ("razon_social", "giro", "direccion_facturacion", "email_contacto"):
        assert respuesta.context["form"].initial[campo] == getattr(cliente, campo)


def test_recorrido_conserva_identidad_y_aceptacion_entre_sesiones(client: Client) -> None:
    usuario, cliente = registrar(client, datos_registro())
    assert User.objects.count() == Cliente.objects.count() == UsuarioPortal.objects.count() == 1
    assert AceptacionTerminos.objects.count() == 1
    assert usuario.groups.filter(name="Cliente").exists()
    assert cliente.rut == "76123456-0"
    inicial = estado_cuentas()

    cerrar_sesion(client)
    iniciar_sesion(client, usuario)
    comprobar_perfil(client, cliente)
    cambios = datos_edicion()
    respuesta = client.post(reverse("seccion_perfil"), cambios)
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("seccion_perfil")
    cliente.refresh_from_db()
    for campo, valor in cambios.items():
        if campo != "confirmacion_contrasena":
            assert getattr(cliente, campo) == valor
    comprobar_perfil(client, cliente)

    cerrar_sesion(client)
    iniciar_sesion(client, usuario)
    comprobar_perfil(client, cliente)
    final = estado_cuentas()
    assert final["usuarios"] == inicial["usuarios"]
    assert final["perfiles"] == inicial["perfiles"]
    # Incluye la fecha, la versión y el actor originales, no solo el conteo.
    assert final["aceptaciones"] == inicial["aceptaciones"]
    esperado = {
        **inicial["clientes"][0],
        **{k: v for k, v in cambios.items() if k != "confirmacion_contrasena"},
    }
    assert final["clientes"] == [esperado]


@pytest.mark.parametrize(
    ("campo", "valor", "formulario", "error", "existente"),
    [
        ("rut", "76.123.456-1", "empresa_form", "rut", False),
        ("rut", "76.987.654-5", "empresa_form", "rut", True),
        ("rut", "76987654-5", "empresa_form", "rut", True),
        ("username", "correo-invalido", "user_form", "username", False),
        ("username", "EXISTENTE@recorrido.cl", "user_form", "username", True),
        ("password2", "OtraClaveSegura123!", "user_form", "password2", False),
        ("acepta_terminos", None, "empresa_form", "acepta_terminos", False),
        ("acepta_terminos", "false", "empresa_form", "acepta_terminos", False),
        ("version_terminos", "version-antigua", "empresa_form", "version_terminos", False),
        ("version_terminos", None, "empresa_form", "version_terminos", False),
    ],
    ids=[
        "rut-invalido",
        "rut-duplicado-puntos",
        "rut-duplicado-sin-puntos",
        "correo-invalido",
        "correo-duplicado",
        "claves-distintas",
        "sin-aceptacion",
        "aceptacion-falsa",
        "version-antigua",
        "sin-version",
    ],
)
def test_registro_rechazado_no_deja_residuos_y_permite_reintentar(
    client: Client, campo: str, valor: str | None, formulario: str, error: str, existente: bool
) -> None:
    if existente:
        registrar(
            Client(), datos_registro("existente@recorrido.cl", "76.987.654-5", "Otra Institución")
        )
    inicial = estado_cuentas()
    datos = datos_registro()
    if valor is None:
        datos.pop(campo)
    else:
        datos[campo] = valor

    respuesta = client.post(reverse("registro"), datos)
    assert respuesta.status_code == 200
    assert respuesta.context[formulario].errors[error]
    assert "_auth_user_id" not in client.session
    assert estado_cuentas() == inicial

    # El intento fallido no reserva el correo/RUT ni deja evidencia de aceptación.
    usuario, cliente = registrar(client, datos_registro())
    final = estado_cuentas()
    for modelo, filas in inicial.items():
        assert final[modelo][:-1] == filas
        assert len(final[modelo]) == len(filas) + 1
    cerrar_sesion(client)
    iniciar_sesion(client, usuario)
    comprobar_perfil(client, cliente)


def test_edicion_rechazada_conserva_toda_la_cuenta_tras_reingresar(client: Client) -> None:
    usuario, cliente = registrar(client, datos_registro())
    inicial = estado_cuentas()
    respuesta = client.post(
        reverse("seccion_perfil"), {**datos_edicion(), "confirmacion_contrasena": "incorrecta"}
    )
    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors["confirmacion_contrasena"]
    assert estado_cuentas() == inicial
    cerrar_sesion(client)
    iniciar_sesion(client, usuario)
    comprobar_perfil(client, cliente)
    assert estado_cuentas() == inicial


def test_dos_instituciones_no_intercambian_datos_por_get_o_post(client: Client) -> None:
    _, propia = registrar(client, datos_registro())
    otro_navegador = Client()
    otro_usuario, otra = registrar(
        otro_navegador, datos_registro("otra@recorrido.cl", "76.987.654-5", "Institución Ajena")
    )
    inicial = estado_cuentas()
    comprobar_perfil(client, propia)
    comprobar_perfil(otro_navegador, otra)
    respuesta = client.get(reverse("seccion_perfil"), {"cliente_id": otra.pk})
    assert respuesta.context["cliente"].pk == propia.pk
    assert otra.razon_social is not None
    assert otra.email_contacto is not None
    assert otra.razon_social not in respuesta.content.decode()
    assert otra.email_contacto not in respuesta.content.decode()

    respuesta = client.post(
        reverse("seccion_perfil"),
        {
            **datos_edicion(),
            "id": otra.pk,
            "cliente": otra.pk,
            "cliente_id": otra.pk,
            "usuario": otro_usuario.pk,
            "usuario_id": otro_usuario.pk,
            "rut": otra.rut,
            "rol": "Superadmin",
        },
    )
    assert respuesta.status_code == 302
    final = estado_cuentas()
    assert final["usuarios"] == inicial["usuarios"]
    assert final["perfiles"] == inicial["perfiles"]
    assert final["aceptaciones"] == inicial["aceptaciones"]
    assert final["clientes"][1] == inicial["clientes"][1]
    propia.refresh_from_db()
    assert propia.razon_social == datos_edicion()["razon_social"]
    assert propia.rut == inicial["clientes"][0]["rut"]
    comprobar_perfil(client, propia)
    comprobar_perfil(otro_navegador, otra)


@pytest.mark.parametrize("vista", ["seccion_perfil", "aceptar_terminos"])
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_anonimo_no_consulta_ni_modifica_cuentas(client: Client, vista: str, metodo: str) -> None:
    _, otra = registrar(Client(), datos_registro())
    inicial = estado_cuentas()
    datos: dict[str, Any] = {"cliente_id": otra.pk}
    if metodo == "post":
        datos.update(datos_edicion())
    respuesta = getattr(client, metodo)(reverse(vista), datos)
    assert respuesta.status_code == 302
    destino = urlsplit(respuesta["Location"])
    assert destino.path == reverse("login")
    # Django conserva también los parámetros GET dentro de next.
    assert parse_qs(destino.query)["next"] == [respuesta.wsgi_request.get_full_path()]
    assert estado_cuentas() == inicial


@pytest.mark.parametrize("con_perfil", [False, True], ids=["sin-portal", "sin-cliente"])
@pytest.mark.parametrize("vista", ["seccion_perfil", "aceptar_terminos"])
@pytest.mark.parametrize("metodo", ["get", "post"])
def test_cuenta_sin_institucion_no_accede_a_otra(
    client: Client, con_perfil: bool, vista: str, metodo: str
) -> None:
    _, otra = registrar(Client(), datos_registro())
    usuario = User.objects.create_user(username="sin-institucion@recorrido.cl", password=CLAVE)
    if con_perfil:
        UsuarioPortal.objects.create(usuario=usuario, cliente=None)
    iniciar_sesion(client, usuario)
    inicial = estado_cuentas()
    respuesta = getattr(client, metodo)(
        reverse(vista),
        {
            **datos_edicion(),
            "cliente_id": otra.pk,
            "acepta_terminos": "on",
            "version_terminos": VERSION_TERMINOS,
        },
    )
    assert respuesta.status_code == 404
    assert "Tu cuenta no tiene una institución asociada" in respuesta.content.decode()
    assert otra.razon_social is not None
    assert otra.email_contacto is not None
    assert otra.razon_social not in respuesta.content.decode()
    assert otra.email_contacto not in respuesta.content.decode()
    assert estado_cuentas() == inicial
