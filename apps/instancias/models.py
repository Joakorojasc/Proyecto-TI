from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import uuid4

from django.db import models

from .consumo import ConsumoUsuarios, calcular_consumo

if TYPE_CHECKING:
    from apps.estadisticas.models import MedicionUsoMensual
    from apps.planes.models import Suscripcion


class EstadoInstancia(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    ACTIVE = "ACTIVE", "Activa"
    FAILED = "FAILED", "Fallida"
    DEPROVISIONED = "DEPROVISIONED", "Desaprovisionada"
    SUSPENDED = "SUSPENDED", "Suspendida"
    RECOVERING = "RECOVERING", "En recuperación"
    RECOVERY_FAILED = "RECOVERY_FAILED", "Recuperación fallida"
    RESTORING = "RESTORING", "Restaurando"
    RESTORE_FAILED = "RESTORE_FAILED", "Restauración fallida"
    PURGING = "PURGING", "Eliminando"
    PURGE_FAILED = "PURGE_FAILED", "Eliminación fallida"
    PURGED = "PURGED", "Eliminada permanentemente"


class TipoOperacion(models.TextChoices):
    PROVISION = "PROVISION", "Provision"
    DEPROVISION = "DEPROVISION", "Deprovision"
    BACKUP = "BACKUP", "Backup"
    RESTORE = "RESTORE", "Restore"
    CLONE = "CLONE", "Clone"
    SUSPEND = "SUSPEND", "Suspend"
    REACTIVATE = "REACTIVATE", "Reactivate"
    RECOVER = "RECOVER", "Recover"
    UPDATE_BRANDING = "UPDATE_BRANDING", "Update branding"


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
        default=EstadoInstancia.PENDING,
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
    def clase_estado(self) -> str:
        """Sufijo CSS de la píldora de estado, en minúsculas y con guiones.

        El estado se guarda como RECOVERY_FAILED y el CSS se escribe
        recovery-failed. Pasa por acá para que un estado nuevo no quede sin
        color por una diferencia de formato.
        """
        return (self.estado or "sin-estado").lower().replace("_", "-")

    @property
    def es_subdominio_edocere(self) -> bool:
        return self.dominio_host.endswith(".edocere.com")

    @property
    def consumo_usuarios(self) -> ConsumoUsuarios:
        """Usa los datos precargados por con_datos_consumo."""
        mediciones: list[MedicionUsoMensual] = self.__dict__["mediciones_consumo"]
        suscripciones: list[Suscripcion] = self.__dict__["suscripciones_activas"]
        return calcular_consumo(mediciones[0] if mediciones else None, suscripciones)


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
