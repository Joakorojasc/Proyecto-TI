import pytest
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from apps.clientes.forms import UsuarioRegistroForm
from apps.clientes.models import AceptacionTerminos, Cliente, UsuarioPortal
from apps.clientes.password_validators import MoodlePasswordValidator
from apps.clientes.terminos import VERSION_TERMINOS


@pytest.mark.parametrize(
    ("clave", "codigo"),
    [
        ("Abc12!x", "password_too_short"),
        ("segura2026!", "password_no_upper"),
        ("SEGURA2026!", "password_no_lower"),
        ("ClaveSegura!", "password_no_digit"),
        ("ClaveSegura2026", "password_no_special"),
        ("password", "password_too_common"),
        ("123456789", "password_entirely_numeric"),
    ],
)
def test_validadores_configurados_rechazan_claves_incorrectas(clave: str, codigo: str) -> None:
    with pytest.raises(ValidationError) as error:
        validate_password(clave)
    assert codigo in {e.code for e in error.value.error_list}


@pytest.mark.parametrize("clave", ["Segura1.", "Segura1!", "Segura1@", "Segura1#", "Ñandú12!"])
def test_acepta_ocho_caracteres_y_distintos_simbolos(clave: str) -> None:
    validate_password(clave)


def test_validador_reutilizable_informa_todas_las_condiciones_faltantes() -> None:
    with pytest.raises(ValidationError) as error:
        MoodlePasswordValidator().validate("abcdefgh")
    assert {e.code for e in error.value.error_list} == {
        "password_no_upper",
        "password_no_digit",
        "password_no_special",
    }
    mensajes = " ".join(error.value.messages)
    assert "mayúscula" in mensajes
    assert "número" in mensajes
    assert "carácter especial" in mensajes
    assert "minúscula" not in mensajes


def test_similitud_con_datos_del_usuario_sigue_rechazada() -> None:
    usuario = User(username="Institucion2026!", email="Institucion2026!@ejemplo.cl")
    with pytest.raises(ValidationError) as error:
        validate_password("Institucion2026!", user=usuario)
    assert "password_too_similar" in {e.code for e in error.value.error_list}


@pytest.mark.django_db
def test_formulario_hereda_validacion_y_muestra_las_condiciones_incumplidas() -> None:
    form = UsuarioRegistroForm(
        data={"username": "cuenta@ejemplo.cl", "password1": "abcdefgh", "password2": "abcdefgh"}
    )
    assert not form.is_valid()
    codigos = {error.code for error in form.errors.as_data()["password2"]}
    assert {"password_no_upper", "password_no_digit", "password_no_special"} <= codigos


@pytest.mark.django_db
def test_registro_muestra_ayuda_antes_de_enviar(client: Client) -> None:
    respuesta = client.get(reverse("registro"))
    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert MoodlePasswordValidator().get_help_text() in contenido
    assert "8" in str(respuesta.context["user_form"].fields["password1"].help_text)


def datos_registro(clave: str) -> dict[str, str]:
    return {
        "username": "cuenta@ejemplo.cl",
        "password1": clave,
        "password2": clave,
        "razon_social": "Institución de Prueba",
        "rut": "76.123.456-0",
        "acepta_terminos": "on",
        "version_terminos": VERSION_TERMINOS,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("clave", "codigo"),
    [
        ("Abc12!x", "password_too_short"),
        ("segura2026!", "password_no_upper"),
        ("SEGURA2026!", "password_no_lower"),
        ("ClaveSegura!", "password_no_digit"),
        ("ClaveSegura2026", "password_no_special"),
        ("password", "password_too_common"),
        ("abcdefgh", "password_no_upper"),
    ],
)
def test_registro_rechazado_no_crea_datos_parciales(
    client: Client, clave: str, codigo: str
) -> None:
    respuesta = client.post(reverse("registro"), datos_registro(clave))
    assert respuesta.status_code == 200
    errores = respuesta.context["user_form"].errors.as_data()["password2"]
    assert codigo in {error.code for error in errores}
    assert str(errores[0].messages[0]) in respuesta.content.decode()
    assert not User.objects.exists()
    assert not Cliente.objects.exists()
    assert not UsuarioPortal.objects.exists()
    assert not AceptacionTerminos.objects.exists()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize("clave", ["Segura1.", "Segura1!", "Segura1@"])
def test_registro_guarda_hash_relaciones_y_permite_login(client: Client, clave: str) -> None:
    respuesta = client.post(reverse("registro"), datos_registro(clave))
    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("instancias:lista")
    usuario = User.objects.get()
    cliente = Cliente.objects.get()
    perfil = UsuarioPortal.objects.get()
    aceptacion = AceptacionTerminos.objects.get()
    assert perfil.usuario_id == aceptacion.usuario_id == usuario.pk
    assert perfil.cliente_id == aceptacion.cliente_id == cliente.pk
    assert aceptacion.version_documento == VERSION_TERMINOS
    assert cliente.rut == "76123456-0"
    assert usuario.password != clave
    assert usuario.check_password(clave)
    assert int(client.session["_auth_user_id"]) == usuario.pk

    assert client.post(reverse("logout")).status_code == 302
    assert "_auth_user_id" not in client.session
    respuesta = client.post(reverse("login"), {"username": usuario.username, "password": clave})
    assert respuesta.status_code == 302
    assert int(client.session["_auth_user_id"]) == usuario.pk


@pytest.mark.django_db
def test_politica_no_invalida_el_login_ni_cambia_la_clave_de_usuarios_historicos(
    client: Client,
) -> None:
    usuario = User.objects.create_user(username="historico@ejemplo.cl", password="clave-anterior")
    hash_original = usuario.password
    respuesta = client.post(
        reverse("login"), {"username": usuario.username, "password": "clave-anterior"}
    )
    assert respuesta.status_code == 302
    assert int(client.session["_auth_user_id"]) == usuario.pk
    usuario.refresh_from_db()
    assert usuario.password == hash_original
