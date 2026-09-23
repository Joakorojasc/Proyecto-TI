from typing import Any

from django.db.models import QuerySet


class AislamientoClienteMixin:
    request: Any

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()  # type: ignore[misc]
        if hasattr(self.request.user, "usuarioportal"):
            cliente_del_usuario = self.request.user.usuarioportal.cliente
            return queryset.filter(cliente=cliente_del_usuario)
        return queryset.none()
