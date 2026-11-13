from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("instancias", "0004_instanciamoodle_created_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="instanciamoodle",
            name="estado",
            field=models.CharField(
                choices=[
                    ("activa", "Activa"),
                    ("archivada", "Archivada"),
                    ("fallida", "Fallida"),
                ],
                max_length=255,
                null=True,
            ),
        ),
    ]
