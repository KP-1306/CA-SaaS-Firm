# Additive: client lifecycle fields (Vridhi Core Workflow + Client Management V1).
# AddField only — no data migration, no destructive change.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_clients", "0002_document_contact_preferences"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="tan",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="client",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("PROSPECT", "Prospect"),
                    ("ONBOARDING", "Onboarding"),
                    ("ACTIVE", "Active"),
                    ("SUSPENDED", "Suspended"),
                    ("CLOSED", "Closed"),
                    ("ARCHIVED", "Archived"),
                ],
                db_index=True,
                default="PROSPECT",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="client",
            name="primary_branch_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="primary_contact_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="onboarding_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="activation_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="suspension_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="suspension_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="client",
            name="closure_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="client",
            name="closure_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="client",
            name="archive_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
