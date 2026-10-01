from django.contrib import admin

from .models import Plan, Suscripcion


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "cliente",
        "tipo_plan",
        "precio_base",
        "precio_por_usuario",
        "limite_usuarios",
    )
    list_filter = ("tipo_plan",)
    search_fields = ("nombre", "cliente__razon_social", "cliente__rut")


admin.site.register(Suscripcion)
