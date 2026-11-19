from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import InstanciaMoodle, SolicitudAprovisionamiento

admin.site.register(InstanciaMoodle)


@admin.register(SolicitudAprovisionamiento)
class SolicitudAprovisionamientoAdmin(admin.ModelAdmin):
    list_display = ("instancia", "estado", "intentos", "updated_at")
    list_filter = ("estado",)
    readonly_fields = (
        "instancia",
        "estado",
        "intentos",
        "operation_id",
        "idempotency_key",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
