from typing import Any

from django import forms
from django.contrib import admin
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from apps.planes.models import Suscripcion

from .models import DocumentoTributario, MedioPago, Pago

DocumentoTributario._meta.verbose_name = "documento tributario"
DocumentoTributario._meta.verbose_name_plural = "documentos tributarios"


class SuscripcionChoiceField(forms.ModelChoiceField):
    """Muestra cada suscripción como «Cliente · Instancia · Plan» en el desplegable."""

    def label_from_instance(self, obj: Any) -> str:
        return f"{obj.cliente} · {obj.instancia} · {obj.plan}"


class PagoChoiceField(forms.ModelChoiceField):
    """Muestra cada pago como «Pago #id · Cliente · monto» en el desplegable."""

    def label_from_instance(self, obj: Any) -> str:
        monto = obj.monto if obj.monto is not None else "sin monto"
        return f"Pago #{obj.pk} · {obj.suscripcion.cliente} · {monto}"


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "enlace_cliente",
        "instancia_pago",
        "plan_pago",
        "monto",
        "fecha_pago",
        "estado",
        "tiene_documento",
    )
    list_select_related = (
        "suscripcion",
        "suscripcion__cliente",
        "suscripcion__instancia",
        "suscripcion__plan",
        "documentotributario",
    )
    list_filter = ("estado", "fecha_pago", "suscripcion__cliente")
    search_fields = (
        "suscripcion__cliente__razon_social",
        "suscripcion__cliente__rut",
        "suscripcion__instancia__nombre",
    )
    ordering = ("-fecha_pago",)

    def formfield_for_foreignkey(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        if db_field.name == "suscripcion":
            kwargs["form_class"] = SuscripcionChoiceField
            kwargs["queryset"] = Suscripcion.objects.select_related("cliente", "instancia", "plan")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Cliente", ordering="suscripcion__cliente__razon_social")
    def enlace_cliente(self, obj: Pago) -> SafeString:
        cliente = obj.suscripcion.cliente
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, cliente)

    @admin.display(description="Instancia", ordering="suscripcion__instancia__nombre")
    def instancia_pago(self, obj: Pago) -> str:
        return str(obj.suscripcion.instancia)

    @admin.display(description="Plan", ordering="suscripcion__plan__nombre")
    def plan_pago(self, obj: Pago) -> str:
        return str(obj.suscripcion.plan)

    @admin.display(boolean=True, description="Documento")
    def tiene_documento(self, obj: Pago) -> bool:
        return hasattr(obj, "documentotributario")


@admin.register(DocumentoTributario)
class DocumentoTributarioAdmin(admin.ModelAdmin):
    list_display = (
        "enlace_cliente",
        "tipo_documento",
        "folio",
        "numero_pago",
        "enlace_pdf",
    )
    list_select_related = ("pago", "pago__suscripcion", "pago__suscripcion__cliente")
    list_filter = ("tipo_documento", "pago__estado", "pago__suscripcion__cliente")
    search_fields = (
        "pago__suscripcion__cliente__razon_social",
        "pago__suscripcion__cliente__rut",
        "tipo_documento",
        "folio",
    )
    ordering = ("-folio",)

    def formfield_for_foreignkey(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        if db_field.name == "pago":
            kwargs["form_class"] = PagoChoiceField
            kwargs["queryset"] = Pago.objects.select_related("suscripcion__cliente")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Cliente", ordering="pago__suscripcion__cliente__razon_social")
    def enlace_cliente(self, obj: DocumentoTributario) -> SafeString:
        cliente = obj.pago.suscripcion.cliente
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, cliente)

    @admin.display(description="Pago", ordering="pago")
    def numero_pago(self, obj: DocumentoTributario) -> str:
        return f"Pago #{obj.pago_id}"

    @admin.display(description="PDF")
    def enlace_pdf(self, obj: DocumentoTributario) -> str | SafeString:
        if obj.url_pdf and obj.url_pdf.startswith(("http://", "https://")):
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">Ver PDF</a>', obj.url_pdf
            )
        return "—"


admin.site.register(MedioPago)
