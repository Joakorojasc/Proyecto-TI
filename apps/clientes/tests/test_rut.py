from contextlib import nullcontext
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from apps.clientes.forms import EmpresaRegistroForm, RegistroClienteForm
from apps.clientes.models import Cliente, UsuarioPortal
from apps.clientes.terminos import VERSION_TERMINOS
from apps.clientes.validators import RUT_DUPLICADO, normalizar_rut, validar_rut


@pytest.mark.parametrize(
    "rut",
    [
        "76.123.456-0",
        "76123456-0",
        "76.987.654-5",
        "12.345.678-5",
        "12345678-5",
        "1.234.567-4",
        "6-K",
        "6-k",
        "14-0",
    ],
)
def test_validador_acepta_rut_valido(rut: str) -> None:
    # Incluye resultados 0, K y numéricos, sin restringir rangos o prefijos.
    validar_rut(rut)


@pytest.mark.parametrize(
    "rut",
    [
        "",
        "76.123.456",
        "76.12.3456-0",
        "76123.456-0",
        "76..123.456-0",
        ".76.123.456-0",
        "76.123.456.-0",
        "76.123.456--0",
        "76.123.456-00",
        "76 123 456-0",
        "-0",
        "ABC-0",
        "76.123.456-X",
        "７６１２３４５６-0",
        "76123456-0\n",
    ],
)
def test_validador_rechaza_formato_incorrecto(rut: str) -> None:
    with pytest.raises(ValidationError) as error:
        validar_rut(rut)

    assert error.value.code == "rut_formato"
    assert "formato válido" in error.value.message


@pytest.mark.parametrize("rut", ["76.123.456-7", "76987654-3", "6-0", "14-K"])
def test_validador_rechaza_digito_incorrecto(rut: str) -> None:
    with pytest.raises(ValidationError) as error:
        validar_rut(rut)

    assert error.value.code == "rut_digito"
    assert "dígito verificador" in error.value.message


@pytest.mark.django_db
@pytest.mark.parametrize("form_class", [EmpresaRegistroForm, RegistroClienteForm])
@pytest.mark.parametrize("rut", ["76.123.456-0", "76123456-0", "6-K", "6-k"])
def test_formularios_guardan_rut_normalizado(
    form_class: type[EmpresaRegistroForm] | type[RegistroClienteForm], rut: str
) -> None:
    form = form_class(
        data={
            "rut": rut,
            "acepta_terminos": "on",
            "version_terminos": VERSION_TERMINOS,
            "razon_social": "Institución de prueba",
            "giro": "Educación",
            "direccion_facturacion": "Calle 123",
            "email_contacto": "contacto@demo.cl",
        }
    )

    assert form.fields["rut"].label == "RUT de la institución"
    assert form.is_valid(), form.errors
    cliente = form.save()
    cliente.refresh_from_db()
    assert cliente.rut == normalizar_rut(rut)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rut, mensaje",
    [
        ("76.12.3456-0", "Ingresa un RUT con formato válido"),
        ("76.123.456-7", "El dígito verificador del RUT no es correcto"),
        ("", "Este campo es obligatorio."),
    ],
)
def test_registro_invalido_muestra_error_y_no_crea_cuentas(
    client: Client, rut: str, mensaje: str
) -> None:
    respuesta = client.post(
        reverse("registro"),
        data={
            "username": "admin@demo.cl",
            "password1": "ClaveSegura123!",
            "password2": "ClaveSegura123!",
            "razon_social": "Institución de prueba",
            "rut": rut,
            "acepta_terminos": "on",
            "version_terminos": VERSION_TERMINOS,
            "giro": "Educación",
            "direccion_facturacion": "Calle 123",
            "email_contacto": "contacto@demo.cl",
        },
    )

    assert respuesta.status_code == 200
    assert "rut" in respuesta.context["empresa_form"].errors
    assert mensaje in respuesta.content.decode()
    assert not Cliente.objects.exists()
    assert not User.objects.exists()
    assert not UsuarioPortal.objects.exists()


@pytest.mark.parametrize(
    "rut, esperado",
    [
        ("76.123.456-0", "76123456-0"),
        ("76123456-0", "76123456-0"),
        ("6-k", "6-K"),
        ("0.000.006-k", "6-K"),
    ],
)
def test_normalizar_rut(rut: str, esperado: str) -> None:
    assert normalizar_rut(rut) == esperado


@pytest.mark.parametrize("rut", ["DEMO-PEQUENO-001", "76.123.456-7", "76123456-X"])
def test_normalizar_no_corrige_rut_invalido(rut: str) -> None:
    with pytest.raises(ValidationError):
        normalizar_rut(rut)


@pytest.mark.django_db
@pytest.mark.parametrize("form_class", [EmpresaRegistroForm, RegistroClienteForm])
@pytest.mark.parametrize("rut", ["76.123.456-0", "76123456-0", "076123456-0"])
def test_formularios_rechazan_rut_equivalente_registrado(
    form_class: type[EmpresaRegistroForm] | type[RegistroClienteForm], rut: str
) -> None:
    Cliente.objects.create(rut="76123456-0")
    form = form_class(
        data={
            "rut": rut,
            "acepta_terminos": "on",
            "version_terminos": VERSION_TERMINOS,
            "razon_social": "Otra institución",
        }
    )

    assert not form.is_valid()
    assert form.errors["rut"] == [RUT_DUPLICADO]
    assert Cliente.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("rut", ["76.123.456-0", "76123456-0"])
def test_modelo_normaliza_y_base_de_datos_impide_duplicados(rut: str) -> None:
    original = Cliente.objects.create(rut="76.123.456-0")
    assert original.rut == "76123456-0"
    with pytest.raises(IntegrityError), transaction.atomic():
        Cliente.objects.create(rut=rut)
    assert Cliente.objects.count() == 1


@pytest.mark.django_db
def test_restriccion_unica_tambien_protege_escrituras_sin_save() -> None:
    Cliente.objects.create(rut="76123456-0")
    # bulk_create omite save(): el índice UNIQUE sigue protegiendo la base.
    with pytest.raises(IntegrityError), transaction.atomic():
        Cliente.objects.bulk_create([Cliente(rut="76123456-0")])
    assert Cliente.objects.count() == 1


@pytest.mark.django_db
def test_modelo_normaliza_k_y_permite_varios_rut_ausentes() -> None:
    cliente = Cliente.objects.create(rut="6-k")
    cliente.refresh_from_db()
    assert cliente.rut == "6-K"
    for rut in (None, None, "", "   "):
        cliente = Cliente.objects.create(rut=rut)
        cliente.refresh_from_db()
        assert cliente.rut is None


@pytest.mark.django_db
@pytest.mark.parametrize("concurrencia", [False, True])
def test_registro_duplicado_muestra_error_sin_crear_usuario(
    client: Client, concurrencia: bool
) -> None:
    Cliente.objects.create(rut="76123456-0", razon_social="Original")
    form_class = EmpresaRegistroForm
    # Al omitir solo la comprobación previa se reproduce el conflicto que
    # ocurriría si otra petición guardara el RUT después de is_valid().
    context = patch.object(form_class, "validate_unique") if concurrencia else nullcontext()
    with context:
        respuesta = client.post(
            reverse("registro"),
            data={
                "username": "admin@otra.cl",
                "password1": "ClaveSegura123!",
                "password2": "ClaveSegura123!",
                "rut": "76.123.456-0",
                "acepta_terminos": "on",
                "version_terminos": VERSION_TERMINOS,
                "razon_social": "Otra institución",
                "giro": "Educación",
                "direccion_facturacion": "Calle 123",
                "email_contacto": "contacto@otra.cl",
            },
        )

    assert respuesta.status_code == 200
    assert respuesta.context["empresa_form"].errors["rut"] == [RUT_DUPLICADO]
    assert RUT_DUPLICADO in respuesta.content.decode()
    assert Cliente.objects.get().razon_social == "Original"
    assert not User.objects.exists()
    assert not UsuarioPortal.objects.exists()
