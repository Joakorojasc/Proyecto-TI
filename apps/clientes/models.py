from django.conf import settings
from django.db import models

from .validators import formatear_rut, normalizar_rut, validar_rut


class ClienteManager(models.Manager["Cliente"]):
    def por_rut(self, rut: str) -> "Cliente":
        """Busca por RUT venga con puntos o sin ellos.

        En la base el RUT se guarda normalizado, así que buscarlo tal como
        lo escribió la persona no encuentra nada.
        """
        return self.get(rut=normalizar_rut(rut))


class Cliente(models.Model):
    id = models.AutoField(primary_key=True)
    rut = models.CharField(
        "RUT",
        max_length=12,
        unique=True,
        validators=[validar_rut],
        error_messages={
            "unique": (
                "Esta institución ya está registrada. Si trabajas ahí, "
                "pídele acceso al administrador de la cuenta."
            )
        },
    )
    razon_social = models.CharField(max_length=255, null=True)
    giro = models.CharField(max_length=255, null=True)
    direccion_facturacion = models.CharField(max_length=255, null=True)
    email_contacto = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField(null=True)

    objects = ClienteManager()

    def save(self, *args: object, **kwargs: object) -> None:
        if self.rut:
            self.rut = normalizar_rut(self.rut)
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def clean(self) -> None:
        super().clean()
        if self.rut:
            self.rut = normalizar_rut(self.rut)

    @property
    def rut_formateado(self) -> str:
        """El RUT con puntos, para mostrarlo. En la base se guarda sin ellos."""
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
