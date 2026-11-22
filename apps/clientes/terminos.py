"""Contrato de aceptación compartido con el Bloque 2; no bloquea instancias."""

from datetime import datetime
from pathlib import Path

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AceptacionTerminos, Cliente, UsuarioPortal

# Identificador técnico de los bytes oficiales; no es una versión legal de Edocere.
SHA256_DOCUMENTO = "b9f8c61b0d559eda0114ec7e92355a119b5227b6c80c805d45a008b11a46b139"
VERSION_TERMINOS = f"sha256-{SHA256_DOCUMENTO}"
DOCUMENTOS_TERMINOS = {
    VERSION_TERMINOS: Path(__file__).parent
    / "documentos"
    / f"terminos-moodle-{SHA256_DOCUMENTO}.pdf",
}


# Marca de sesión que deja la descarga del PDF. Es la prueba de que la persona
# abrió el documento antes de marcar la casilla.
CLAVE_SESION_DOCUMENTO = "terminos_documento_abierto"

ERROR_SIN_ABRIR = (
    "Abre primero el documento de términos y condiciones. El enlace lo muestra en otra pestaña."
)


def asegurar_sesion(request: HttpRequest) -> None:
    """Crea la sesión antes de mostrar el formulario.

    Si la sesión naciera recién al pedir el PDF, el navegador tendría que
    guardar la cookie desde esa respuesta, y con un PDF abierto en otra pestaña
    hay navegadores que no lo hacen. Creándola antes, la petición del documento
    ya llega con la cookie puesta.
    """
    if not request.session.session_key:
        request.session.create()


def marcar_documento_abierto(request: HttpRequest, version: str) -> None:
    """Guarda en la sesión qué documento se abrió y cuándo."""
    request.session[CLAVE_SESION_DOCUMENTO] = {
        "version": version,
        "fecha": timezone.now().isoformat(),
    }


def fecha_documento_abierto(request: HttpRequest) -> datetime | None:
    """Cuándo se abrió el documento vigente en esta sesión, o None si no se abrió."""
    marca = request.session.get(CLAVE_SESION_DOCUMENTO)
    if not isinstance(marca, dict) or marca.get("version") != VERSION_TERMINOS:
        return None
    return parse_datetime(str(marca.get("fecha", "")))


def documento_abierto(request: HttpRequest) -> bool:
    return fecha_documento_abierto(request) is not None


def validar_version_terminos(version: str) -> None:
    if version != VERSION_TERMINOS:
        raise ValidationError(
            "El documento vigente cambió. Recarga la página, revisa el documento y vuelve a aceptar.",
            code="terminos_desactualizados",
        )


def tiene_aceptacion_vigente(cliente: Cliente) -> bool:
    if cliente.pk is None:
        return False
    return AceptacionTerminos.objects.filter(
        cliente=cliente, version_documento=VERSION_TERMINOS
    ).exists()


def registrar_aceptacion(
    cliente: Cliente,
    usuario: User | AnonymousUser,
    version: str,
    fecha_apertura: datetime | None = None,
) -> AceptacionTerminos:
    """Registra al actor asociado a la institución, sin reemplazar evidencia previa.

    El llamador debe haber validado la casilla explícita. En el registro se llama
    dentro de la transacción que crea usuario, cliente y UsuarioPortal.
    `fecha_apertura` guarda cuándo se abrió el PDF, como respaldo de la casilla.
    """
    if not usuario.is_authenticated:
        raise PermissionDenied("Debes iniciar sesión para aceptar los términos.")
    validar_version_terminos(version)
    if not UsuarioPortal.objects.filter(usuario=usuario, cliente=cliente).exists():
        raise PermissionDenied("Solo puedes aceptar los términos de tu institución.")
    aceptacion, _ = AceptacionTerminos.objects.get_or_create(
        cliente=cliente,
        version_documento=version,
        defaults={"usuario": usuario, "fecha_documento_abierto": fecha_apertura},
    )
    return aceptacion
