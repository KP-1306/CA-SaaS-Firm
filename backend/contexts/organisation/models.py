from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class ActiveStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class FirmProfile(TenantModel):
    name = models.CharField(max_length=200)
    legal_name = models.CharField(max_length=250, blank=True)
    pan = models.CharField(max_length=10, blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id"], name="uq_firm_per_tenant")]


class Branch(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_branch_code_tenant")]
        ordering = ["name"]


class Team(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    branch_id = models.UUIDField(null=True, blank=True)
    lead_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ActiveStatus.choices, default=ActiveStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_team_code_tenant")]
        ordering = ["name"]
