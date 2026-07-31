from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class FirmRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    PARTNER = "PARTNER", "Partner"
    MANAGER = "MANAGER", "Manager"
    STAFF = "STAFF", "Staff"
    READ_ONLY = "READ_ONLY", "Read only"


class Employee(TenantModel):
    name = models.CharField(max_length=180)
    email = models.EmailField()
    mobile = models.CharField(max_length=20, blank=True)
    employee_code = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=20, choices=FirmRole.choices, default=FirmRole.STAFF)
    branch_id = models.UUIDField(null=True, blank=True)
    team_id = models.UUIDField(null=True, blank=True)
    expertise = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    principal_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "email"], name="uq_employee_email_tenant")]
        ordering = ["name"]


class ExpertiseCategory(models.TextChoices):
    GST = "GST", "GST"
    INCOME_TAX = "INCOME_TAX", "Income Tax"
    TDS = "TDS", "TDS"
    ROC = "ROC", "ROC"
    STATUTORY_AUDIT = "STATUTORY_AUDIT", "Statutory Audit"
    INTERNAL_AUDIT = "INTERNAL_AUDIT", "Internal Audit"
    TAX_AUDIT = "TAX_AUDIT", "Tax Audit"
    BANK_AUDIT = "BANK_AUDIT", "Bank Audit"
    CONCURRENT_AUDIT = "CONCURRENT_AUDIT", "Concurrent Audit"
    ACCOUNTING = "ACCOUNTING", "Accounting"
    BOOKKEEPING = "BOOKKEEPING", "Bookkeeping"
    PAYROLL = "PAYROLL", "Payroll"
    COMPLIANCE = "COMPLIANCE", "Compliance"
    COMPANY_FORMATION = "COMPANY_FORMATION", "Company Formation"
    PROJECT_FINANCE = "PROJECT_FINANCE", "Project Finance"
    MSME = "MSME", "MSME"
    FEMA = "FEMA", "FEMA"
    INTERNATIONAL_TAX = "INTERNATIONAL_TAX", "International Tax"
    NRI_TAXATION = "NRI_TAXATION", "NRI Taxation"
    TRANSFER_PRICING = "TRANSFER_PRICING", "Transfer Pricing"


class ProficiencyLevel(models.TextChoices):
    BASIC = "BASIC", "Basic"
    INTERMEDIATE = "INTERMEDIATE", "Intermediate"
    ADVANCED = "ADVANCED", "Advanced"
    EXPERT = "EXPERT", "Expert"


class EmployeeExpertise(TenantModel):
    """Normalized employee expertise (replaces the legacy JSON list for writes).

    ``employee_id`` is a UUID reference (cross-row integrity on
    ``(tenant_id, id)``), consistent with the platform's no-cross-FK rule.
    Duplicate categories per employee are prevented by a unique constraint.
    """

    employee_id = models.UUIDField(db_index=True)
    category = models.CharField(max_length=30, choices=ExpertiseCategory.choices)
    proficiency = models.CharField(
        max_length=15, choices=ProficiencyLevel.choices, default=ProficiencyLevel.INTERMEDIATE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id", "category"],
                name="uq_employee_expertise_category",
            )
        ]
        ordering = ["category"]
