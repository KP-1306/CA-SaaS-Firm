"""Backend audit capture helper.

Design (per approved audit contract):

* Optional metadata collection/sanitization is best-effort: if it fails, we
  fall back to reduced metadata and still write the mandatory audit row.
* Core AuditEvent persistence is mandatory and is NOT silently swallowed. When
  called inside the business transaction (the wiring in the work viewsets uses
  ``transaction.atomic``), a persistence failure propagates and rolls the whole
  business mutation back, so no audited mutation survives without its audit row.

``record_event`` therefore raises on core persistence failure. Callers that
must not fail on audit (there are none for mandatory business actions in this
sprint) would use ``record_event_best_effort``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("audit")

# Keys that must never be copied into audit payloads.
_SENSITIVE_KEYS = frozenset({
    "password", "token", "secret", "file", "files", "content", "raw",
    "attachment", "data", "payload", "authorization",
})
_MAX_VALUE_LEN = 500


def _sanitize(mapping) -> dict:
    """Best-effort sanitization of an optional field map. Never raises."""
    try:
        if not isinstance(mapping, dict):
            return {}
        clean = {}
        for key, value in mapping.items():
            lower = str(key).lower()
            if any(s in lower for s in _SENSITIVE_KEYS):
                continue
            if isinstance(value, (dict, list)):
                continue
            text = "" if value is None else str(value)
            if len(text) > _MAX_VALUE_LEN:
                text = text[:_MAX_VALUE_LEN] + "..."
            clean[str(key)] = text
        return clean
    except Exception:  # optional metadata must never break the audit row
        logger.warning("audit metadata sanitization failed; storing empty map", exc_info=True)
        return {}


def _optional_context(request):
    """Collect optional request context. Never raises; returns reduced data."""
    correlation_id = ""
    ip_address = None
    try:
        if request is not None:
            correlation_id = request.META.get("HTTP_X_CORRELATION_ID", "")[:64]
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            ip_address = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    except Exception:
        logger.warning("audit optional context collection failed; reduced metadata", exc_info=True)
    return correlation_id, ip_address


def record_event(
    *,
    tenant_id,
    principal_id,
    action,
    entity_type,
    entity_id,
    summary="",
    previous=None,
    new=None,
    actor_employee_id=None,
    request=None,
    metadata=None,
):
    """Write one mandatory audit row.

    Optional metadata failures fall back to reduced metadata. Core persistence
    is mandatory: any failure to insert the AuditEvent PROPAGATES to the caller
    so the surrounding business transaction rolls back. Do not wrap this call in
    a bare try/except that discards the error.
    """
    from .models import AuditEvent

    correlation_id, ip_address = _optional_context(request)
    # Core persistence is intentionally NOT guarded - failures must surface.
    return AuditEvent.objects.create(
        tenant_id=tenant_id,
        created_by=principal_id,
        updated_by=principal_id,
        actor_principal_id=principal_id,
        actor_employee_id=actor_employee_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=(summary or "")[:300],
        previous_values=_sanitize(previous),
        new_values=_sanitize(new),
        correlation_id=correlation_id,
        ip_address=ip_address,
        metadata=_sanitize(metadata),
    )


def record_event_best_effort(**kwargs):
    """Non-critical audit capture: swallow persistence failures (logged).

    Reserved for genuinely optional, non-business-critical audit points. Not
    used for the mandatory business actions in this sprint.
    """
    try:
        return record_event(**kwargs)
    except Exception:
        logger.exception(
            "best-effort audit failed for %s %s",
            kwargs.get("entity_type"), kwargs.get("entity_id"),
        )
        return None
