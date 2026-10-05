import re
from typing import Any

from django import forms
from django.db.models import Q

from .models import InstanciaMoodle

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
