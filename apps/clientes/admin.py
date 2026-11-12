from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, OuterRef, Q, QuerySet
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from apps.instancias.models import InstanciaMoodle
from apps.planes.models import Plan, Suscripcion

from . import terminos
from .models import AceptacionTerminos, Cliente, UsuarioPortal

UsuarioPortal._meta.verbose_name = "usuario del portal"
UsuarioPortal._meta.verbose_name_plural = "usuarios del portal"
AceptacionTerminos._meta.verbose_name = "aceptación de términos"
AceptacionTerminos._meta.verbose_name_plural = "aceptaciones de términos"


class ClienteAltaForm(forms.ModelForm):
    """Formulario de alta: crea la empresa y su primer usuario administrador."""

    correo_admin = forms.EmailField(
        label="Correo del usuario administrador",
        help_text="Con este correo iniciará sesión en el portal.",
        max_length=150,
    )
    password1 = forms.CharField(label="Contraseña inicial", strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repetir contraseña", strip=False, widget=forms.PasswordInput)

    class Meta:
        model = Cliente
        fields = (
            "rut",
            "razon_social",
            "giro",
            "direccion_facturacion",
            "email_contacto",
            "created_at",
        )

    def clean_correo_admin(self) -> str:
        correo: str = self.cleaned_data["correo_admin"].strip().lower()
        if User.objects.filter(username__iexact=correo).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def clean(self) -> dict[str, Any]:
        datos = super().clean() or {}
        clave1 = datos.get("password1")
        clave2 = datos.get("password2")
        if clave1 and clave2 and clave1 != clave2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif clave1:
            correo = datos.get("correo_admin") or ""
            try:
                validate_password(clave1, User(username=correo, email=correo))
            except ValidationError as error:
                self.add_error("password1", error)
        return datos


class SoloLecturaInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class UsuarioPortalInline(admin.TabularInline):
    model = UsuarioPortal
    extra = 0
    fields = ("nombre", "email", "rol", "usuario")
    raw_id_fields = ("usuario",)
    show_change_link = True
    verbose_name = "Usuario del portal"
    verbose_name_plural = "Usuarios del portal"

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class InstanciaInline(SoloLecturaInline):
    model = InstanciaMoodle
    fields = ("enlace_instancia", "dominio", "version", "estado", "created_at")
    readonly_fields = fields
    verbose_name_plural = "Instancias Moodle"

    @admin.display(description="Instancia")
    def enlace_instancia(self, obj: InstanciaMoodle) -> SafeString:
        url = reverse("admin:instancias_instanciamoodle_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.nombre or f"Instancia {obj.pk}")


class SuscripcionInline(SoloLecturaInline):
    model = Suscripcion
    fields = ("instancia", "plan", "estado", "fecha_inicio")
    readonly_fields = fields
    verbose_name_plural = "Suscripciones"


def _cliente_de_la_ruta(request: HttpRequest) -> int | None:
    """Id del cliente que se está editando, tomado de la URL del admin."""
    ruta = request.resolver_match
    if ruta is None:
        return None
    try:
        return int(ruta.kwargs.get("object_id", ""))
    except (TypeError, ValueError):
        return None


class NuevaSuscripcionForm(forms.ModelForm):
    """Impide asignar a una suscripción el plan negociado de otro cliente."""

    def clean(self) -> dict[str, Any]:
        datos = super().clean() or {}
        plan = datos.get("plan")
        if plan is not None and plan.cliente_id not in (None, self.instance.cliente_id):
            self.add_error(
                "plan",
                "Este plan negociado pertenece a otro cliente. "
                "Elige un plan general o uno de este cliente.",
            )
        return datos


class NuevaSuscripcionInline(admin.TabularInline):
    """Alta de suscripciones desde la ficha del cliente.

    Solo ofrece las instancias del cliente y sus planes (generales o negociados
    con él). No muestra suscripciones existentes: el historial está en el recuadro
    de solo lectura.
    """

    model = Suscripcion
    form = NuevaSuscripcionForm
    extra = 0
    can_delete = False
    fields = ("instancia", "plan", "estado", "fecha_inicio")
    verbose_name = "Nueva suscripción"
    verbose_name_plural = "Agregar suscripción"

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return obj is not None and super().has_add_permission(request, obj)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Suscripcion]:
        return super().get_queryset(request).none()

    def formfield_for_foreignkey(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        cliente_id = _cliente_de_la_ruta(request) or 0
        if db_field.name == "instancia":
            kwargs["queryset"] = InstanciaMoodle.objects.filter(cliente_id=cliente_id)
        elif db_field.name == "plan":
            kwargs["queryset"] = Plan.objects.filter(
                Q(cliente__isnull=True) | Q(cliente_id=cliente_id)
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class AceptacionTerminosInline(SoloLecturaInline):
    model = AceptacionTerminos
    fields = ("version_documento", "fecha_aceptacion", "usuario")
    readonly_fields = fields
    verbose_name_plural = "Aceptaciones de términos y condiciones"


class InstanciasFilter(admin.SimpleListFilter):
    title = "instancias"
    parameter_name = "instancias"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [("si", "Con instancias"), ("no", "Sin instancias")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        if self.value() == "si":
            return queryset.filter(instanciamoodle__isnull=False).distinct()
        if self.value() == "no":
            return queryset.filter(instanciamoodle__isnull=True)
        return queryset


class UsuariosPortalFilter(admin.SimpleListFilter):
    title = "usuarios del portal"
    parameter_name = "usuarios_portal"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [("si", "Con usuarios"), ("no", "Sin usuarios")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        if self.value() == "si":
            return queryset.filter(usuarioportal__isnull=False).distinct()
        if self.value() == "no":
            return queryset.filter(usuarioportal__isnull=True)
        return queryset


class TipoPlanFilter(admin.SimpleListFilter):
    title = "tipo de plan"
    parameter_name = "tipo_plan"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [
            ("mensual", "Mensual"),
            ("anual", "Anual"),
            ("personalizado", "Personalizado (negociado)"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        if self.value():
            return queryset.filter(suscripcion__plan__tipo_plan__iexact=self.value()).distinct()
        return queryset


class EstadoSuscripcionFilter(admin.SimpleListFilter):
    title = "estado de la suscripción"
    parameter_name = "estado_suscripcion"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        estados = (
            Suscripcion.objects.exclude(estado__isnull=True)
            .order_by("estado")
            .values_list("estado", flat=True)
            .distinct()
        )
        return [(estado, estado.capitalize()) for estado in estados if estado]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        if self.value():
            return queryset.filter(suscripcion__estado=self.value()).distinct()
        return queryset


class EstadoAccesoFilter(admin.SimpleListFilter):
    title = "estado de acceso"
    parameter_name = "estado_acceso"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [
            ("activo", "Activo"),
            ("suspendido", "Suspendido"),
            ("sin_usuarios", "Sin usuarios"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        if self.value() == "activo":
            return queryset.filter(usuarioportal__usuario__is_active=True).distinct()
        if self.value() == "suspendido":
            return (
                queryset.filter(usuarioportal__isnull=False)
                .exclude(usuarioportal__usuario__is_active=True)
                .distinct()
            )
        if self.value() == "sin_usuarios":
            return queryset.filter(usuarioportal__isnull=True)
        return queryset


class TerminosFilter(admin.SimpleListFilter):
    title = "términos y condiciones"
    parameter_name = "terminos"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        return [
            ("si", "Aceptó la versión vigente"),
            ("no", "No ha aceptado la versión vigente"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> QuerySet[Cliente]:
        aceptados = AceptacionTerminos.objects.filter(
            version_documento=terminos.VERSION_TERMINOS
        ).values("cliente_id")
        if self.value() == "si":
            return queryset.filter(pk__in=aceptados)
        if self.value() == "no":
            return queryset.exclude(pk__in=aceptados)
        return queryset


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "razon_social",
        "rut_con_puntos",
        "email_contacto",
        "estado_acceso",
        "terminos_aceptados",
        "created_at",
    )
    list_filter = (
        EstadoAccesoFilter,
        TerminosFilter,
        InstanciasFilter,
        UsuariosPortalFilter,
        TipoPlanFilter,
        EstadoSuscripcionFilter,
    )
    search_fields = ("razon_social", "rut", "email_contacto")
    ordering = ("razon_social",)
    actions = ["suspender_clientes", "reactivar_clientes"]
    fieldsets = (
        (
            "Datos de la empresa",
            {
                "fields": (
                    "razon_social",
                    "rut",
                    "giro",
                    "direccion_facturacion",
                    "email_contacto",
                )
            },
        ),
        ("Registro", {"fields": ("created_at",)}),
    )
    inlines = [
        UsuarioPortalInline,
        InstanciaInline,
        SuscripcionInline,
        NuevaSuscripcionInline,
        AceptacionTerminosInline,
    ]

    def get_fieldsets(self, request: HttpRequest, obj: Any = None) -> Any:
        if obj is None:
            return [
                (
                    "Datos de la empresa",
                    {"fields": ("razon_social", "rut", "giro", "direccion_facturacion")},
                ),
                ("Registro", {"fields": ("created_at",)}),
                (
                    "Usuario administrador de la empresa",
                    {
                        "description": (
                            "Este correo también será el correo de contacto de la empresa."
                        ),
                        "fields": ("correo_admin", "password1", "password2"),
                    },
                ),
            ]
        return super().get_fieldsets(request, obj)

    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> Any:
        if obj is None:
            kwargs["form"] = ClienteAltaForm
        form = super().get_form(request, obj, change=change, **kwargs)
        if "created_at" in form.base_fields:
            form.base_fields["created_at"].required = False
        return form

    def get_inline_instances(self, request: HttpRequest, obj: Any = None) -> Any:
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def save_model(self, request: HttpRequest, obj: Cliente, form: Any, change: bool) -> None:
        if not change:
            if obj.created_at is None:
                obj.created_at = timezone.now()
            obj.email_contacto = form.cleaned_data["correo_admin"]
        super().save_model(request, obj, form, change)
        if change:
            return
        correo = form.cleaned_data["correo_admin"]
        usuario = User.objects.create_user(
            username=correo, email=correo, password=form.cleaned_data["password1"]
        )
        grupo, _ = Group.objects.get_or_create(name="Cliente")
        usuario.groups.add(grupo)
        UsuarioPortal.objects.create(usuario=usuario, cliente=obj, email=correo, rol="Admin")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Cliente]:
        return (
            super()
            .get_queryset(request)
            .annotate(
                _usuarios=Count("usuarioportal", distinct=True),
                _usuarios_activos=Count(
                    "usuarioportal",
                    filter=Q(usuarioportal__usuario__is_active=True),
                    distinct=True,
                ),
                _acepto_terminos=Exists(
                    AceptacionTerminos.objects.filter(
                        cliente=OuterRef("pk"), version_documento=terminos.VERSION_TERMINOS
                    )
                ),
            )
        )

    @admin.display(description="RUT", ordering="rut")
    def rut_con_puntos(self, obj: Cliente) -> str:
        return obj.rut_formateado

    @admin.display(description="Acceso")
    def estado_acceso(self, obj: Cliente) -> str:
        usuarios = getattr(obj, "_usuarios", 0)
        activos = getattr(obj, "_usuarios_activos", 0)
        if usuarios == 0:
            return "Sin usuarios"
        return "Activo" if activos else "Suspendido"

    @admin.display(boolean=True, description="Términos aceptados")
    def terminos_aceptados(self, obj: Cliente) -> bool:
        return bool(getattr(obj, "_acepto_terminos", False))

    @admin.action(description="Suspender clientes seleccionados")
    def suspender_clientes(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> None:
        self._cambiar_acceso(request, queryset, activo=False)

    @admin.action(description="Reactivar clientes seleccionados")
    def reactivar_clientes(self, request: HttpRequest, queryset: QuerySet[Cliente]) -> None:
        self._cambiar_acceso(request, queryset, activo=True)

    def _cambiar_acceso(
        self, request: HttpRequest, queryset: QuerySet[Cliente], activo: bool
    ) -> None:
        usuario_model = get_user_model()
        verbo = "reactivó" if activo else "suspendió"
        cambiados = 0
        sin_usuarios: list[str] = []
        for cliente in queryset:
            usuarios = usuario_model.objects.filter(usuarioportal__cliente=cliente).exclude(
                is_staff=True
            )
            cantidad = usuarios.update(is_active=activo)
            if cantidad == 0:
                sin_usuarios.append(cliente.razon_social or f"Cliente {cliente.pk}")
                continue
            cambiados += 1
            self.log_change(
                request,
                cliente,
                f"Acceso {'reactivado' if activo else 'suspendido'}: "
                f"{cantidad} usuario(s) del portal.",
            )
        if cambiados:
            self.message_user(
                request, f"Se {verbo} el acceso de {cambiados} cliente(s).", messages.SUCCESS
            )
        if sin_usuarios:
            self.message_user(
                request,
                "Sin usuarios del portal, no se pudo cambiar: " + ", ".join(sin_usuarios),
                messages.WARNING,
            )


@admin.register(UsuarioPortal)
class UsuarioPortalAdmin(admin.ModelAdmin):
    list_display = ("nombre_visible", "email", "rol", "enlace_cliente", "cuenta_activa")
    list_select_related = ("cliente", "usuario")
    list_filter = ("rol", "cliente")

    search_fields = (
        "nombre",
        "email",
        "usuario__username",
        "cliente__razon_social",
        "cliente__rut",
    )
    ordering = ("cliente__razon_social", "nombre")
    raw_id_fields = ("usuario",)

    @admin.display(description="Cliente", ordering="cliente__razon_social")
    def enlace_cliente(self, obj: UsuarioPortal) -> str | SafeString:
        cliente = obj.cliente
        if cliente is None:
            return "—"
        url = reverse("admin:clientes_cliente_change", args=[cliente.pk])
        return format_html('<a href="{}">{}</a>', url, cliente)

    @admin.display(boolean=True, description="Cuenta activa", ordering="usuario__is_active")
    def cuenta_activa(self, obj: UsuarioPortal) -> bool:
        return bool(obj.usuario and obj.usuario.is_active)

    @admin.display(description="Nombre", ordering="nombre")
    def nombre_visible(self, obj: UsuarioPortal) -> str:
        return obj.nombre or (obj.usuario.username if obj.usuario else "—")


admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    """Los usuarios se crean junto a su cliente; aquí solo se editan."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
