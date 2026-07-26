"""Bootstrap tests.

These verify that the scaffolding produced by EWP-000.1A is structurally sound:
the project imports, the three planes resolve, the health endpoint responds and
the Django admin is absent.

They deliberately assert on structure rather than behaviour, because no
behaviour exists yet.
"""

from __future__ import annotations

from django.conf import settings
from django.test import Client
from django.urls import Resolver404, resolve, reverse


class TestProjectConfiguration:
    """The Django project is configured as the frozen architecture requires."""

    def test_all_fifteen_bounded_contexts_are_installed(self) -> None:
        expected = {
            "contexts.platform",
            "contexts.identity",
            "contexts.organisation",
            "contexts.configuration",
            "contexts.clients",
            "contexts.workflow",
            "contexts.work",
            "contexts.generation",
            "contexts.quality",
            "contexts.documents",
            "contexts.collaboration",
            "contexts.audit",
            "contexts.notifications",
            "contexts.insight",
            "contexts.portal",
        }
        installed = set(settings.INSTALLED_APPS)
        assert expected <= installed, f"missing contexts: {sorted(expected - installed)}"

    def test_no_unexpected_bounded_contexts(self) -> None:
        contexts = {a for a in settings.INSTALLED_APPS if a.startswith("contexts.")}
        assert len(contexts) == 15, f"expected exactly 15 contexts, found {len(contexts)}"

    def test_database_engine_is_postgresql(self) -> None:
        """PostgreSQL is architecturally mandated: RLS is load-bearing (TAD §5)."""
        assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"

    def test_timestamps_are_timezone_aware_utc(self) -> None:
        """All timestamps are stored in UTC (TD §1.3)."""
        assert settings.USE_TZ is True
        assert settings.TIME_ZONE == "UTC"


class TestDjangoAdminIsAbsent:
    """The admin bypasses the tenant model and permission layer (EIB §7.4)."""

    def test_admin_app_is_not_installed(self) -> None:
        assert "django.contrib.admin" not in settings.INSTALLED_APPS

    def test_no_admin_route_is_registered(self) -> None:
        client = Client()
        for candidate in ("/admin/", "/django-admin/"):
            assert client.get(candidate).status_code == 404, f"{candidate} is routed"


class TestThreePlanes:
    """Internal, portal and platform planes are structurally separate (AR §2.4)."""

    def test_each_plane_namespace_is_registered(self) -> None:
        from config import urls_internal, urls_platform, urls_portal

        assert urls_internal.app_name == "internal"
        assert urls_portal.app_name == "portal"
        assert urls_platform.app_name == "platform"

    def test_planes_expose_only_their_bootstrap_route(self) -> None:
        """EWP-000.1B-01 adds one bootstrap route per plane; no domain routes."""
        from config import urls_internal, urls_platform, urls_portal

        for module in (urls_internal, urls_portal, urls_platform):
            assert len(module.urlpatterns) == 1, f"{module.app_name} has extra routes"

    def test_unrouted_plane_paths_return_404(self) -> None:
        for prefix in ("/api/v1/", "/portal/api/v1/", "/platform/api/v1/"):
            with_suffix = f"{prefix}does-not-exist/"
            try:
                resolve(with_suffix)
            except Resolver404:
                continue
            raise AssertionError(f"{with_suffix} unexpectedly resolved")


class TestHealthEndpoint:
    """The health endpoint proves the application starts (EWP-000.1A §12)."""

    def test_returns_ok(self) -> None:
        response = Client().get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "ca-firm-operations-api"}

    def test_is_reachable_by_name(self) -> None:
        assert reverse("health:health") == "/health/"

    def test_discloses_nothing_beyond_liveness(self) -> None:
        """No versions, environment, configuration or dependency detail."""
        payload = Client().get("/health/").json()
        assert set(payload) == {"status", "service"}

    def test_requires_no_database(self) -> None:
        """Runs without the `db` fixture: a DB connection would error here."""
        assert Client().get("/health/").status_code == 200
