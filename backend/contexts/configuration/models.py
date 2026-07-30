from __future__ import annotations

from django.db import models

from core.db.models import TenantModel


class CatalogueStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Vertical(TenantModel):
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "code"], name="uq_vertical_code_tenant")]
        ordering = ["name"]


class Domain(TenantModel):
    vertical_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    owner_user_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "vertical_id", "code"], name="uq_domain_code_vertical")]
        ordering = ["name"]


class Service(TenantModel):
    domain_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    default_owner_user_id = models.UUIDField(null=True, blank=True)
    default_due_days = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=CatalogueStatus.choices, default=CatalogueStatus.ACTIVE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["tenant_id", "domain_id", "code"], name="uq_service_code_domain")]
        ordering = ["name"]
