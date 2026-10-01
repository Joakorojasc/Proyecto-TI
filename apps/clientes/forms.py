from django import forms

from .models import Cliente


class RegistroClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["rut", "razon_social", "giro", "direccion_facturacion", "email_contacto"]


class EmpresaRegistroForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["razon_social", "rut"]
        labels = {"razon_social": "Nombre de la Institución", "rut": "RUT de la Institución"}
