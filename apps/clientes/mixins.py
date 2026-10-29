from typing import Any

from django.db.models import QuerySet

from .permisos import es_superadministrador


class AislamientoClienteMixin:
    request: Any

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()  # type: ignore[misc]
        user = getattr(self.request, "user", None)

        if user is None or not getattr(user, "is_authenticated", False):
            return queryset.none()

        if es_superadministrador(user):
            return queryset

        usuario_portal = getattr(user, "usuarioportal", None)
        if usuario_portal is None or usuario_portal.cliente_id is None:
            return queryset.none()

        return queryset.filter(cliente_id=usuario_portal.cliente_id)
