# Employee Operations V1 — capacity, availability, leave and holidays (initial).

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
            name="CapacityProfile",
            fields=_audit_fields() + [
                ("employee_id", models.UUIDField(db_index=True)),
                ("daily_hours", models.DecimalField(decimal_places=2, default=8, max_digits=5)),
                ("works_monday", models.BooleanField(default=True)),
                ("works_tuesday", models.BooleanField(default=True)),
                ("works_wednesday", models.BooleanField(default=True)),
                ("works_thursday", models.BooleanField(default=True)),
                ("works_friday", models.BooleanField(default=True)),
                ("works_saturday", models.BooleanField(default=False)),
                ("works_sunday", models.BooleanField(default=False)),
                ("effective_from", models.DateField(blank=True, null=True)),
                ("effective_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
            ],
            options={"ordering": ["-effective_from", "-created_at"]},
        ),
        migrations.AddIndex(
            model_name="capacityprofile",
            index=models.Index(fields=["tenant_id", "employee_id", "is_active"], name="ix_capprofile_emp_active"),
        ),
        migrations.CreateModel(
            name="CapacityOverride",
            fields=_audit_fields() + [
                ("employee_id", models.UUIDField(db_index=True)),
                ("override_date", models.DateField(db_index=True)),
                ("delta_hours", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-override_date"]},
        ),
        migrations.CreateModel(
            name="CapacityReservation",
            fields=_audit_fields() + [
                ("employee_id", models.UUIDField(db_index=True)),
                ("start_date", models.DateField(db_index=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("hours", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("work_item_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("reason", models.CharField(blank=True, max_length=200)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["-start_date"]},
        ),
        migrations.CreateModel(
            name="LeaveType",
            fields=_audit_fields() + [
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=30)),
                ("is_paid", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="LeaveRecord",
            fields=_audit_fields() + [
                ("employee_id", models.UUIDField(db_index=True)),
                ("leave_type_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("start_date", models.DateField(db_index=True)),
                ("end_date", models.DateField(db_index=True)),
                ("is_partial_day", models.BooleanField(default=False)),
                ("hours", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("status", models.CharField(choices=[("REQUESTED", "Requested"), ("APPROVED", "Approved"), ("REJECTED", "Rejected"), ("CANCELLED", "Cancelled")], db_index=True, default="REQUESTED", max_length=10)),
                ("reason", models.TextField(blank=True)),
                ("approved_by", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_comment", models.TextField(blank=True)),
            ],
            options={"ordering": ["-start_date"]},
        ),
        migrations.AddIndex(
            model_name="leaverecord",
            index=models.Index(fields=["tenant_id", "employee_id", "status"], name="ix_leave_emp_status"),
        ),
        migrations.CreateModel(
            name="Holiday",
            fields=_audit_fields() + [
                ("name", models.CharField(max_length=160)),
                ("holiday_date", models.DateField(db_index=True)),
                ("branch_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("team_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["holiday_date"]},
        ),
        migrations.AddConstraint(
            model_name="leavetype",
            constraint=models.UniqueConstraint(fields=("tenant_id", "code"), name="uq_leave_type_code_tenant"),
        ),
        migrations.AddConstraint(
            model_name="holiday",
            constraint=models.UniqueConstraint(fields=("tenant_id", "holiday_date", "branch_id", "team_id"), name="uq_holiday_scope_date"),
        ),
    ]
