from typing import Any

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

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


class PerfilInstitucionForm(forms.ModelForm):
    email_contacto = forms.EmailField(
        label="Correo electrónico de contacto",
        max_length=255,
        required=False,
        error_messages={"invalid": "Ingresa un correo electrónico válido."},
    )
    confirmacion_contrasena = forms.CharField(
        label="Contraseña de tu cuenta",
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "id": "id_confirmacion_contrasena"}
        ),
    )

    class Meta:
        model = Cliente
        fields = ("razon_social", "giro", "direccion_facturacion", "email_contacto")
        labels = {
            "razon_social": "Nombre de la Institución",
            "giro": "Giro",
            "direccion_facturacion": "Dirección de facturación",
        }

    def clean_confirmacion_contrasena(self) -> str:
        contrasena = self.cleaned_data["confirmacion_contrasena"]
        if not contrasena:
            raise forms.ValidationError("Ingresa tu contraseña para confirmar los cambios.")
        return contrasena


class UsuarioRegistroForm(UserCreationForm):
    # El campo se llama "username" porque Django lo usa para iniciar sesión,
    # pero aquí la persona escribe su correo.
    username = forms.EmailField(
        label="Correo electrónico",
        help_text="Con este correo vas a iniciar sesión.",
        max_length=150,
        widget=forms.EmailInput(attrs={"placeholder": "nombre@empresa.cl"}),
    )

    def clean_username(self) -> str:
        correo: str = self.cleaned_data["username"].strip().lower()
        if User.objects.filter(username__iexact=correo).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def save(self, commit: bool = True) -> User:
        user: User = super().save(commit=False)
        user.email = user.username
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Correo electrónico"
