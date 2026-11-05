from typing import Any

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html

from . import terminos
from .models import Cliente
from .validators import normalizar_rut


class AceptacionTerminosForm(forms.Form):
    acepta_terminos = forms.BooleanField(
        label="He leído y acepto los términos y condiciones de Edocere.",
        required=True,
        widget=forms.CheckboxInput(
            attrs={"style": "width: auto; padding: 0; align-self: flex-start;"}
        ),
        error_messages={"required": "Debes aceptar los términos y condiciones para continuar."},
    )
    version_terminos = forms.CharField(
        max_length=80, widget=forms.HiddenInput, validators=[terminos.validar_version_terminos]
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["version_terminos"].initial = terminos.VERSION_TERMINOS
        self.fields["acepta_terminos"].help_text = format_html(
            '<a href="{}" target="_blank" rel="noopener">Leer el documento completo '
            "de términos y condiciones (PDF, se abre en otra pestaña)</a>.",
            reverse("documento_terminos", kwargs={"version": terminos.VERSION_TERMINOS}),
        )

    def clean_acepta_terminos(self) -> bool:
        # CheckboxInput considera verdadero cualquier texto no vacío. Exigimos
        # un valor afirmativo explícito, no valores como "0", "no" u "off".
        valor = self.data.get(self.add_prefix("acepta_terminos"))
        if valor not in (True, "on", "true", "True", "1"):
            raise forms.ValidationError(
                self.fields["acepta_terminos"].error_messages["required"], code="required"
            )
        return True


class RutInstitucionForm(forms.ModelForm, AceptacionTerminosForm):
    rut = forms.CharField(label="RUT de la institución", max_length=255)

    def clean_rut(self) -> str:
        return normalizar_rut(self.cleaned_data["rut"])


class RegistroClienteForm(RutInstitucionForm):
    class Meta:
        model = Cliente
        fields = ["rut", "razon_social", "giro", "direccion_facturacion", "email_contacto"]


class EmpresaRegistroForm(RutInstitucionForm):
    class Meta:
        model = Cliente
        fields = ["razon_social", "rut"]
        labels = {"razon_social": "Nombre de la Institución"}


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
