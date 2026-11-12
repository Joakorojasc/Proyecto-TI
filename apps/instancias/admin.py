from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from apps.planes.models import Plan, Suscripcion

from .models import InstanciaMoodle

InstanciaMoodle._meta.verbose_name = "instancia de Moodle"
InstanciaMoodle._meta.verbose_name_plural = "instancias de Moodle"


class SuscripcionInline(admin.TabularInline):
    model = Suscripcion
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("plan", "estado", "fecha_inicio")
    readonly_fields = fields
    verbose_name_plural = "Suscripciones"

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class TipoDominioFilter(admin.SimpleListFilter):
    title = "tipo de dominio"
    parameter_name = "tipo_dominio"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [("edocere", "Dominio de Edocere"), ("propio", "Dominio propio")]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[InstanciaMoodle]
    ) -> QuerySet[InstanciaMoodle]:
        valor = self.value()
        if valor not in ("edocere", "propio"):
            return queryset
        ids_edocere = [i.pk for i in queryset if i.es_subdominio_edocere]
        if valor == "edocere":
            return queryset.filter(pk__in=ids_edocere)
        return queryset.exclude(pk__in=ids_edocere)


class InstanciaAltaForm(forms.ModelForm):
    """Alta manual: pide el plan y evita planes negociados de otro cliente."""

    plan = forms.ModelChoiceField(
        queryset=Plan.objects.all(),
        label="Plan",
        help_text="Un plan general, o el plan negociado de este mismo cliente.",
    )

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


@admin.register(InstanciaMoodle)
class InstanciaMoodleAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_instancia",
        "enlace_cliente",
        "dominio",
        "version",
        "estado",
        "created_at",
    )
    list_select_related = ("cliente",)
    search_fields = ("nombre",)
    list_filter = ("estado", TipoDominioFilter)
    inlines = [SuscripcionInline]

    @admin.display(description="Instancia", ordering="nombre")
    def nombre_instancia(self, obj: InstanciaMoodle) -> str:
        return str(obj)

    @admin.display(description="Cliente", ordering="cliente__razon_social")
    def enlace_cliente(self, obj: InstanciaMoodle) -> str | SafeString:
        cliente = obj.cliente
        etiqueta = cliente.razon_social or cliente.rut_formateado or f"Cliente {cliente.pk}"
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, etiqueta)

    def get_form(
        self, request: HttpRequest, obj: Any | None = None, change: bool = False, **kwargs: Any
    ) -> Any:
        if obj is None:
            kwargs["form"] = InstanciaAltaForm
        return super().get_form(request, obj, change=change, **kwargs)

    def save_model(
        self, request: HttpRequest, obj: InstanciaMoodle, form: Any, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)
        if change:
            return
        Suscripcion.objects.create(
            instancia=obj,
            cliente=obj.cliente,
            plan=form.cleaned_data["plan"],
            estado="activa",
            fecha_inicio=timezone.now(),
        )
