"""Health endpoint view."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

SERVICE_NAME = "ca-firm-operations-api"


def health(request: HttpRequest) -> JsonResponse:
    """Return a minimal liveness response.

    Deliberately discloses nothing beyond liveness: no versions, no environment,
    no dependency status, no configuration (EWP-000.1A §12).
    """
    return JsonResponse({"status": "ok", "service": SERVICE_NAME})
