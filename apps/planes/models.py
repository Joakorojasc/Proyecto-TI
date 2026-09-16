from django.db import models


class Plan(models.Model):
	id = models.AutoField(primary_key=True)
	nombre = models.CharField(max_length=255, null=True)
	tipo_plan = models.CharField(max_length=255, null=True)
	precio_base = models.DecimalField(max_digits=12, decimal_places=2, null=True)
	precio_por_usuario = models.DecimalField(max_digits=12, decimal_places=2, null=True)
	limite_usuarios = models.IntegerField(null=True)


class Suscripcion(models.Model):
	id = models.AutoField(primary_key=True)
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
