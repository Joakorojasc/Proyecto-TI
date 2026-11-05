from django.db import migrations

from ._rut_data import normalizar_ruts


class Migration(migrations.Migration):
    dependencies = [("clientes", "0002_usuarioportal_usuario")]

    operations = [
        # Revisión completa antes de escribir y transacción también en MariaDB.
        # Revertir conserva el RUT canónico; no recupera su puntuación original.
        migrations.RunPython(normalizar_ruts, migrations.RunPython.noop, atomic=True),
    ]
