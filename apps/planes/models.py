from django.core.exceptions import ValidationError
from django.db import models


class Plan(models.Model):
    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255, null=True)
    tipo_plan = models.CharField(max_length=255, null=True)
    precio_base = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    precio_por_usuario = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    limite_usuarios = models.IntegerField(null=True)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planes",
    )

    def __str__(self) -> str:
        return self.display_label()

    def display_label(self) -> str:
        precio = self.precio_base if self.precio_base is not None else 0
        precio_unitario = self.precio_por_usuario if self.precio_por_usuario is not None else 0
        tipo = self.tipo_plan or "Plan"
        if self.tipo_plan == "mensual":
            return f"{self.nombre} · ${precio_unitario:,.2f}/usuario/mes"
        elif self.tipo_plan == "anual":
            return f"{self.nombre} · ${precio:,.0f}/año"
        elif self.tipo_plan and self.tipo_plan.lower() == "personalizado":
            return f"{self.nombre} · Valores a convenir"
        return self.nombre or tipo


class Suscripcion(models.Model):
    id = models.AutoField(primary_key=True)
    instancia = models.ForeignKey(
        "instancias.InstanciaMoodle",
        on_delete=models.PROTECT,
        related_name="suscripciones",
        null=True,
        blank=True,
    )
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
    )
    plan = models.ForeignKey(
        "planes.Plan",
        on_delete=models.PROTECT,
    )
    estado = models.CharField(max_length=255, null=True)
    fecha_inicio = models.DateTimeField(null=True)

    def clean(self) -> None:
        super().clean()
        if self.instancia is not None and self.cliente_id != self.instancia.cliente_id:
            raise ValidationError(
                "La suscripción y la instancia deben pertenecer al mismo cliente."
            )
