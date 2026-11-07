import uuid

import django.db.models.deletion
from django.db import migrations, models


def marcar_activas_como_pendientes(apps, schema_editor):
    instancia = apps.get_model("instancias", "InstanciaMoodle")
    instancia.objects.exclude(estado="archivada").update(estado="pendiente")
    instancia.objects.filter(estado__isnull=True).update(estado="pendiente")


class Migration(migrations.Migration):

    dependencies = [
        ("instancias", "0004_instanciamoodle_created_at"),
    ]

    operations = [
        migrations.RunPython(
            marcar_activas_como_pendientes,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="instanciamoodle",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente de aprovisionamiento"),
                    ("activa", "Activa"),
                    ("archivada", "Archivada"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="SolicitudAprovisionamiento",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("pendiente", "Pendiente"),
                            ("en_proceso", "En proceso"),
                            ("activa", "Activa"),
                            ("fallida", "Fallida"),
                        ],
                        default="pendiente",
                        max_length=20,
                    ),
                ),
                (
                    "operation_id",
                    models.CharField(blank=True, max_length=255, null=True, unique=True),
                ),
                (
                    "idempotency_key",
                    models.CharField(
                        default=uuid.uuid4,
                        editable=False,
                        max_length=255,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "instancia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="solicitudes_aprovisionamiento",
                        to="instancias.instanciamoodle",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
            },
        ),
    ]
