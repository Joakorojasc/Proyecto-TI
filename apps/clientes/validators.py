import re

from django.core.exceptions import ValidationError

RUT_DUPLICADO = "Ya existe una institución registrada con este RUT."


def validar_rut(value: str) -> None:
    """Valida formato y módulo 11 sin modificar el RUT ni consultar su existencia legal."""
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)-[0-9Kk]", value):
        raise ValidationError(
            "Ingresa un RUT con formato válido, por ejemplo 76.123.456-0 o 76123456-0.",
            code="rut_formato",
        )

    cuerpo, digito = value.replace(".", "").split("-")
    suma = sum(int(numero) * (2 + indice % 6) for indice, numero in enumerate(reversed(cuerpo)))
    resultado = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resultado, str(resultado))
    if digito.upper() != esperado:
        raise ValidationError(
            "El dígito verificador del RUT no es correcto. Revisa el RUT ingresado.",
            code="rut_digito_verificador",
        )


def normalizar_rut(value: str) -> str:
    """Devuelve un RUT validado sin puntos, sin ceros iniciales y con K mayúscula."""
    validar_rut(value)
    cuerpo, digito = value.replace(".", "").split("-")
    return f"{cuerpo.lstrip('0') or '0'}-{digito.upper()}"
