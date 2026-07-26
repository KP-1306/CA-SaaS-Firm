"""Portal plane bootstrap view.

Proves that a request to the portal plane resolves to a portal-plane handler
(AR §2.4, ADR-004). This is plane infrastructure, not a domain route: it
discloses only the plane identity and availability, touches no database and
holds no state. Domain routes are added by later work packages.

This handler is owned by the portal plane and must never be imported by the
internal or platform plane. The portal plane never exposes an internal
representation (AR ADR-004).
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

PLANE = "portal"


def bootstrap(request: HttpRequest) -> JsonResponse:
    """Return the portal plane's availability marker."""
    return JsonResponse({"plane": PLANE, "status": "available"})
