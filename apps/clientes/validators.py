"""Validación de RUT chileno.

El RUT se guarda normalizado, sin puntos y con el guion antes del dígito
verificador, para que "12345678-5" y "12.345.678-5" no entren como dos
valores distintos. La restricción de único del modelo depende de eso.
"""

import re

from django.core.exceptions import ValidationError

# Hasta 8 dígitos, guion, y el dígito verificador que puede ser un número o K.
FORMATO_RUT = re.compile(r"^(\d{1,8})-([0-9K])$")


def normalizar_rut(valor: str) -> str:
    """Saca puntos y espacios, pone la K en mayúscula y agrega el guion si falta."""
    limpio = valor.strip().replace(".", "").replace(" ", "").upper()
    if "-" not in limpio and len(limpio) > 1:
        limpio = f"{limpio[:-1]}-{limpio[-1]}"
    return limpio


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
    """Revisa el formato y el dígito verificador.

    Verifica que el RUT sea matemáticamente correcto. No verifica que esté
    inscrito en el SII, para eso haría falta consultar un servicio externo.
    """
    rut = normalizar_rut(valor)

    coincidencia = FORMATO_RUT.match(rut)
    if not coincidencia:
        raise ValidationError(
            "Escribe el RUT con el formato 12.345.678-5.",
            code="rut_formato",
        )

    numero, digito = coincidencia.groups()
    if calcular_digito_verificador(numero) != digito:
        raise ValidationError(
            "El RUT no es válido. Revisa el dígito verificador.",
            code="rut_digito",
        )


def formatear_rut(valor: str) -> str:
    """Deja el RUT con puntos para mostrarlo: 12345678-5 queda 12.345.678-5."""
    rut = normalizar_rut(valor)
    coincidencia = FORMATO_RUT.match(rut)
    if not coincidencia:
        return valor

    numero, digito = coincidencia.groups()
    return f"{int(numero):,}".replace(",", ".") + f"-{digito}"
