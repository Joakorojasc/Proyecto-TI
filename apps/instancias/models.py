from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.db import models

from .consumo import ConsumoUsuarios, calcular_consumo

if TYPE_CHECKING:
    from apps.estadisticas.models import MedicionUsoMensual
    from apps.planes.models import Suscripcion


class EstadoInstancia(models.TextChoices):
    ACTIVA = "activa", "Activa"
    ARCHIVADA = "archivada", "Archivada"


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
        max_length=255,
        null=True,
        choices=EstadoInstancia.choices,
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

    @property
    def consumo_usuarios(self) -> ConsumoUsuarios:
        """Usa los datos precargados por con_datos_consumo."""
        mediciones: list[MedicionUsoMensual] = self.__dict__["mediciones_consumo"]
        suscripciones: list[Suscripcion] = self.__dict__["suscripciones_activas"]
        return calcular_consumo(mediciones[0] if mediciones else None, suscripciones)
