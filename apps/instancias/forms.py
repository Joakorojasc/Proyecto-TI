import re
from typing import Any

from django import forms
from django.db.models import Q

from apps.planes.forms import PlanChoiceField
from apps.planes.models import Plan, Suscripcion

from .models import EstadoInstancia, InstanciaMoodle

DOMINIO_BASE_EDOCERE = "edocere.com"
SUBDOMINIO_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
DOMINIO_PROPIO_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


class CrearInstanciaForm(forms.ModelForm):
    TIPO_EDOCERE = "edocere"
    TIPO_PROPIO = "propio"

    nombre = forms.CharField(
        label="Nombre de la instancia",
        help_text="Cómo quieres identificar esta instancia, por ejemplo: Campus Corporativo.",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Campus Corporativo"}),
    )
    tipo_dominio = forms.ChoiceField(
        label="Dirección web de la instancia",
        choices=[
            (TIPO_EDOCERE, "Usar una dirección de Edocere (recomendado)"),
            (TIPO_PROPIO, "Usar mi propio dominio"),
        ],
        initial=TIPO_EDOCERE,
        widget=forms.RadioSelect,
    )
    subdominio = forms.CharField(
        label="Nombre para tu dirección",
        help_text="Escribe solo un nombre corto, por ejemplo: duoc",
        required=False,
        max_length=63,
        widget=forms.TextInput(attrs={"placeholder": "duoc"}),
    )
    dominio_propio = forms.CharField(
        label="Tu dominio",
        help_text=(
            "Sin https://, por ejemplo: aula.duoc.cl. "
            "Después de crear la instancia te indicaremos cómo configurarlo."
        ),
        required=False,
        max_length=253,
        widget=forms.TextInput(attrs={"placeholder": "aula.duoc.cl"}),
    )
    logo_url = forms.URLField(
        label="URL del logo",
        help_text="Campo opcional. Incluye el protocolo de la URL.",
        max_length=2048,
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://empresa.cl/logo.png"}),
    )

    class Meta:
        model = InstanciaMoodle
        fields = ("nombre", "logo_url")

    field_order = ["nombre", "tipo_dominio", "subdominio", "dominio_propio", "logo_url"]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        tipo = cleaned.get("tipo_dominio")

        if tipo == self.TIPO_EDOCERE:
            campo = "subdominio"
            sub = (cleaned.get("subdominio") or "").strip().lower()
            if not SUBDOMINIO_RE.match(sub):
                self.add_error(
                    campo,
                    "Usa entre 3 y 63 caracteres: minúsculas, números y guiones, "
                    "sin empezar ni terminar con guion.",
                )
                return cleaned
            host = f"{sub}.{DOMINIO_BASE_EDOCERE}"
        elif tipo == self.TIPO_PROPIO:
            campo = "dominio_propio"
            host = (cleaned.get("dominio_propio") or "").strip().lower()
            host = re.sub(r"^https?://", "", host).rstrip("/")
            if not DOMINIO_PROPIO_RE.match(host):
                self.add_error(campo, "Ingresa un dominio válido, por ejemplo aula.duoc.cl.")
                return cleaned
            if host == DOMINIO_BASE_EDOCERE or host.endswith(f".{DOMINIO_BASE_EDOCERE}"):
                self.add_error(
                    campo,
                    "Ese dominio es de Edocere. Elige la opción de dirección de Edocere.",
                )
                return cleaned
        else:
            return cleaned

        dominio = f"https://{host}"
        if InstanciaMoodle.objects.filter(
            Q(dominio__iexact=dominio) | Q(dominio__iexact=host)
        ).exists():
            self.add_error(campo, "Ese dominio ya está en uso. Elige otro.")
            return cleaned

        cleaned["dominio_final"] = dominio
        return cleaned

    def save(self, commit: bool = True) -> InstanciaMoodle:
        instancia = super().save(commit=False)
        instancia.dominio = self.cleaned_data["dominio_final"]
        if commit:
            instancia.save()
        return instancia


class EditarInstanciaForm(forms.ModelForm):
    PLAN_BLOCKS = {
        "mensual": {
            "key": "Mensual",
            "title": "Planes mensuales",
            "description": "Ideal para equipos que requieren pagar mes a mes.",
        },
        "anual": {
            "key": "Anual",
            "title": "Planes anuales",
            "description": "Ahorra con pagos anuales con precios al por mayor.",
        },
        "personalizado": {
            "key": "Personalizado",
            "title": "Plan personalizado",
            "description": "Planes personalizados disponibles para tu institución.",
        },
    }

    nombre = forms.CharField(
        label="Nombre de la instancia",
        help_text="Cómo quieres identificar esta instancia, por ejemplo: Campus Corporativo.",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Campus Corporativo"}),
    )
    plan = PlanChoiceField(
        queryset=Plan.objects.none(),
        label="Plan de suscripción",
        required=False,
        empty_label=None,
        widget=forms.RadioSelect,
    )
    confirmacion_contrasena = forms.CharField(
        label="Contraseña de tu cuenta",
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "id": "id_confirmacion_contrasena"}
        ),
    )
    logo_url = forms.URLField(
        label="URL del logo",
        help_text="Campo opcional. Incluye el protocolo de la URL.",
        max_length=2048,
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://empresa.cl/logo.png"}),
    )

    class Meta:
        model = InstanciaMoodle
        fields = ("nombre", "logo_url", "estado")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        instancia = self.instance
        planes = Plan.objects.none()
        if instancia.pk:
            planes = Plan.objects.filter(
                Q(tipo_plan__iexact="mensual")
                | Q(tipo_plan__iexact="anual")
                | Q(cliente_id=instancia.cliente_id)
            ).order_by("tipo_plan", "precio_base")
            suscripciones_activas = Suscripcion.objects.filter(
                instancia=instancia,
                estado="activa",
            )
            if suscripciones_activas.count() == 1:
                self.initial["plan"] = suscripciones_activas.get().plan_id

        plan_field = self.fields["plan"]
        assert isinstance(plan_field, forms.ModelChoiceField)
        plan_field.queryset = planes
        self.plan_sections = self._build_plan_sections(planes, instancia.cliente_id)

    def _build_plan_sections(self, planes: Any, cliente_id: int) -> list[dict[str, Any]]:
        planes_lista = list(planes)
        agrupados: dict[str, list[Plan]] = {
            "mensual": [],
            "anual": [],
            "personalizado": [],
        }
        for plan in planes_lista:
            tipo_plan = (plan.tipo_plan or "").lower()
            if tipo_plan in ("mensual", "anual"):
                agrupados[tipo_plan].append(plan)
            elif plan.cliente_id == cliente_id:
                agrupados["personalizado"].append(plan)

        return [
            {
                **config,
                "plans": agrupados[key],
            }
            for key, config in self.PLAN_BLOCKS.items()
        ]

    def clean_confirmacion_contrasena(self) -> str:
        contrasena = self.cleaned_data["confirmacion_contrasena"]
        if not contrasena:
            raise forms.ValidationError("Ingresa tu contraseña para confirmar los cambios.")
        return contrasena


class FiltroInstanciasForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=255,
        label="Buscar",
        widget=forms.TextInput(attrs={"placeholder": "Buscar por nombre"}),
    )
    estado = forms.ChoiceField(
        required=False,
        label="Estado",
        choices=[("", "Todos los estados"), *EstadoInstancia.choices],
    )
    orden = forms.ChoiceField(
        required=False,
        label="Orden",
        choices=[
            ("", "Más antiguas primero"),
            ("recientes", "Más recientes primero"),
            ("nombre_asc", "Nombre A-Z"),
            ("nombre_desc", "Nombre Z-A"),
        ],
    )
