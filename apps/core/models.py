from django.db import models


class Bitacora(models.Model):
	id = models.AutoField(primary_key=True)
	usuario = models.ForeignKey(
		"clientes.UsuarioPortal",
		on_delete=models.PROTECT,
	)
	accion = models.TextField(null=True)
	created_at = models.DateTimeField(null=True)
