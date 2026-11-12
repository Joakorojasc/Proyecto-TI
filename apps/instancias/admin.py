from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from .consumo import con_datos_consumo
from .models import InstanciaMoodle


@admin.register(InstanciaMoodle)
class InstanciaMoodleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "cliente", "estado", "consumo")
    list_select_related = ("cliente",)

    class Media:
        css = {"all": ("css/consumo_instancia.css",)}

    def get_queryset(self, request: HttpRequest) -> QuerySet[InstanciaMoodle]:
        return con_datos_consumo(super().get_queryset(request))

    @admin.display(description="Consumo de usuarios")
    def consumo(self, instancia: InstanciaMoodle) -> str:
        contenido = render_to_string(
            "instancias/consumo.html", {"consumo": instancia.consumo_usuarios}
        )
        return mark_safe(contenido)
