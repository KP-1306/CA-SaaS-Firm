# Employee Operations V1 — authoritative operational effort estimate (additive).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_work", "0004_attachment_review_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="workitem",
            name="estimated_hours",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
    ]
