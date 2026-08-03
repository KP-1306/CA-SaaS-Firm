# Employee Operations V1 — task template default estimate (additive).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_generation", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tasktemplate",
            name="default_estimated_hours",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
    ]
