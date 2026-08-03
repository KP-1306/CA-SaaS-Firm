# Employee Operations V1 — organisation extensions (additive).

import core.db.uuid7
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ctx_organisation", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=30)),
                ("description", models.TextField(blank=True)),
                ("branch_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("head_user_id", models.UUIDField(blank=True, null=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")], default="ACTIVE", max_length=10)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Designation",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=30)),
                ("description", models.TextField(blank=True)),
                ("rank", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")], default="ACTIVE", max_length=10)),
            ],
            options={"ordering": ["rank", "name"]},
        ),
        migrations.CreateModel(
            name="TeamMembership",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("employee_id", models.UUIDField(db_index=True)),
                ("team_id", models.UUIDField(db_index=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-is_primary", "-effective_from"]},
        ),
        migrations.CreateModel(
            name="ReportingRelationship",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("employee_id", models.UUIDField(db_index=True)),
                ("manager_id", models.UUIDField(db_index=True)),
                ("relation_type", models.CharField(choices=[("PRIMARY", "Primary"), ("DOTTED", "Dotted line")], default="PRIMARY", max_length=10)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-effective_from"]},
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(fields=("tenant_id", "code"), name="uq_department_code_tenant"),
        ),
        migrations.AddConstraint(
            model_name="designation",
            constraint=models.UniqueConstraint(fields=("tenant_id", "code"), name="uq_designation_code_tenant"),
        ),
        migrations.AddConstraint(
            model_name="teammembership",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "employee_id", "team_id"),
                condition=models.Q(is_active=True),
                name="uq_active_team_membership",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportingrelationship",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "employee_id"),
                condition=models.Q(is_active=True, relation_type="PRIMARY"),
                name="uq_active_primary_reporting",
            ),
        ),
    ]
