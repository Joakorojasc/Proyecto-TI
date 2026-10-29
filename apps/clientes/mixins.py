from typing import Any

from django.db.models import QuerySet
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404

from .models import Cliente


def get_cliente_autorizado(request: HttpRequest, cliente_id: int) -> Cliente:
    cliente = get_object_or_404(Cliente, id=cliente_id)
    user = request.user

    if user.is_superuser or user.is_staff:
        return cliente

    usuario_portal = getattr(user, "usuarioportal", None)
    if usuario_portal is None or usuario_portal.cliente_id != cliente.id:
        raise Http404("No tienes acceso a esta institución.")

    return cliente


class AislamientoClienteMixin:
    request: Any

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()  # type: ignore[misc]
        user = getattr(self.request, "user", None)

        if user is None or not getattr(user, "is_authenticated", False):
            return queryset.none()

        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return queryset

        usuario_portal = getattr(user, "usuarioportal", None)
        if usuario_portal is None or usuario_portal.cliente_id is None:
            return queryset.none()

        return queryset.filter(cliente_id=usuario_portal.cliente_id)
