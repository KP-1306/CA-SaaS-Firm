from __future__ import annotations

from typing import Any

from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from core.api.request_context import HeaderPrincipalAuthentication, InternalPrincipal


class TenantModelViewSet(viewsets.ModelViewSet[Any]):
    authentication_classes = [HeaderPrincipalAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def principal(self) -> InternalPrincipal:
        return self.request.user

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.principal().tenant_id)

    def perform_create(self, serializer):
        p = self.principal()
        serializer.save(tenant_id=p.tenant_id, created_by=p.principal_id, updated_by=p.principal_id)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.principal().principal_id)
