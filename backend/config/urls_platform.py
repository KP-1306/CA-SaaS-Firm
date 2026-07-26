"""Platform plane URL configuration.

Serves vendor operators. Requires a platform principal acting under a
time-boxed, tenant-approved support grant (AR §7.9).

Platform principals have no standing access to tenant business data, and
document contents are unreachable under any grant scope.

A single bootstrap route proves that requests reach a platform-plane handler
(EWP-000.1B-01). Domain routes are added by the work package that implements
platform administration.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from .bootstrap_platform import bootstrap

app_name = "platform"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", bootstrap, name="bootstrap"),
]
