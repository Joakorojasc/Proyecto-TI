from typing import Any

from django.conf import settings
from django.db import models

from .validators import RUT_DUPLICADO, normalizar_rut


class Cliente(models.Model):
    id = models.AutoField(primary_key=True)
    rut = models.CharField(
        max_length=255, null=True, unique=True, error_messages={"unique": RUT_DUPLICADO}
    )
    razon_social = models.CharField(max_length=255, null=True)
    giro = models.CharField(max_length=255, null=True)
    direccion_facturacion = models.CharField(max_length=255, null=True)
    email_contacto = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(null=True)

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Conserva los clientes sin RUT; no guarda cadenas vacías como identificadores.
        if self.rut is not None:
            self.rut = normalizar_rut(self.rut) if self.rut.strip() else None


class UsuarioPortal(models.Model):
    id = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usuarioportal",
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.SET_NULL,
        null=True,
    )
    nombre = models.CharField(max_length=255, null=True)
    email = models.CharField(max_length=255, null=True)
    rol = models.CharField(max_length=255, null=True)
