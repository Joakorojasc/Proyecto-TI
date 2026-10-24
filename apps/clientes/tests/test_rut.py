import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from apps.clientes.forms import EmpresaRegistroForm, RegistroClienteForm
from apps.clientes.models import Cliente, UsuarioPortal
from apps.clientes.validators import validar_rut


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
        "761234560",
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

    assert error.value.code == "rut_digito_verificador"
    assert "dígito verificador" in error.value.message


@pytest.mark.django_db
@pytest.mark.parametrize("form_class", [EmpresaRegistroForm, RegistroClienteForm])
@pytest.mark.parametrize("rut", ["76.123.456-0", "76123456-0", "6-K", "6-k"])
def test_formularios_guardan_rut_sin_normalizar(
    form_class: type[EmpresaRegistroForm] | type[RegistroClienteForm], rut: str
) -> None:
    form = form_class(
        data={
            "rut": rut,
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
    assert cliente.rut == rut


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ruta, formulario", [("registro", "empresa_form"), ("registro_cliente", "form")]
)
@pytest.mark.parametrize(
    "rut, mensaje",
    [
        ("76.12.3456-0", "Ingresa un RUT con formato válido"),
        ("76.123.456-7", "El dígito verificador del RUT no es correcto"),
        ("", "Este campo es obligatorio."),
    ],
)
def test_registro_invalido_muestra_error_y_no_crea_cuentas(
    client: Client, ruta: str, formulario: str, rut: str, mensaje: str
) -> None:
    respuesta = client.post(
        reverse(ruta),
        data={
            "username": "admin@demo.cl",
            "password1": "ClaveSegura123!",
            "password2": "ClaveSegura123!",
            "razon_social": "Institución de prueba",
            "rut": rut,
            "giro": "Educación",
            "direccion_facturacion": "Calle 123",
            "email_contacto": "contacto@demo.cl",
        },
    )

    assert respuesta.status_code == 200
    assert "rut" in respuesta.context[formulario].errors
    assert mensaje in respuesta.content.decode()
    assert not Cliente.objects.exists()
    assert not User.objects.exists()
    assert not UsuarioPortal.objects.exists()
