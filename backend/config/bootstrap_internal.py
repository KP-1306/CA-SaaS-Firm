"""Internal plane bootstrap view.

Proves that a request to the internal plane resolves to an internal-plane
handler (AR §2.4, ADR-004). This is plane infrastructure, not a domain route:
it discloses only the plane identity and availability, touches no database and
holds no state. Domain routes are added by later work packages.

This handler is owned by the internal plane and must never be imported by the
portal or platform plane.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

PLANE = "internal"


def bootstrap(request: HttpRequest) -> JsonResponse:
    """Return the internal plane's availability marker."""
    return JsonResponse({"plane": PLANE, "status": "available"})
