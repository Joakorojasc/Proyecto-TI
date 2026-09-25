from typing import Any

from django.db.models import QuerySet


class AislamientoClienteMixin:
    request: Any

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()  # type: ignore[misc]
        usuario_portal = getattr(self.request.user, "usuarioportal", None)
        if usuario_portal is None or usuario_portal.cliente_id is None:
            return queryset.none()
        return queryset.filter(cliente_id=usuario_portal.cliente_id)
