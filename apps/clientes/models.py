from typing import Any

from django.conf import settings
from django.db import models

from .validators import RUT_DUPLICADO, formatear_rut, normalizar_rut, validar_rut


class ClienteManager(models.Manager["Cliente"]):
    def por_rut(self, rut: str) -> "Cliente":
        """Busca por RUT venga con puntos o sin ellos."""
        return self.get(rut=normalizar_rut(rut))


class Cliente(models.Model):
    id = models.AutoField(primary_key=True)
    rut = models.CharField(
        "RUT",
        max_length=255,
        null=True,
        unique=True,
        validators=[validar_rut],
        error_messages={"unique": RUT_DUPLICADO},
    )
    razon_social = models.CharField(max_length=255, null=True)
    giro = models.CharField(max_length=255, null=True)
    direccion_facturacion = models.CharField(max_length=255, null=True)
    email_contacto = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(null=True)

    objects = ClienteManager()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        # Conserva los clientes sin RUT; no guarda cadenas vacías como identificadores.
        if self.rut is not None:
            self.rut = normalizar_rut(self.rut) if self.rut.strip() else None

    @property
    def rut_formateado(self) -> str:
        """El RUT con puntos para mostrarlo, sin cambiar el valor almacenado."""
        return formatear_rut(self.rut) if self.rut else ""


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


class AceptacionTerminos(models.Model):
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="aceptaciones_terminos"
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    version_documento = models.CharField(max_length=80)
    fecha_aceptacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cliente", "version_documento"], name="aceptacion_cliente_version_unica"
            ),
        ]
