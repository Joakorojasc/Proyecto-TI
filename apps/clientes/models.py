from django.db import models


class Cliente(models.Model):
	id = models.AutoField(primary_key=True)
	rut = models.CharField(max_length=255, null=True)
	razon_social = models.CharField(max_length=255, null=True)
	giro = models.CharField(max_length=255, null=True)
	direccion_facturacion = models.CharField(max_length=255, null=True)
	email_contacto = models.CharField(max_length=255, null=True)
	created_at = models.DateTimeField(null=True)


class UsuarioPortal(models.Model):
	id = models.AutoField(primary_key=True)
	cliente = models.ForeignKey(
		"clientes.Cliente",
		on_delete=models.SET_NULL,
		null=True,
	)
	nombre = models.CharField(max_length=255, null=True)
	email = models.CharField(max_length=255, null=True)
	rol = models.CharField(max_length=255, null=True)
