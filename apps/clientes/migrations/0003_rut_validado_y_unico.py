"""El RUT pasa a ser obligatorio, único y validado.

Antes de cambiar el esquema hay que dejar los datos en condiciones, porque la
base trae RUTs que no pasan la validación nueva (los de los datos de prueba) y
porque el campo pasa a no aceptar vacíos.
"""

from django.db import migrations, models

import apps.clientes.validators as validadores

# Los datos de prueba antiguos no eran RUTs. Se reemplazan por los nuevos, que
# son los mismos que ahora genera seed_demo.
RUTS_DEMO = {
    "DEMO-PEQUENO-001": "76543210-3",
    "DEMO-MEDIANO-001": "77777777-7",
    "DEMO-ANUAL-001": "65123456-5",
}


def arreglar_ruts(apps, schema_editor):
    Cliente = apps.get_model("clientes", "Cliente")
    problemas = []

    for cliente in Cliente.objects.all():
        if cliente.rut in RUTS_DEMO:
            cliente.rut = RUTS_DEMO[cliente.rut]
            cliente.save(update_fields=["rut"])
            continue

        if not cliente.rut:
            problemas.append(f"id={cliente.id} sin RUT")
            continue

        normalizado = validadores.normalizar_rut(cliente.rut)
        try:
            validadores.validar_rut(normalizado)
        except Exception:
            problemas.append(f"id={cliente.id} rut={cliente.rut!r}")
            continue

        if normalizado != cliente.rut:
            cliente.rut = normalizado
            cliente.save(update_fields=["rut"])

    if problemas:
        raise RuntimeError(
            "Hay clientes con RUT inválido o vacío y la migración no puede "
            "inventarlos. Corrígelos en la base y vuelve a correrla:\n  "
            + "\n  ".join(problemas)
        )


def revertir(apps, schema_editor):
    """No hay nada que devolver: los RUTs normalizados siguen siendo válidos."""


class Migration(migrations.Migration):
    dependencies = [
        ("clientes", "0002_usuarioportal_usuario"),
    ]

    operations = [
        migrations.RunPython(arreglar_ruts, revertir),
        migrations.AlterField(
            model_name="cliente",
            name="rut",
            field=models.CharField(
                error_messages={
                    "unique": (
                        "Esta institución ya está registrada. Si trabajas ahí, "
                        "pídele acceso al administrador de la cuenta."
                    )
                },
                max_length=12,
                unique=True,
                validators=[validadores.validar_rut],
                verbose_name="RUT",
            ),
        ),
    ]
