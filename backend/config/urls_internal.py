"""Internal plane URL configuration.

Serves firm staff. Requires an internal principal (AR §2.4).

A single bootstrap route proves that requests reach an internal-plane handler
(EWP-000.1B-01). Domain routes are added by the work packages that implement
each bounded context.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from .bootstrap_internal import bootstrap

app_name = "internal"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", bootstrap, name="bootstrap"),
]
