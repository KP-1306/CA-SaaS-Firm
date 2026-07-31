from __future__ import annotations

import core.db.uuid7
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("actor_principal_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("actor_employee_id", models.UUIDField(blank=True, null=True)),
                ("action", models.CharField(db_index=True, max_length=30)),
                ("entity_type", models.CharField(db_index=True, max_length=60)),
                ("entity_id", models.UUIDField(db_index=True)),
                ("summary", models.CharField(blank=True, max_length=300)),
                ("previous_values", models.JSONField(blank=True, default=dict)),
                ("new_values", models.JSONField(blank=True, default=dict)),
                ("correlation_id", models.CharField(blank=True, max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["tenant_id", "created_at"], name="idx_audit_tenant_created"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["tenant_id", "entity_type", "entity_id"], name="idx_audit_entity"),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(fields=["tenant_id", "action"], name="idx_audit_action"),
        ),
    ]
