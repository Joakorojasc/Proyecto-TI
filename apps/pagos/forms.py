from django import forms


class CheckoutSimuladoForm(forms.Form):
    ultimos_4_digitos = forms.CharField(
        label="Últimos 4 dígitos",
        min_length=4,
        max_length=4,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )
    marca_tarjeta = forms.CharField(
        label="Marca de tarjeta",
        max_length=50,
    )
    token_simulado = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.HiddenInput,
    )

    def clean_ultimos_4_digitos(self) -> str:
        value = self.cleaned_data["ultimos_4_digitos"]
        if not value.isdigit():
            raise forms.ValidationError("Ingresa solo números.")
        return value
