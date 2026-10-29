from django.db import models


class MedioPago(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="medios_pago",
    )
    ultimos_4_digitos = models.CharField(max_length=4)
    marca_tarjeta = models.CharField(max_length=50)
    token_simulado = models.CharField(max_length=255, unique=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.marca_tarjeta} terminada en {self.ultimos_4_digitos}"


class Pago(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_APROBADO = "aprobado"
    ESTADO_RECHAZADO = "rechazado"
    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_APROBADO, "Aprobado"),
        (ESTADO_RECHAZADO, "Rechazado"),
    )

    id = models.AutoField(primary_key=True)
    suscripcion = models.ForeignKey(
        "planes.Suscripcion",
        on_delete=models.PROTECT,
    )
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    fecha_pago = models.DateTimeField(null=True)
    estado = models.CharField(max_length=255, choices=ESTADOS, null=True)


class DocumentoTributario(models.Model):
    id = models.AutoField(primary_key=True)
    pago = models.OneToOneField(
        "pagos.Pago",
        on_delete=models.PROTECT,
    )
    tipo_documento = models.CharField(max_length=255, null=True)
    folio = models.IntegerField(null=True)
    url_pdf = models.CharField(max_length=255, null=True)
