from django import forms

from .models import InstanciaMoodle


class CrearInstanciaForm(forms.ModelForm):
    dominio = forms.URLField(
        label="URL del dominio de la instancia",
        help_text="Incluye el protocolo, por ejemplo https://aula.empresa.cl.",
        max_length=2048,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://aula.empresa.cl"}),
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
        fields = ("dominio", "logo_url")
