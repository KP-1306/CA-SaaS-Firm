"""Root URL configuration.

Three application planes with no shared handlers (AR §2.4, ADR-003, ADR-004).
The separation is structural: a portal request never reaches an internal
handler because no route maps it there.

    /api/v1/            internal plane   — firm staff
    /portal/api/v1/     portal plane     — client organisations
    /platform/api/v1/   platform plane   — vendor operators
    /health/            bootstrap health — no authentication, no database

The Django admin is deliberately absent from every plane. It bypasses the
tenant model and the permission layer and is never routed (EIB §7.4).
There is no conditional and no environment flag: the route does not exist.
"""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("health/", include("core.health.urls")),
    path("api/v1/", include("config.urls_internal")),
    path("portal/api/v1/", include("config.urls_portal")),
    path("platform/api/v1/", include("config.urls_platform")),
]
