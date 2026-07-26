"""Portal plane URL configuration.

Serves client organisations. Requires a portal principal with an active
organisation membership (AR ADR-012).

This plane must only ever expose allow-list serialisers constructed field by
field (AR ADR-004). It must never import an internal serialiser: a field added
to an internal representation must remain invisible to clients by default.

A single bootstrap route proves that requests reach a portal-plane handler
(EWP-000.1B-01). Domain routes are added by the work package that implements
portal publication.
"""

from __future__ import annotations

from django.urls import URLPattern, URLResolver, path

from .bootstrap_portal import bootstrap

app_name = "portal"

urlpatterns: list[URLPattern | URLResolver] = [
    path("", bootstrap, name="bootstrap"),
]
