from django.db.models import QuerySet


class AislamientoClienteMixin:
    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        if hasattr(self.request.user, "usuarioportal"):
            cliente_del_usuario = self.request.user.usuarioportal.cliente
            return queryset.filter(cliente=cliente_del_usuario)
        return queryset.none()
