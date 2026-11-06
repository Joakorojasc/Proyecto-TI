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
    usuarios_inscritos = models.IntegerField(null=True)
    # Matrículas de estudiantes sumando todos los cursos: un alumno en dos cursos
    # cuenta dos veces. De acá sale el promedio por curso, que no se puede deducir
    # de los usuarios activos.
    total_matriculas = models.IntegerField(null=True)
