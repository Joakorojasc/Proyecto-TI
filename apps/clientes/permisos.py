from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from .models import Cliente, UsuarioPortal


def es_superadministrador(usuario: User | AnonymousUser | None) -> bool:
    """Staff habilita el admin de Django, no el acceso global del portal."""
    return usuario is not None and usuario.is_authenticated and usuario.is_superuser


def obtener_cliente_propio(request: HttpRequest) -> Cliente | None:
    """El perfil y los términos siempre pertenecen a la cuenta de la sesión."""
    if not request.user.is_authenticated:
        return None
    perfil = (
        UsuarioPortal.objects.select_related("cliente").filter(usuario_id=request.user.pk).first()
    )
    return perfil.cliente if perfil is not None else None


def obtener_cliente_autorizado(request: HttpRequest, cliente_id: int) -> Cliente:
    """Aplica a una institución el mismo acceso que AislamientoClienteMixin."""
    clientes = Cliente.objects.all()
    usuario = request.user
    if not usuario.is_authenticated:
        clientes = clientes.none()
    elif not es_superadministrador(usuario):
        clientes = clientes.filter(usuarioportal__usuario_id=usuario.pk)
    return get_object_or_404(clientes, pk=cliente_id)
