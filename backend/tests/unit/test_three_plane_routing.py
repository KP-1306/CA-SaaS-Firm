"""Three-plane routing tests (EWP-000.1B-01).

Prove that the internal, portal and platform planes each resolve to their own
independently owned handler, that the plane namespaces are distinct, that the
Django admin returns 404, and that unknown routes under every plane return 404.

These exercise the real URL resolver and the real handlers through Django's test
client; no server process is started. No database, authentication or business
behaviour is involved — those belong to later work packages.
"""

from __future__ import annotations

from django.test import Client
from django.urls import Resolver404, resolve, reverse

PLANES = (
    ("internal", "/api/v1/"),
    ("portal", "/portal/api/v1/"),
    ("platform", "/platform/api/v1/"),
)


class TestPlaneBootstrapResponses:
    """Each plane root returns its own availability marker with HTTP 200."""

    def test_internal_plane_returns_its_marker(self) -> None:
        response = Client().get("/api/v1/")
        assert response.status_code == 200
        assert response.json() == {"plane": "internal", "status": "available"}

    def test_portal_plane_returns_its_marker(self) -> None:
        response = Client().get("/portal/api/v1/")
        assert response.status_code == 200
        assert response.json() == {"plane": "portal", "status": "available"}

    def test_platform_plane_returns_its_marker(self) -> None:
        response = Client().get("/platform/api/v1/")
        assert response.status_code == 200
        assert response.json() == {"plane": "platform", "status": "available"}


class TestPlaneNamespaces:
    """Each plane root reverses through its own distinct namespace."""

    def test_each_plane_reverses_through_its_namespace(self) -> None:
        assert reverse("internal:bootstrap") == "/api/v1/"
        assert reverse("portal:bootstrap") == "/portal/api/v1/"
        assert reverse("platform:bootstrap") == "/platform/api/v1/"

    def test_namespaces_are_distinct(self) -> None:
        matches = {resolve(path).namespace for _, path in PLANES}
        assert matches == {"internal", "portal", "platform"}


class TestHandlerIndependence:
    """The three roots resolve to three different handler callables."""

    def test_each_plane_resolves_to_a_distinct_handler(self) -> None:
        handlers = [resolve(path).func for _, path in PLANES]
        assert len({id(h) for h in handlers}) == 3, "planes share a handler"

    def test_handlers_come_from_distinct_plane_modules(self) -> None:
        modules = {resolve(path).func.__module__ for _, path in PLANES}
        assert modules == {
            "config.bootstrap_internal",
            "config.bootstrap_portal",
            "config.bootstrap_platform",
        }


class TestAdminLockdown:
    """The Django admin is not routed on any plane (EIB §7.4)."""

    def test_admin_returns_404(self) -> None:
        assert Client().get("/admin/").status_code == 404

    def test_admin_is_not_redirected(self) -> None:
        """A 301/302 would imply a registered admin surface behind a redirect."""
        assert Client().get("/admin/").status_code == 404

    def test_admin_is_unresolvable(self) -> None:
        try:
            resolve("/admin/")
        except Resolver404:
            return
        raise AssertionError("/admin/ unexpectedly resolved")


class TestUnknownRoutesReturn404:
    """An unknown route under every plane returns 404."""

    def test_unknown_route_per_plane_returns_404(self) -> None:
        client = Client()
        for _, prefix in PLANES:
            unknown = f"{prefix}not-a-route/"
            assert client.get(unknown).status_code == 404, f"{unknown} resolved"
