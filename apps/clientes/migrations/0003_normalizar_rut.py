from django.apps.registry import Apps
from django.core.exceptions import ValidationError
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from apps.clientes.validators import normalizar_rut


def normalizar_ruts(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Revisa todos los registros antes de escribir; nunca fusiona clientes."""
    Cliente = apps.get_model("clientes", "Cliente")
    clientes = Cliente.objects.using(schema_editor.connection.alias)
    # Identificadores exactos del seed histórico. No se cambian IDs ni relaciones.
    demo = {
        "DEMO-PEQUENO-001": "90000001-4",
        "DEMO-MEDIANO-001": "90000002-2",
        "DEMO-ANUAL-001": "90000003-0",
    }
    cambios: list[tuple[int, str | None]] = []
    identificadores: dict[str, list[int]] = {}
    errores: list[str] = []
    for pk, rut in clientes.order_by("pk").values_list("pk", "rut"):
        if rut is None or not rut.strip():
            nuevo = None
        else:
            try:
                nuevo = normalizar_rut(demo.get(rut, rut.strip()))
            except ValidationError:
                errores.append(f"Cliente ID {pk}: RUT inválido")
                continue
            identificadores.setdefault(nuevo, []).append(pk)
        if nuevo != rut:
            cambios.append((pk, nuevo))

    for ids in identificadores.values():
        if len(ids) > 1:
            errores.append(f"RUT equivalente en clientes IDs {ids}")
    if errores:
        raise RuntimeError(
            "No se modificó ningún cliente. Corrige los RUT con los responsables de los datos "
            "y vuelve a ejecutar migrate; no elimines ni fusiones empresas automáticamente. "
            + "; ".join(errores)
        )

    for pk, rut in cambios:
        clientes.filter(pk=pk).update(rut=rut)


class Migration(migrations.Migration):
    dependencies = [("clientes", "0002_usuarioportal_usuario")]

    operations = [
        # La transacción de datos también se exige en MariaDB. La restricción va
        # en otra migración porque MariaDB no permite revertir DDL con rollback.
        # Revertir conserva el RUT canónico: no se puede recuperar su puntuación.
        migrations.RunPython(normalizar_ruts, migrations.RunPython.noop, atomic=True),
    ]
