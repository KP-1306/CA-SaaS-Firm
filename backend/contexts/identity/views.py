from __future__ import annotations

from core.api.viewsets import TenantModelViewSet

from .models import Employee, EmployeeExpertise
from .serializers import EmployeeExpertiseSerializer, EmployeeSerializer


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
                tenant_id=self.principal().tenant_id, category=category
            ).values_list("employee_id", flat=True)
            qs = qs.filter(id__in=list(emp_ids))
        return qs

    def perform_create(self, serializer):
        principal = self.principal()
        has_link = Employee.objects.filter(
            tenant_id=principal.tenant_id,
            principal_id=principal.principal_id,
        ).exists()
        serializer.save(
            tenant_id=principal.tenant_id,
            created_by=principal.principal_id,
            updated_by=principal.principal_id,
            principal_id=None if has_link else principal.principal_id,
        )


class EmployeeExpertiseViewSet(TenantModelViewSet):
    queryset = EmployeeExpertise.objects.all()
    serializer_class = EmployeeExpertiseSerializer
    search_fields = ["category", "proficiency"]

    def perform_create(self, serializer):
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        principal = self.principal()
        # Prevent duplicate (employee, category) per tenant with a clean 400.
        existing = EmployeeExpertise.objects.filter(
            tenant_id=principal.tenant_id,
            employee_id=serializer.validated_data.get("employee_id"),
            category=serializer.validated_data.get("category"),
        ).exists()
        if existing:
            raise ValidationError({"category": "This expertise category is already recorded for the employee."})
        try:
            serializer.save(
                tenant_id=principal.tenant_id,
                created_by=principal.principal_id,
                updated_by=principal.principal_id,
            )
        except IntegrityError as exc:
            raise ValidationError({"category": "This expertise category is already recorded for the employee."}) from exc

    def get_queryset(self):
        qs = super().get_queryset()
        employee_id = self.request.query_params.get("employee_id")
        category = self.request.query_params.get("category")
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        if category:
            qs = qs.filter(category=category)
        return qs
