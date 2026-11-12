from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import MedicionUsoMensual

MedicionUsoMensual._meta.verbose_name = "medición de uso mensual"
MedicionUsoMensual._meta.verbose_name_plural = "mediciones de uso mensual"

MESES = [
    (1, "Enero"),
    (2, "Febrero"),
    (3, "Marzo"),
    (4, "Abril"),
    (5, "Mayo"),
    (6, "Junio"),
    (7, "Julio"),
    (8, "Agosto"),
    (9, "Septiembre"),
    (10, "Octubre"),
    (11, "Noviembre"),
    (12, "Diciembre"),
]
NOMBRE_MES = dict(MESES)


class MesFilter(admin.SimpleListFilter):
    title = "mes"
    parameter_name = "mes"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [(str(numero), nombre) for numero, nombre in MESES]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[MedicionUsoMensual]
    ) -> QuerySet[MedicionUsoMensual]:
        valor = self.value()
        if valor and valor.isdigit():
            return queryset.filter(mes=int(valor))
        return queryset


@admin.register(MedicionUsoMensual)
class MedicionUsoMensualAdmin(admin.ModelAdmin):
    list_display = (
        "enlace_cliente",
        "instancia",
        "periodo",
        "usuarios_activos",
        "cantidad_cursos",
        "cantidad_categorias",
    )
    list_select_related = ("instancia", "instancia__cliente")
    list_filter = ("anio", MesFilter, "instancia__cliente")
    search_fields = (
        "instancia__nombre",
        "instancia__cliente__razon_social",
        "instancia__cliente__rut",
    )
    ordering = ("-anio", "-mes")

    @admin.display(description="Cliente", ordering="instancia__cliente__razon_social")
    def enlace_cliente(self, obj: MedicionUsoMensual) -> SafeString:
        cliente = obj.instancia.cliente
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, cliente)

    @admin.display(description="Período", ordering="anio")
    def periodo(self, obj: MedicionUsoMensual) -> str:
        if obj.mes is None or obj.anio is None:
            return "—"
        return f"{NOMBRE_MES.get(obj.mes, obj.mes)} {obj.anio}"
