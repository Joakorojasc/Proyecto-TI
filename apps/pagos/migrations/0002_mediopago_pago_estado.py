from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0002_usuarioportal_usuario"),
        ("pagos", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MedioPago",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("ultimos_4_digitos", models.CharField(max_length=4)),
                ("marca_tarjeta", models.CharField(max_length=50)),
                ("token_simulado", models.CharField(max_length=255, unique=True)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="medios_pago",
                        to="clientes.cliente",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="pago",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("aprobado", "Aprobado"),
                    ("rechazado", "Rechazado"),
                ],
                max_length=255,
                null=True,
            ),
        ),
    ]
