from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("instancias", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="instanciamoodle",
            name="dominio",
            field=models.URLField(max_length=2048, null=True),
        ),
        migrations.AddField(
            model_name="instanciamoodle",
            name="logo_url",
            field=models.URLField(blank=True, max_length=2048, null=True),
        ),
    ]
