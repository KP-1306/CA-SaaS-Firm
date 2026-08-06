from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory

from contexts.authorization.permissions import (
    AuthorizationDenied,
    HasAccess,
    access_permission,
    effective_access_for_request,
    require_access,
)
from contexts.authorization.services import EffectiveAccess


def _request():
    request = APIRequestFactory().get("/api/v1/clients/")
    request.vridhi_account = SimpleNamespace(id=uuid4())
    request.vridhi_membership = SimpleNamespace(
        tenant_id=uuid4(),
    )
    request.auth = None
    return request


def _effective(
    request,
    *codes: str,
) -> EffectiveAccess:
    return EffectiveAccess(
        tenant_id=request.vridhi_membership.tenant_id,
        user_account_id=request.vridhi_account.id,
        role_code="CONSULTANT",
        access_codes=frozenset(codes),
        department_ids=(),
        team_ids=(),
        service_ids=(),
    )


def test_effective_access_is_resolved_once_and_cached_on_request():
    request = _request()
    resolved = _effective(request, "clients.view")

    with patch(
        "contexts.authorization.permissions.resolve_effective_access",
        return_value=resolved,
    ) as resolver:
        first = effective_access_for_request(request)
        second = effective_access_for_request(request)

    assert first is resolved
    assert second is resolved
    assert request.effective_access is resolved
    resolver.assert_called_once_with(
        tenant_id=request.vridhi_membership.tenant_id,
        user_account_id=request.vridhi_account.id,
    )


def test_missing_identity_context_fails_closed():
    request = APIRequestFactory().get("/api/v1/clients/")

    with pytest.raises(
        AuthorizationDenied,
        match="authenticated Vridhi account",
    ):
        effective_access_for_request(request)


def test_require_access_returns_effective_access_when_allowed():
    request = _request()
    resolved = _effective(
        request,
        "clients.view",
        "work.view",
    )

    with patch(
        "contexts.authorization.permissions.resolve_effective_access",
        return_value=resolved,
    ):
        result = require_access(
            request,
            "clients.view",
        )

    assert result is resolved


def test_require_access_denies_and_records_security_event():
    request = _request()
    resolved = _effective(request, "clients.view")

    with (
        patch(
            "contexts.authorization.permissions.resolve_effective_access",
            return_value=resolved,
        ),
        patch(
            "contexts.authorization.permissions.record_auth_event",
        ) as recorder,
    ):
        with pytest.raises(
            AuthorizationDenied,
            match="work.approve",
        ):
            require_access(
                request,
                "work.approve",
            )

    recorder.assert_called_once()
    call = recorder.call_args.kwargs

    assert call["reason"] == "RBAC_ACCESS_DENIED"
    assert call["metadata"]["required_access"] == "work.approve"
    assert call["metadata"]["request_method"] == "GET"
    assert call["metadata"]["request_path"] == "/api/v1/clients/"


def test_access_permission_factory_creates_drf_permission_class():
    permission_class = access_permission("clients.view")

    assert issubclass(permission_class, HasAccess)
    assert permission_class.required_access == "clients.view"
    assert permission_class.__name__ == "HasAccess_clients_view"


def test_bound_permission_allows_matching_access():
    request = _request()
    resolved = _effective(request, "clients.view")
    permission_class = access_permission("clients.view")

    with patch(
        "contexts.authorization.permissions.resolve_effective_access",
        return_value=resolved,
    ):
        assert permission_class().has_permission(
            request,
            SimpleNamespace(),
        )


def test_view_level_required_access_is_supported():
    request = _request()
    resolved = _effective(request, "reports.view")

    with patch(
        "contexts.authorization.permissions.resolve_effective_access",
        return_value=resolved,
    ):
        assert HasAccess().has_permission(
            request,
            SimpleNamespace(required_access="reports.view"),
        )


def test_unconfigured_has_access_fails_during_development():
    request = _request()

    with pytest.raises(
        RuntimeError,
        match="requires a non-empty",
    ):
        HasAccess().has_permission(
            request,
            SimpleNamespace(),
        )


@pytest.mark.parametrize(
    "value",
    ["", " ", "\t"],
)
def test_access_permission_rejects_empty_codes(value):
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        access_permission(value)
