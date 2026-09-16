from django.db import models


class Pago(models.Model):
    id = models.AutoField(primary_key=True)
    suscripcion = models.ForeignKey(
        "planes.Suscripcion",
        on_delete=models.PROTECT,
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    fecha_pago = models.DateTimeField(null=True)
    estado = models.CharField(max_length=255, null=True)


class DocumentoTributario(models.Model):
    id = models.AutoField(primary_key=True)
    pago = models.OneToOneField(
        "pagos.Pago",
        on_delete=models.PROTECT,
    )
    tipo_documento = models.CharField(max_length=255, null=True)
    folio = models.IntegerField(null=True)
    url_pdf = models.CharField(max_length=255, null=True)
