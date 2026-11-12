from typing import Any

from django import forms
from django.contrib import admin
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import Plan, Suscripcion

Plan._meta.verbose_name = "plan"
Plan._meta.verbose_name_plural = "planes"
Suscripcion._meta.verbose_name = "suscripción"
Suscripcion._meta.verbose_name_plural = "suscripciones"

TIPOS_PLAN = [
    ("", "---------"),
    ("mensual", "Mensual"),
    ("anual", "Anual"),
    ("personalizado", "Personalizado (negociado)"),
]


class PlanAdminForm(forms.ModelForm):
    """Reglas del plan negociado: solo el superadmin lo registra, y siempre para un cliente."""

    def clean(self) -> dict[str, Any]:
        datos = super().clean() or {}
        tipo = (datos.get("tipo_plan") or "").lower()
        cliente = datos.get("cliente")
        if tipo == "personalizado":
            if cliente is None:
                self.add_error(
                    "cliente",
                    "Un plan personalizado debe asignarse al cliente con el que se negoció.",
                )
            if datos.get("precio_base") is None:
                self.add_error("precio_base", "Indica el precio acordado con el cliente.")
            if not datos.get("limite_usuarios"):
                self.add_error(
                    "limite_usuarios",
                    "Indica la cantidad de usuarios activos acordada con el cliente.",
                )
        elif cliente is not None:
            self.add_error(
                "cliente",
                "Solo los planes personalizados (negociados) se asignan a un cliente.",
            )
        return datos


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
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

    def formfield_for_dbfield(
        self, db_field: Any, request: HttpRequest, **kwargs: Any
    ) -> Any:
        if db_field.name == "tipo_plan":
            return forms.ChoiceField(choices=TIPOS_PLAN, label="Tipo de plan")
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class SuscripcionAdminForm(forms.ModelForm):
    """Impide asignar el plan negociado de otro cliente a una suscripción."""

    def clean(self) -> dict[str, Any]:
        datos = super().clean() or {}
        cliente = datos.get("cliente")
        plan = datos.get("plan")
        if cliente is None or plan is None:
            return datos
        if plan.cliente_id not in (None, cliente.pk):
            self.add_error(
                "plan",
                "Este plan negociado pertenece a otro cliente. "
                "Elige un plan general o uno de este cliente.",
            )
        return datos


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    form = SuscripcionAdminForm
    list_display = ("enlace_cliente", "instancia", "plan", "estado", "fecha_inicio")
    list_select_related = ("cliente", "instancia", "plan")
    list_filter = ("estado", "plan__tipo_plan")
    search_fields = (
        "cliente__razon_social",
        "cliente__rut",
        "instancia__nombre",
        "plan__nombre",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    @admin.display(description="Cliente", ordering="cliente__razon_social")
    def enlace_cliente(self, obj: Suscripcion) -> SafeString:
        cliente = obj.cliente
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html(
            '<a href="{}">{}</a>', url, cliente.razon_social or f"Cliente {cliente.pk}"
        )