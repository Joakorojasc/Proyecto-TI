from django import forms

from .models import Cliente


class RegistroClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['rut', 'razon_social', 'contacto', 'direccion']