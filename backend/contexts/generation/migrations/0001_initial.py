# Generated for Vridhi Core Workflow + Client Management V1 (additive).

import core.db.uuid7
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="ClientServiceSubscription",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("client_id", models.UUIDField(db_index=True)),
                ("service_id", models.UUIDField(db_index=True)),
                ("default_owner_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("default_reviewer_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("frequency", models.CharField(choices=[("NONE", "None"), ("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("HALF_YEARLY", "Half yearly"), ("YEARLY", "Yearly")], default="NONE", max_length=15)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("PAUSED", "Paused"), ("ENDED", "Ended")], db_index=True, default="ACTIVE", max_length=10)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="TaskTemplate",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("service_id", models.UUIDField(db_index=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("default_title", models.CharField(blank=True, max_length=200)),
                ("default_priority", models.CharField(blank=True, max_length=10)),
                ("default_owner_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("default_reviewer_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("default_due_days", models.PositiveIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="RecurringWorkProfile",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("subscription_id", models.UUIDField(db_index=True)),
                ("task_template_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("client_id", models.UUIDField(db_index=True)),
                ("service_id", models.UUIDField(db_index=True)),
                ("frequency", models.CharField(choices=[("NONE", "None"), ("MONTHLY", "Monthly"), ("QUARTERLY", "Quarterly"), ("HALF_YEARLY", "Half yearly"), ("YEARLY", "Yearly")], default="MONTHLY", max_length=15)),
                ("anchor_date", models.DateField(blank=True, null=True)),
                ("default_owner_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("default_reviewer_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="GeneratedWorkLedger",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("recurring_profile_id", models.UUIDField(db_index=True)),
                ("period_key", models.CharField(db_index=True, max_length=20)),
                ("work_item_id", models.UUIDField(db_index=True)),
                ("generated_on", models.DateField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="clientservicesubscription",
            constraint=models.UniqueConstraint(fields=("tenant_id", "client_id", "service_id"), name="uq_subscription_client_service"),
        ),
        migrations.AddConstraint(
            model_name="tasktemplate",
            constraint=models.UniqueConstraint(fields=("tenant_id", "service_id", "name"), name="uq_task_template_service_name"),
        ),
        migrations.AddConstraint(
            model_name="generatedworkledger",
            constraint=models.UniqueConstraint(fields=("tenant_id", "recurring_profile_id", "period_key"), name="uq_generated_profile_period"),
        ),
    ]
