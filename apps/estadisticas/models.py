from django.db import models


class MedicionUsoMensual(models.Model):
    id = models.AutoField(primary_key=True)
    instancia = models.ForeignKey(
        "instancias.InstanciaMoodle",
        on_delete=models.PROTECT,
    )
    mes = models.IntegerField(null=True)
    anio = models.IntegerField(null=True)
    usuarios_activos = models.IntegerField(null=True)
    cantidad_cursos = models.IntegerField(null=True)
    cantidad_categorias = models.IntegerField(null=True)
