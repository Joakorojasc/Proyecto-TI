"""Validación, almacenamiento canónico y presentación del RUT chileno."""

import re

from django.core.exceptions import ValidationError

RUT_DUPLICADO = (
    "Esta institución ya está registrada. Si trabajas ahí, "
    "pídele acceso al administrador de la cuenta."
)
FORMATO_RUT = re.compile(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)-[0-9Kk]")


def _con_guion(valor: str) -> str:
    # Conserva la entrada compacta que dev ya aceptaba, sin tolerar puntuación incorrecta.
    if "-" not in valor and len(valor) > 1:
        return f"{valor[:-1]}-{valor[-1]}"
    return valor


def calcular_digito_verificador(numero: str) -> str:
    """Módulo 11 sobre el número del RUT, sin el dígito verificador."""
    suma = 0
    multiplicador = 2
    for digito in reversed(numero):
        suma += int(digito) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    resto = suma % 11
    if resto == 0:
        return "0"
    if resto == 1:
        return "K"
    return str(11 - resto)


def validar_rut(valor: str) -> None:
    """Verifica formato y módulo 11; no confirma existencia ante el SII."""
    rut = _con_guion(valor)
    if not FORMATO_RUT.fullmatch(rut):
        raise ValidationError(
            "Ingresa un RUT con formato válido, por ejemplo 76.123.456-0 o 76123456-0.",
            code="rut_formato",
        )
    cuerpo, digito = rut.replace(".", "").split("-")
    if digito.upper() != calcular_digito_verificador(cuerpo):
        raise ValidationError(
            "El dígito verificador del RUT no es correcto. Revisa el RUT ingresado.",
            code="rut_digito",
        )


def normalizar_rut(valor: str) -> str:
    """Valida y devuelve el RUT sin puntos/ceros iniciales y con K mayúscula."""
    rut = _con_guion(valor.strip().replace(" ", ""))
    validar_rut(rut)
    cuerpo, digito = rut.replace(".", "").split("-")
    return f"{cuerpo.lstrip('0') or '0'}-{digito.upper()}"


def formatear_rut(valor: str) -> str:
    """Mantiene la presentación con puntos utilizada por el perfil de dev."""
    try:
        rut = normalizar_rut(valor)
    except ValidationError:
        return valor
    cuerpo, digito = rut.split("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{digito}"
