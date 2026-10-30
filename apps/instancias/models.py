from urllib.parse import urlparse
from uuid import uuid4

from django.db import models


class EstadoInstancia(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente de aprovisionamiento"
    ACTIVA = "activa", "Activa"
    ARCHIVADA = "archivada", "Archivada"


class EstadoAprovisionamiento(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    EN_PROCESO = "en_proceso", "En proceso"
    ACTIVA = "activa", "Activa"
    FALLIDA = "fallida", "Fallida"


class InstanciaMoodle(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
    )
    nombre = models.CharField(max_length=255, null=True, blank=True)
    dominio = models.URLField(max_length=2048, null=True)
    logo_url = models.URLField(max_length=2048, blank=True, null=True)
    version = models.CharField(max_length=255, null=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoInstancia.choices,
        default=EstadoInstancia.PENDIENTE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.nombre or self.dominio_host or f"Instancia {self.pk}"

    @property
    def dominio_host(self) -> str:
        """Dominio sin esquema (https://). Los datos vienen con y sin esquema."""
        if not self.dominio:
            return ""
        url = self.dominio if "//" in self.dominio else f"//{self.dominio}"
        return urlparse(url).hostname or ""

    @property
    def es_subdominio_edocere(self) -> bool:
        return self.dominio_host.endswith(".edocere.com")


class SolicitudAprovisionamiento(models.Model):
    instancia = models.ForeignKey(
        InstanciaMoodle,
        on_delete=models.PROTECT,
        related_name="solicitudes_aprovisionamiento",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoAprovisionamiento.choices,
        default=EstadoAprovisionamiento.PENDIENTE,
    )
    operation_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        default=uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"Aprovisionamiento de instancia {self.instancia_id} ({self.estado})"
