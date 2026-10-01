from typing import Any

from django.db.models import QuerySet


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
