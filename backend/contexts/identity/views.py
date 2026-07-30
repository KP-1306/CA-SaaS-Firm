from __future__ import annotations

from core.api.viewsets import TenantModelViewSet

from .models import Employee
from .serializers import EmployeeSerializer


class EmployeeViewSet(TenantModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    search_fields = ["name", "email", "mobile", "employee_code", "role"]

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
