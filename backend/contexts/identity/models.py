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
