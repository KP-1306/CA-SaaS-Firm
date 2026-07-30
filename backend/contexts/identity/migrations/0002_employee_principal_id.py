from __future__ import annotations

from django.db import migrations, models


def link_existing_employees(apps, schema_editor):
    Employee = apps.get_model("ctx_identity", "Employee")
    seen = set()
    for employee in Employee.objects.order_by("tenant_id", "created_at", "id"):
        key = (employee.tenant_id, employee.created_by)
        if employee.created_by and key not in seen:
            employee.principal_id = employee.created_by
            employee.save(update_fields=["principal_id"])
            seen.add(key)


def unlink_existing_employees(apps, schema_editor):
    Employee = apps.get_model("ctx_identity", "Employee")
    Employee.objects.update(principal_id=None)


class Migration(migrations.Migration):
    dependencies = [("ctx_identity", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="principal_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(link_existing_employees, unlink_existing_employees),
    ]
