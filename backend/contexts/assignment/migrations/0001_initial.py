# Employee Operations V1 — reviewer hierarchy and assignment ledger (initial).

import core.db.uuid7
from django.db import migrations, models


def _audit_fields():
    return [
        ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
        ("tenant_id", models.UUIDField(db_index=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("created_by", models.UUIDField()),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("updated_by", models.UUIDField()),
        ("row_version", models.PositiveIntegerField(default=0)),
    ]


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReviewerRule",
            fields=_audit_fields() + [
                ("scope", models.CharField(choices=[("ASSIGNMENT", "Assignment-specific"), ("SERVICE", "Service"), ("TASK_TEMPLATE", "Task template"), ("TEAM", "Team"), ("EMPLOYEE_DEFAULT", "Employee default"), ("PARTNER_FALLBACK", "Partner/final fallback")], db_index=True, max_length=20)),
                ("scope_ref_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("level", models.CharField(choices=[("PRIMARY", "Primary reviewer"), ("SECONDARY", "Secondary reviewer"), ("ESCALATION", "Escalation reviewer"), ("FINAL_APPROVER", "Final approver")], default="PRIMARY", max_length=15)),
                ("reviewer_user_id", models.UUIDField(db_index=True)),
                ("service_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.CharField(blank=True, max_length=200)),
            ],
            options={"ordering": ["scope", "level"]},
        ),
        migrations.AddIndex(
            model_name="reviewerrule",
            index=models.Index(fields=["tenant_id", "scope", "is_active"], name="ix_revrule_scope_active"),
        ),
        migrations.AddConstraint(
            model_name="reviewerrule",
            constraint=models.UniqueConstraint(
                fields=("tenant_id", "scope", "scope_ref_id", "level"),
                condition=models.Q(is_active=True),
                name="uq_active_reviewer_rule",
            ),
        ),
        migrations.CreateModel(
            name="AssignmentDecision",
            fields=_audit_fields() + [
                ("work_item_id", models.UUIDField(db_index=True)),
                ("selected_owner_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("selected_reviewer_user_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("was_override", models.BooleanField(default=False)),
                ("override_reason", models.TextField(blank=True)),
                ("recommended_owner_user_id", models.UUIDField(blank=True, null=True)),
                ("explanation", models.JSONField(blank=True, default=dict)),
                ("decided_by", models.UUIDField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="assignmentdecision",
            index=models.Index(fields=["tenant_id", "work_item_id", "is_active"], name="ix_assndecision_wi_active"),
        ),
        migrations.CreateModel(
            name="AssignmentEvent",
            fields=_audit_fields() + [
                ("work_item_id", models.UUIDField(db_index=True)),
                ("event_type", models.CharField(choices=[("RECOMMENDED_APPLIED", "Recommended assignment applied"), ("OVERRIDE_APPLIED", "Override assignment applied"), ("REASSIGNED", "Reassigned"), ("REVIEWER_SET", "Reviewer set")], max_length=25)),
                ("owner_user_id", models.UUIDField(blank=True, null=True)),
                ("reviewer_user_id", models.UUIDField(blank=True, null=True)),
                ("was_override", models.BooleanField(default=False)),
                ("reason", models.TextField(blank=True)),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("detail", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="assignmentevent",
            index=models.Index(fields=["tenant_id", "work_item_id"], name="ix_assnevent_wi"),
        ),
    ]
