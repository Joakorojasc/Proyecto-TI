from django import forms

from .models import Cliente


class EmpresaRegistroForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['razon_social', 'rut']
        labels = {
            'razon_social': 'Nombre de la Institución',
            'rut': 'RUT de la Institución'
        }