"""Reusable fail-closed audit helpers for Employee Operations viewsets.

Provides a mixin that records a mandatory :class:`AuditEvent` on create/update
inside the same request, converting an audit-persistence failure into a 503 so
the mutation is never silently unaudited. Metadata is limited to non-sensitive
identifiers; credentials/tokens/secrets are never included.
"""

from __future__ import annotations

from rest_framework.exceptions import APIException

from .models import AuditAction
from .recording import record_event


class MandatoryAuditPersistenceError(APIException):
    status_code = 503
    default_detail = "The change was not saved because the mandatory audit record could not be persisted."
    default_code = "mandatory_audit_unavailable"


# Fields that must never be copied into audit metadata.
_SENSITIVE_KEYS = frozenset(
    {"password", "token", "secret", "authorization", "api_key", "access_key", "refresh_token"}
)


def _safe_new(instance, fields):
    out = {}
    for f in fields:
        if f in _SENSITIVE_KEYS:
            continue
        value = getattr(instance, f, None)
        if value is not None:
            out[f] = str(value)
    return out


class AuditedTenantViewSetMixin:
    """Mixin adding fail-closed audit to a TenantModelViewSet.

    Subclasses set ``audit_entity_type`` and ``audit_summary_fields`` (the field
    names summarised into metadata). ``audit_create_action`` /
    ``audit_update_action`` default to CREATE/UPDATE but may be overridden.
    """

    audit_entity_type = "Record"
    audit_summary_fields: tuple[str, ...] = ()
    audit_create_action = AuditAction.CREATE
    audit_update_action = AuditAction.UPDATE

    def _record_audit(self, instance, action, summary):
        principal = self.principal()
        try:
            record_event(
                tenant_id=instance.tenant_id,
                principal_id=principal.principal_id,
                action=action,
                entity_type=self.audit_entity_type,
                entity_id=instance.id,
                summary=summary,
                new=_safe_new(instance, self.audit_summary_fields),
                request=self.request,
            )
        except Exception as exc:  # noqa: BLE001
            raise MandatoryAuditPersistenceError() from exc

    def perform_create(self, serializer):
        principal = self.principal()
        instance = serializer.save(
            tenant_id=principal.tenant_id,
            created_by=principal.principal_id,
            updated_by=principal.principal_id,
        )
        self._record_audit(instance, self.audit_create_action, f"{self.audit_entity_type} created")
        return instance

    def perform_update(self, serializer):
        instance = serializer.save(updated_by=self.principal().principal_id)
        self._record_audit(instance, self.audit_update_action, f"{self.audit_entity_type} updated")
        return instance
