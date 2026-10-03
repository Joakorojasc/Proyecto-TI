from django.db import models


class InstanciaMoodle(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
    )
    dominio = models.URLField(max_length=2048, null=True)
    logo_url = models.URLField(max_length=2048, blank=True, null=True)
    version = models.CharField(max_length=255, null=True)
    estado = models.CharField(max_length=255, null=True)
