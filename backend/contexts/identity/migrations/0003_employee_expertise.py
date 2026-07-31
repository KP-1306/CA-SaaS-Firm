from __future__ import annotations

import core.db.uuid7
from django.db import migrations, models
from django.utils import timezone

# Legacy JSON tags that map cleanly to normalized categories.
_LEGACY_MAP = {
    "GST": "GST", "INCOME_TAX": "INCOME_TAX", "INCOME TAX": "INCOME_TAX",
    "TDS": "TDS", "ROC": "ROC", "ACCOUNTING": "ACCOUNTING", "PAYROLL": "PAYROLL",
    "COMPLIANCE": "COMPLIANCE", "AUDIT": "STATUTORY_AUDIT",
    "STATUTORY_AUDIT": "STATUTORY_AUDIT", "INTERNAL_AUDIT": "INTERNAL_AUDIT",
    "TAX_AUDIT": "TAX_AUDIT", "BOOKKEEPING": "BOOKKEEPING",
}


def seed_from_legacy_json(apps, schema_editor):
    """Additively seed normalized rows from the legacy JSON list.

    The legacy Employee.expertise JSON is left intact (deprecated, read-only).
    Only unambiguously mappable tags are seeded; anything else is skipped, and
    duplicates are avoided by the unique constraint (checked before insert).
    """
    Employee = apps.get_model("ctx_identity", "Employee")
    EmployeeExpertise = apps.get_model("ctx_identity", "EmployeeExpertise")
    for emp in Employee.objects.all():
        tags = emp.expertise if isinstance(emp.expertise, list) else []
        for raw in tags:
            key = str(raw).strip().upper().replace("-", "_")
            category = _LEGACY_MAP.get(key)
            if not category:
                continue
            exists = EmployeeExpertise.objects.filter(
                tenant_id=emp.tenant_id, employee_id=emp.id, category=category
            ).exists()
            if exists:
                continue
            EmployeeExpertise.objects.create(
                tenant_id=emp.tenant_id,
                created_by=emp.created_by,
                updated_by=emp.updated_by,
                employee_id=emp.id,
                category=category,
                proficiency="INTERMEDIATE",
            )


def unseed(apps, schema_editor):
    EmployeeExpertise = apps.get_model("ctx_identity", "EmployeeExpertise")
    EmployeeExpertise.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("ctx_identity", "0002_employee_principal_id")]

    operations = [
        migrations.CreateModel(
            name="EmployeeExpertise",
            fields=[
                ("id", models.UUIDField(default=core.db.uuid7.uuid7, editable=False, primary_key=True, serialize=False)),
                ("tenant_id", models.UUIDField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.UUIDField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.UUIDField()),
                ("row_version", models.PositiveIntegerField(default=0)),
                ("employee_id", models.UUIDField(db_index=True)),
                ("category", models.CharField(choices=[
                    ("GST", "GST"),
                    ("INCOME_TAX", "Income Tax"),
                    ("TDS", "TDS"),
                    ("ROC", "ROC"),
                    ("STATUTORY_AUDIT", "Statutory Audit"),
                    ("INTERNAL_AUDIT", "Internal Audit"),
                    ("TAX_AUDIT", "Tax Audit"),
                    ("BANK_AUDIT", "Bank Audit"),
                    ("CONCURRENT_AUDIT", "Concurrent Audit"),
                    ("ACCOUNTING", "Accounting"),
                    ("BOOKKEEPING", "Bookkeeping"),
                    ("PAYROLL", "Payroll"),
                    ("COMPLIANCE", "Compliance"),
                    ("COMPANY_FORMATION", "Company Formation"),
                    ("PROJECT_FINANCE", "Project Finance"),
                    ("MSME", "MSME"),
                    ("FEMA", "FEMA"),
                    ("INTERNATIONAL_TAX", "International Tax"),
                    ("NRI_TAXATION", "NRI Taxation"),
                    ("TRANSFER_PRICING", "Transfer Pricing"),
                ], max_length=30)),
                ("proficiency", models.CharField(choices=[
                    ("BASIC", "Basic"),
                    ("INTERMEDIATE", "Intermediate"),
                    ("ADVANCED", "Advanced"),
                    ("EXPERT", "Expert"),
                ], default="INTERMEDIATE", max_length=15)),
            ],
            options={"ordering": ["category"]},
        ),
        migrations.AddConstraint(
            model_name="employeeexpertise",
            constraint=models.UniqueConstraint(
                fields=["tenant_id", "employee_id", "category"],
                name="uq_employee_expertise_category",
            ),
        ),
        migrations.RunPython(seed_from_legacy_json, unseed),
    ]
