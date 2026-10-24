"""Ruta histórica de dev, compatible con los clientes antiguos sin RUT.

Se conserva su nombre para reconocer bases donde ya fue aplicada. La revisión
previa evita escrituras parciales en instalaciones nuevas; 0005 alinea las
bases que aplicaron la versión anterior con NOT NULL y longitud 12.
"""

from django.db import migrations, models

import apps.clientes.validators as validadores

from ._rut_data import normalizar_ruts


class Migration(migrations.Migration):
    dependencies = [("clientes", "0002_usuarioportal_usuario")]

    operations = [
        migrations.RunPython(normalizar_ruts, migrations.RunPython.noop, atomic=True),
        migrations.AlterField(
            model_name="cliente",
            name="rut",
            field=models.CharField(
                "RUT", max_length=255, null=True, unique=True,
                validators=[validadores.validar_rut],
                error_messages={"unique": validadores.RUT_DUPLICADO},
            ),
        ),
    ]
