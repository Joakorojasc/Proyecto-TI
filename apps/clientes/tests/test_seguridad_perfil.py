from html.parser import HTMLParser

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from apps.clientes.models import AceptacionTerminos, Cliente, UsuarioPortal
from apps.clientes.terminos import VERSION_TERMINOS, registrar_aceptacion
from apps.instancias.models import InstanciaMoodle

pytestmark = pytest.mark.django_db
CLAVE = "ClaveSegura123!"


@pytest.fixture
def cuenta() -> tuple[User, Cliente]:
    usuario = User.objects.create_user(username="cuenta@seguridad.cl", password=CLAVE)
    cliente = Cliente.objects.create(
        rut="76123456-0",
        razon_social="Institución Original",
        giro="Original",
        direccion_facturacion="Dirección Original",
        email_contacto="empresa@original.cl",
    )
    UsuarioPortal.objects.create(
        usuario=usuario,
        cliente=cliente,
        nombre="Nombre Histórico",
        email=usuario.username,
        rol="Admin",
    )
    registrar_aceptacion(cliente, usuario, VERSION_TERMINOS)
    return usuario, cliente


def datos_edicion() -> dict[str, str]:
    return {
        "razon_social": "Institución Actualizada",
        "giro": "Educación",
        "direccion_facturacion": "Dirección Actualizada",
        "email_contacto": "empresa@nueva.cl",
        "confirmacion_contrasena": CLAVE,
    }


@pytest.mark.parametrize(
    "actor",
    [
        "normal",
        "staff",
        "staff-sin-portal",
        "staff-sin-cliente",
        "rol",
        "permisos",
        "superusuario",
        "superusuario-sin-portal",
    ],
)
@pytest.mark.parametrize("operacion", ["lista", "detalle", "editar-get", "editar-post"])
def test_instancias_aplican_el_mismo_limite_de_acceso_que_creacion(
    client: Client, cuenta: tuple[User, Cliente], actor: str, operacion: str
) -> None:
    usuario, propia = cuenta
    ajena = Cliente.objects.create(rut="76987654-5", razon_social="Institución Ajena")
    instancia_propia = InstanciaMoodle.objects.create(
        cliente=propia, nombre="Propia", dominio="https://propia.example.cl"
    )
    instancia_ajena = InstanciaMoodle.objects.create(
        cliente=ajena, nombre="Ajena", dominio="https://ajena.example.cl"
    )
    if actor.startswith("staff"):
        usuario.is_staff = True
    if actor.startswith("superusuario"):
        usuario.is_staff = True
        usuario.is_superuser = True
    usuario.save()
    if actor.endswith("sin-portal"):
        # La aceptación histórica permanece vinculada a User y Cliente.
        usuario.usuarioportal.delete()
    elif actor == "staff-sin-cliente":
        perfil = usuario.usuarioportal
        perfil.cliente = None
        perfil.save()
    elif actor == "rol":
        perfil = usuario.usuarioportal
        perfil.rol = "Superadmin"
        perfil.save()
    elif actor == "permisos":
        usuario.groups.add(Group.objects.create(name="Superadministradores"))
        usuario.user_permissions.add(*Permission.objects.all())
    client.force_login(usuario)
    global_permitido = actor.startswith("superusuario")

    if operacion == "lista":
        respuesta = client.get(reverse("instancias:lista"))
        assert respuesta.status_code == 200
        visibles = {instancia.pk for instancia in respuesta.context["instancias"]}
        if global_permitido:
            assert visibles == {instancia_propia.pk, instancia_ajena.pk}
        elif actor in ("staff-sin-portal", "staff-sin-cliente"):
            assert visibles == set()
        else:
            assert visibles == {instancia_propia.pk}
    else:
        url = reverse(
            "instancias:detalle" if operacion == "detalle" else "instancias:editar",
            args=[instancia_ajena.pk],
        )
        if operacion == "editar-post":
            respuesta = client.post(
                url,
                {
                    "nombre": "Actualizada",
                    "logo_url": "",
                    "estado": "pendiente",
                    "confirmacion_contrasena": CLAVE,
                },
            )
        else:
            respuesta = client.get(url)
        esperado = (302 if operacion == "editar-post" else 200) if global_permitido else 404
        assert respuesta.status_code == esperado
        instancia_ajena.refresh_from_db()
        assert instancia_ajena.nombre == (
            "Actualizada" if global_permitido and operacion == "editar-post" else "Ajena"
        )
    instancia_propia.refresh_from_db()
    assert instancia_propia.nombre == "Propia"


@pytest.mark.parametrize("fallo", ["correo", "contrasena", "vacio"])
def test_error_conserva_datos_enviados_y_no_modifica_la_cuenta(
    client: Client, cuenta: tuple[User, Cliente], fallo: str
) -> None:
    usuario, cliente = cuenta
    client.force_login(usuario)
    inicial = Cliente.objects.values().get(pk=cliente.pk)
    perfil_inicial = UsuarioPortal.objects.values().get(usuario=usuario)
    aceptacion_inicial = AceptacionTerminos.objects.values().get(cliente=cliente)
    datos = datos_edicion()
    if fallo == "correo":
        datos["email_contacto"] = "correo-invalido"
        campo_error = "email_contacto"
    elif fallo == "contrasena":
        datos["confirmacion_contrasena"] = "incorrecta"
        campo_error = "confirmacion_contrasena"
    else:
        datos = {}
        campo_error = "confirmacion_contrasena"
    respuesta = client.post(reverse("seccion_perfil"), datos)
    assert respuesta.status_code == 200
    form = respuesta.context["form"]
    assert form.is_bound
    assert form.errors[campo_error]
    for campo in ("razon_social", "giro", "direccion_facturacion", "email_contacto"):
        assert form[campo].value() == datos.get(campo)
    assert Cliente.objects.values().get(pk=cliente.pk) == inicial
    assert UsuarioPortal.objects.values().get(usuario=usuario) == perfil_inicial
    assert AceptacionTerminos.objects.values().get(cliente=cliente) == aceptacion_inicial
    assert 'value="incorrecta"' not in respuesta.content.decode()


def test_editar_empresa_no_modifica_nombre_historico_ni_datos_personales(
    client: Client, cuenta: tuple[User, Cliente]
) -> None:
    usuario, cliente = cuenta
    client.force_login(usuario)
    inicial = User.objects.values().get(pk=usuario.pk)
    perfil_inicial = UsuarioPortal.objects.values().get(usuario=usuario)
    aceptacion_inicial = AceptacionTerminos.objects.values().get(cliente=cliente)
    respuesta = client.post(
        reverse("seccion_perfil"),
        {
            **datos_edicion(),
            "username": "ajeno@ejemplo.cl",
            "email": "ajeno@ejemplo.cl",
            "first_name": "Otro",
            "last_name": "Nombre",
            "password": "NuevaClave123!",
            "nombre": "Otro",
            "is_staff": "1",
            "is_superuser": "1",
            "created_at": "2000-01-01",
        },
    )
    assert respuesta.status_code == 302
    cliente.refresh_from_db()
    assert cliente.email_contacto == "empresa@nueva.cl"
    assert cliente.created_at is None
    assert User.objects.values().get(pk=usuario.pk) == inicial
    assert UsuarioPortal.objects.values().get(usuario=usuario) == perfil_inicial
    assert AceptacionTerminos.objects.values().get(cliente=cliente) == aceptacion_inicial


@pytest.mark.parametrize("superusuario", [False, True])
def test_administrador_sigue_editando_solo_su_perfil_institucional(
    client: Client, cuenta: tuple[User, Cliente], superusuario: bool
) -> None:
    usuario, propia = cuenta
    usuario.is_staff = True
    usuario.is_superuser = superusuario
    usuario.save()
    ajena = Cliente.objects.create(rut="76987654-5", razon_social="Institución Ajena")
    inicial = Cliente.objects.values().get(pk=ajena.pk)
    client.force_login(usuario)
    url = reverse("seccion_perfil")
    respuesta = client.get(url, {"cliente_id": ajena.pk})
    assert respuesta.status_code == 200
    assert respuesta.context["cliente"].pk == propia.pk
    respuesta = client.post(url, {**datos_edicion(), "cliente_id": ajena.pk})
    assert respuesta.status_code == 302
    propia.refresh_from_db()
    assert propia.razon_social == datos_edicion()["razon_social"]
    assert Cliente.objects.values().get(pk=ajena.pk) == inicial


@pytest.mark.parametrize("token", ["ausente", "incorrecto", "valido", "origen-ajeno"])
def test_csrf_impide_editar_sin_autorizacion_del_navegador(
    cuenta: tuple[User, Cliente], token: str
) -> None:
    usuario, cliente = cuenta
    navegador = Client(enforce_csrf_checks=True)
    navegador.force_login(usuario)
    url = reverse("seccion_perfil")
    assert navegador.get(url).status_code == 200
    inicial = Cliente.objects.values().get(pk=cliente.pk)
    datos = datos_edicion()
    if token != "ausente":
        datos["csrfmiddlewaretoken"] = (
            "x" * 64 if token == "incorrecto" else navegador.cookies["csrftoken"].value
        )
    respuesta = (
        navegador.post(url, datos, HTTP_ORIGIN="https://ajeno.example.cl")
        if token == "origen-ajeno"
        else navegador.post(url, datos)
    )
    assert respuesta.status_code == (302 if token == "valido" else 403)
    if token == "valido":
        cliente.refresh_from_db()
        assert cliente.razon_social == datos["razon_social"]
    else:
        assert Cliente.objects.values().get(pk=cliente.pk) == inicial


class CampoContrasenaParser(HTMLParser):
    """Comprueba que el HTML inicial permita confirmar sin ejecutar JavaScript."""

    def __init__(self) -> None:
        super().__init__()
        self.en_dialogo = False
        self.campos: list[bool] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "dialog":
            self.en_dialogo = True
        if tag == "input" and dict(attrs).get("name") == "confirmacion_contrasena":
            self.campos.append(self.en_dialogo)

    def handle_endtag(self, tag: str) -> None:
        if tag == "dialog":
            self.en_dialogo = False


def test_contrasena_esta_disponible_sin_javascript(
    client: Client, cuenta: tuple[User, Cliente]
) -> None:
    usuario, _ = cuenta
    client.force_login(usuario)
    respuesta = client.get(reverse("seccion_perfil"))
    parser = CampoContrasenaParser()
    parser.feed(respuesta.content.decode())
    assert parser.campos == [False]


@pytest.mark.parametrize("staff", [False, True])
def test_administrador_no_acepta_terminos_por_una_empresa_ajena(
    cuenta: tuple[User, Cliente], staff: bool
) -> None:
    _, cliente = cuenta
    administrador = User.objects.create_user(
        username="administrador", is_staff=staff, is_superuser=not staff
    )
    inicial = list(AceptacionTerminos.objects.values())
    with pytest.raises(PermissionDenied):
        registrar_aceptacion(cliente, administrador, VERSION_TERMINOS)
    assert list(AceptacionTerminos.objects.values()) == inicial
