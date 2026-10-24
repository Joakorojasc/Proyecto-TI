"""Une las historias y actualiza bases migradas desde cualquiera de las dos."""

from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

import apps.clientes.validators as validadores

from ._rut_data import normalizar_ruts


def campo_rut():
    return models.CharField(
        "RUT", max_length=255, null=True, unique=True,
        validators=[validadores.validar_rut],
        error_messages={"unique": validadores.RUT_DUPLICADO},
    )


def alinear_esquema(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Cliente = apps.get_model("clientes", "Cliente")
    nuevo = campo_rut()
    nuevo.set_attributes_from_name("rut")
    nuevo.model = Cliente
    anterior = nuevo.clone()
    anterior.set_attributes_from_name("rut")
    anterior.model = Cliente
    # Lee el esquema físico: una base puede tener la versión original de dev
    # (NOT NULL, longitud 12) aunque el archivo histórico ahora esté corregido.
    # No se fuerza temporalmente NOT NULL sobre bases que ya contienen nulos.
    with schema_editor.connection.cursor() as cursor:
        columnas = schema_editor.connection.introspection.get_table_description(
            cursor, Cliente._meta.db_table
        )
    columna = next(campo for campo in columnas if campo.name == "rut")
    anterior.max_length = columna.internal_size or nuevo.max_length
    anterior.null = columna.null_ok
    schema_editor.alter_field(Cliente, anterior, nuevo)


class Migration(migrations.Migration):
    atomic = False  # MariaDB no revierte DDL; la conversión de datos sí es atómica.
    dependencies = [
        ("clientes", "0003_rut_validado_y_unico"),
        ("clientes", "0004_rut_unico"),
    ]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(alinear_esquema, migrations.RunPython.noop, atomic=False),
            ],
            state_operations=[
                migrations.AlterField(model_name="cliente", name="rut", field=campo_rut()),
            ],
        ),
        migrations.RunPython(normalizar_ruts, migrations.RunPython.noop, atomic=True),
    ]
