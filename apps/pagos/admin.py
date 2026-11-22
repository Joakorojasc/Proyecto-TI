from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from apps.planes.models import Suscripcion

from .models import CodigoDescuento, DocumentoTributario, MedioPago, Pago

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


@admin.register(CodigoDescuento)
class CodigoDescuentoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "plan",
        "porcentaje",
        "activo",
        "suscripciones_con_codigo",
        "pagos_con_codigo",
        "creado_en",
    )
    list_filter = ("activo", "plan")
    search_fields = ("codigo", "plan__nombre")
    ordering = ("plan__nombre", "codigo")
    list_select_related = ("plan",)
    readonly_fields = ("creado_en",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[CodigoDescuento]:
        return (
            super()
            .get_queryset(request)
            .annotate(
                _suscripciones=Count("suscripciones", distinct=True),
                _pagos=Count("pagos", distinct=True),
            )
        )

    @admin.display(description="Suscripciones", ordering="_suscripciones")
    def suscripciones_con_codigo(self, obj: CodigoDescuento) -> int:
        return int(getattr(obj, "_suscripciones", 0))

    @admin.display(description="Pagos", ordering="_pagos")
    def pagos_con_codigo(self, obj: CodigoDescuento) -> int:
        return int(getattr(obj, "_pagos", 0))


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        "enlace_cliente",
        "instancia_pago",
        "plan_pago",
        "monto",
        "codigo_descuento",
        "monto_descuento",
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
        "codigo_descuento",
    )
    list_filter = ("estado", "fecha_pago", "suscripcion__cliente")
    search_fields = (
        "suscripcion__cliente__razon_social",
        "suscripcion__cliente__rut",
        "suscripcion__instancia__nombre",
        "codigo_descuento__codigo",
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
        "folio",
        "tipo_documento",
        "enlace_cliente",
        "monto",
        "fecha_del_pago",
        "enlace_pdf",
    )
    list_display_links = ("folio",)
    list_select_related = (
        "pago",
        "pago__suscripcion",
        "pago__suscripcion__cliente",
        "pago__suscripcion__plan",
        "pago__codigo_descuento",
    )
    list_filter = (
        "tipo_documento",
        "pago__estado",
        "pago__suscripcion__plan",
        "pago__suscripcion__cliente",
    )
    search_fields = (
        "pago__suscripcion__cliente__razon_social",
        "pago__suscripcion__cliente__rut",
        "tipo_documento",
        "folio",
    )
    ordering = ("-folio",)
    fields = (
        "pago",
        "tipo_documento",
        "folio",
        "url_pdf",
        "enlace_pdf",
        "enlace_cliente",
        "plan_del_pago",
        "estado_del_pago",
        "descuento_del_pago",
        "enlace_pago",
    )
    readonly_fields = (
        "enlace_pdf",
        "enlace_cliente",
        "plan_del_pago",
        "estado_del_pago",
        "descuento_del_pago",
        "enlace_pago",
    )

    def formfield_for_foreignkey(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        if db_field.name == "pago":
            kwargs["form_class"] = PagoChoiceField
            kwargs["queryset"] = Pago.objects.select_related("suscripcion__cliente")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Cliente", ordering="pago__suscripcion__cliente__razon_social")
    def enlace_cliente(self, obj: DocumentoTributario) -> str | SafeString:
        if not obj.pago_id:
            return "—"
        cliente = obj.pago.suscripcion.cliente
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, cliente)

    @admin.display(description="Monto", ordering="pago__monto")
    def monto(self, obj: DocumentoTributario) -> str:
        if obj.pago.monto is None:
            return "—"
        return f"${obj.pago.monto}"

    @admin.display(description="Fecha de pago", ordering="pago__fecha_pago")
    def fecha_del_pago(self, obj: DocumentoTributario) -> str:
        if obj.pago.fecha_pago is None:
            return "—"
        return timezone.localtime(obj.pago.fecha_pago).strftime("%d/%m/%Y")

    @admin.display(description="Plan")
    def plan_del_pago(self, obj: DocumentoTributario) -> str:
        if not obj.pago_id:
            return "—"
        return str(obj.pago.suscripcion.plan)

    @admin.display(description="Estado del pago")
    def estado_del_pago(self, obj: DocumentoTributario) -> str:
        if not obj.pago_id:
            return "—"
        return obj.pago.estado or "—"

    @admin.display(description="Descuento aplicado")
    def descuento_del_pago(self, obj: DocumentoTributario) -> str:
        if not obj.pago_id:
            return "—"
        codigo = obj.pago.codigo_descuento
        if codigo is None:
            return "Sin descuento"
        return f"{codigo.codigo} ({codigo.porcentaje} %) · ${obj.pago.monto_descuento}"

    @admin.display(description="Pago")
    def enlace_pago(self, obj: DocumentoTributario) -> str | SafeString:
        if not obj.pago_id:
            return "—"
        url = reverse("admin:pagos_pago_change", args=[obj.pago_id])
        return format_html('<a href="{}">Pago #{}</a>', url, obj.pago_id)

    @admin.display(description="PDF")
    def enlace_pdf(self, obj: DocumentoTributario) -> str | SafeString:
        if obj.url_pdf and obj.url_pdf.startswith(("http://", "https://")):
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">Ver PDF</a>', obj.url_pdf
            )
        return "—"


admin.site.register(MedioPago)
