from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from .models import Cliente


def obtener_cliente_autorizado(request: HttpRequest, cliente_id: int) -> Cliente:
    """Aplica a una institución el mismo acceso que AislamientoClienteMixin."""
    clientes = Cliente.objects.all()
    usuario = request.user
    if not usuario.is_authenticated:
        clientes = clientes.none()
    elif not (usuario.is_staff or usuario.is_superuser):
        clientes = clientes.filter(usuarioportal__usuario_id=usuario.pk)
    return get_object_or_404(clientes, pk=cliente_id)
