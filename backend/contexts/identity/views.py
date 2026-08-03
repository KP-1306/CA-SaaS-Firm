from __future__ import annotations

from django.db import transaction

from core.api.viewsets import TenantModelViewSet
from contexts.audit.models import AuditAction
from contexts.audit.recording import record_event
from contexts.audit.viewset_mixins import MandatoryAuditPersistenceError

from .models import Employee, EmployeeExpertise, SkillCatalogue
from .serializers import (
    EmployeeExpertiseSerializer,
    EmployeeSerializer,
    SkillCatalogueSerializer,
)


class EmployeeViewSet(TenantModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    search_fields = ["name", "email", "mobile", "employee_code", "role"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Filter employees by normalized expertise category.
        category = self.request.query_params.get("expertise")
        if category:
            emp_ids = EmployeeExpertise.objects.filter(
                tenant_id=self.principal().tenant_id, category=category, is_active=True
            ).values_list("employee_id", flat=True)
            qs = qs.filter(id__in=list(emp_ids))
        for field in ("department_id", "designation_id", "team_id", "branch_id", "manager_id"):
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        principal = self.principal()
        has_link = Employee.objects.filter(
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
        ).exists()
        try:
            with transaction.atomic():
                instance = serializer.save(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                    principal_id=None if has_link else principal.principal_id,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"email": "An employee with this email or code already exists for the firm."}
            ) from exc
        self._audit(instance, AuditAction.EMPLOYEE_CREATED, "Employee created")

    def perform_update(self, serializer):
        from django.db import IntegrityError

        principal = self.principal()
        previous_active = getattr(serializer.instance, "is_active", None)
        try:
            with transaction.atomic():
                instance = serializer.save(updated_by=principal.principal_id)
        except IntegrityError as exc:
            raise ValidationError(
                {"email": "An employee with this email or code already exists for the firm."}
            ) from exc
        action = AuditAction.EMPLOYEE_UPDATED
        summary = "Employee updated"
        if previous_active is not None and previous_active != instance.is_active:
            action = AuditAction.EMPLOYEE_ACTIVATED if instance.is_active else AuditAction.EMPLOYEE_DEACTIVATED
            summary = "Employee activated" if instance.is_active else "Employee deactivated"
        self._audit(instance, action, summary)

    def _audit(self, instance, action, summary):
        principal = self.principal()
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=action,
                entity_type="Employee",
                entity_id=instance.id,
                summary=summary,
                new={"name": instance.name, "employment_status": instance.employment_status, "is_active": str(instance.is_active)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc


class SkillCatalogueViewSet(TenantModelViewSet):
    queryset = SkillCatalogue.objects.all()
    serializer_class = SkillCatalogueSerializer
    search_fields = ["name", "code", "category_key"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active") == "true":
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        principal = self.principal()
        try:
            with transaction.atomic():
                instance = serializer.save(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                )
        except IntegrityError as exc:
            raise ValidationError({"code": "A skill with this code already exists."}) from exc
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.EXPERTISE_CHANGED,
                entity_type="SkillCatalogue",
                entity_id=instance.id,
                summary="Skill catalogue entry created",
                new={"name": instance.name, "code": instance.code, "is_custom": str(instance.is_custom)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc


class EmployeeExpertiseViewSet(TenantModelViewSet):
    queryset = EmployeeExpertise.objects.all()
    serializer_class = EmployeeExpertiseSerializer
    search_fields = ["category", "proficiency", "certification", "custom_label"]

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        principal = self.principal()
        # Prevent duplicate ACTIVE (employee, category) per tenant with a clean 400.
        existing = EmployeeExpertise.objects.filter(
            tenant_id=principal.tenant_id,
            employee_id=serializer.validated_data.get("employee_id"),
            category=serializer.validated_data.get("category"),
            is_active=True,
        ).exists()
        if existing and serializer.validated_data.get("is_active", True):
            raise ValidationError(
                {"category": "This expertise category is already recorded for the employee."}
            )
        try:
            with transaction.atomic():
                instance = serializer.save(
                    tenant_id=principal.tenant_id,
                    created_by=principal.principal_id,
                    updated_by=principal.principal_id,
                )
        except IntegrityError as exc:
            raise ValidationError(
                {"category": "This expertise category is already recorded for the employee."}
            ) from exc
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=AuditAction.EXPERTISE_CHANGED,
                entity_type="EmployeeExpertise",
                entity_id=instance.id,
                summary="Expertise recorded",
                new={"employee_id": str(instance.employee_id), "category": instance.category, "proficiency": instance.proficiency, "reviewer_eligible": str(instance.reviewer_eligible)},
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get("employee_id")
        category = self.request.query_params.get("category")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if category:
            qs = qs.filter(category=category)
        return qs
