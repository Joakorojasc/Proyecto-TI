"""Política provisional basada en los valores predeterminados de Moodle.

Edocere debe confirmar la configuración definitiva de sus instancias:
https://docs.moodle.org/503/en/report/security/report_security_check_passwordpolicy
Solo valida contraseñas del portal; no sincroniza credenciales con Moodle.
"""

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError


class MoodlePasswordValidator:
    def validate(self, password: str, user: AbstractBaseUser | None = None) -> None:
        # La longitud se valida por separado con MinimumLengthValidator de Django.
        requisitos = (
            (any(c.isupper() for c in password), "una letra mayúscula", "password_no_upper"),
            (any(c.islower() for c in password), "una letra minúscula", "password_no_lower"),
            (any(c.isdecimal() for c in password), "un número", "password_no_digit"),
            (
                any(not c.isalnum() for c in password),
                "un carácter especial (por ejemplo, !, @, # o .)",
                "password_no_special",
            ),
        )
        errores = [
            ValidationError(f"Tu contraseña debe incluir al menos {descripcion}.", code=codigo)
            for cumple, descripcion, codigo in requisitos
            if not cumple
        ]
        if errores:
            raise ValidationError(errores)

    def get_help_text(self) -> str:
        return (
            "Tu contraseña debe incluir al menos una mayúscula, una minúscula, "
            "un número y un carácter especial (por ejemplo, !, @, # o .)."
        )
