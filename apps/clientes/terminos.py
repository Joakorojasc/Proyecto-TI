"""Contrato de aceptación compartido con el Bloque 2; no bloquea instancias."""

from pathlib import Path

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError

from .models import AceptacionTerminos, Cliente, UsuarioPortal

# Identificador técnico de los bytes oficiales; no es una versión legal de Edocere.
SHA256_DOCUMENTO = "b9f8c61b0d559eda0114ec7e92355a119b5227b6c80c805d45a008b11a46b139"
VERSION_TERMINOS = f"sha256-{SHA256_DOCUMENTO}"
DOCUMENTOS_TERMINOS = {
    VERSION_TERMINOS: Path(__file__).parent
    / "documentos"
    / f"terminos-moodle-{SHA256_DOCUMENTO}.pdf",
}


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
    cliente: Cliente, usuario: User | AnonymousUser, version: str
) -> AceptacionTerminos:
    """Registra al actor asociado a la institución, sin reemplazar evidencia previa.

    El llamador debe haber validado la casilla explícita. En el registro se llama
    dentro de la transacción que crea usuario, cliente y UsuarioPortal.
    """
    if not usuario.is_authenticated:
        raise PermissionDenied("Debes iniciar sesión para aceptar los términos.")
    validar_version_terminos(version)
    if not UsuarioPortal.objects.filter(usuario=usuario, cliente=cliente).exists():
        raise PermissionDenied("Solo puedes aceptar los términos de tu institución.")
    aceptacion, _ = AceptacionTerminos.objects.get_or_create(
        cliente=cliente, version_documento=version, defaults={"usuario": usuario}
    )
    return aceptacion
