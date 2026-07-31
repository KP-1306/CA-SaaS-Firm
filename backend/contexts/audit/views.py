"""Read-only audit viewer.

Audit events are append-only: they are written only by the backend capture
helper, never through this API. This viewset exposes list/retrieve with
filters and is backend-authorized and tenant-scoped.
"""

from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated

from contexts.identity.access import is_executive
from core.api.request_context import HeaderPrincipalAuthentication, InternalPrincipal

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List/retrieve only. No create/update/delete is exposed."""

    authentication_classes = [HeaderPrincipalAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    serializer_class = AuditEventSerializer
    search_fields = ["summary", "entity_type", "action"]
    ordering_fields = ["created_at", "action", "entity_type"]
    queryset = AuditEvent.objects.all()

    def principal(self) -> InternalPrincipal:
        return self.request.user

    def _require_executive(self):
        principal = self.principal()
        if not is_executive(principal.tenant_id, principal):
            raise PermissionDenied("Audit access is restricted to firm leadership.")

    def get_queryset(self):
        self._require_executive()
        qs = AuditEvent.objects.filter(tenant_id=self.principal().tenant_id)
        params = self.request.query_params
        action = params.get("action")
        actor = params.get("actor")
        entity_type = params.get("entity_type")
        entity_id = params.get("entity_id")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if action:
            qs = qs.filter(action=action)
        if actor:
            qs = qs.filter(actor_principal_id=actor)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs
