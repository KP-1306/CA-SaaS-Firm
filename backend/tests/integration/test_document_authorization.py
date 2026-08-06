from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import Client as HttpClient
from rest_framework.test import APIRequestFactory

from contexts.authorization.models import (
    Access,
    AccessProfile,
    RoleAccess,
    RoleTemplate,
)
from contexts.authorization.permissions import (
    DocumentAttachmentAccessPermission,
    DocumentRequestAccessPermission,
)
from contexts.authorization.services import EffectiveAccess
from contexts.identity.models import ProviderRole
from contexts.work.views import (
    DocumentAttachmentViewSet,
    DocumentRequestViewSet,
)
from tests.integration.test_vridhi_consultant_admin import (
    OTHER_PRINCIPAL,
    TENANT,
    _identity,
    _login,
)


pytestmark = pytest.mark.django_db


def _grant(account, *codes: str) -> AccessProfile:
    role = RoleTemplate.objects.create(
        tenant_id=TENANT,
        code=f"DOC_{account.id.hex[:10].upper()}",
        name="Test Document Role",
        is_system=False,
        is_active=True,
    )

    for code in codes:
        access, _ = Access.objects.get_or_create(
            code=code,
            defaults={
                "module": "Documents",
                "name": code,
                "is_active": True,
            },
        )

        RoleAccess.objects.create(
            role=role,
            access=access,
        )

    return AccessProfile.objects.create(
        tenant_id=TENANT,
        user_account_id=account.id,
        role=role,
        is_active=True,
    )


def _permission_request(account, *codes: str):
    request = APIRequestFactory().post(
        "/api/v1/document-requests/test/",
        {},
        format="json",
    )
    request.vridhi_account = account
    request.vridhi_membership = SimpleNamespace(
        tenant_id=TENANT,
    )
    request.auth = None
    request.effective_access = EffectiveAccess(
        tenant_id=TENANT,
        user_account_id=account.id,
        role_code="TEST_DOCUMENT_ROLE",
        access_codes=frozenset(codes),
        department_ids=(),
        team_ids=(),
        service_ids=(),
    )
    return request


def test_document_view_capability_allows_request_and_attachment_lists():
    account, _, _ = _identity(
        email="document-viewer@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "documents.view")

    http = HttpClient()
    _login(http, account)

    requests_response = http.get(
        "/api/v1/document-requests/"
    )
    attachments_response = http.get(
        "/api/v1/document-attachments/"
    )

    assert requests_response.status_code == 200, requests_response.content
    assert attachments_response.status_code == 200, attachments_response.content


def test_user_without_document_view_is_denied():
    account, _, _ = _identity(
        email="document-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    http = HttpClient()
    _login(http, account)

    response = http.get("/api/v1/document-requests/")

    assert response.status_code == 403
    assert "documents.view" in response.content.decode()


def test_document_view_does_not_allow_request_creation():
    account, _, _ = _identity(
        email="document-readonly@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    _grant(account, "documents.view")

    http = HttpClient()
    _login(http, account)

    response = http.post(
        "/api/v1/document-requests/",
        data={},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "documents.upload" in response.content.decode()


def test_document_request_action_mapping_is_exact():
    account, _, _ = _identity(
        email="document-map@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    cases = (
        ("list", "documents.view"),
        ("retrieve", "documents.view"),
        ("attachments", "documents.view"),
        ("create", "documents.upload"),
        ("update", "documents.upload"),
        ("partial_update", "documents.upload"),
        ("upload", "documents.upload"),
        ("verify", "documents.review"),
        ("destroy", "documents.view"),
    )

    for action, capability in cases:
        request = _permission_request(account, capability)

        assert DocumentRequestAccessPermission().has_permission(
            request,
            SimpleNamespace(action=action),
        )


def test_document_attachment_action_mapping_is_exact():
    account, _, _ = _identity(
        email="attachment-map@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )

    cases = (
        ("list", "documents.view"),
        ("retrieve", "documents.view"),
        ("download", "documents.view"),
        ("create", "documents.view"),
        ("update", "documents.view"),
        ("partial_update", "documents.view"),
        ("destroy", "documents.view"),
        ("review", "documents.review"),
        ("resolve_duplicate", "documents.review"),
        ("mark_canonical", "documents.approve"),
    )

    for action, capability in cases:
        request = _permission_request(account, capability)

        assert DocumentAttachmentAccessPermission().has_permission(
            request,
            SimpleNamespace(action=action),
        )


def test_document_review_requires_review_capability():
    account, _, _ = _identity(
        email="document-review-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    request = _permission_request(
        account,
        "documents.view",
        "documents.upload",
    )

    with patch(
        "contexts.authorization.permissions.record_auth_event",
    ):
        with pytest.raises(Exception) as exc:
            DocumentRequestAccessPermission().has_permission(
                request,
                SimpleNamespace(action="verify"),
            )

    assert "documents.review" in str(exc.value)


def test_mark_canonical_requires_approval_capability():
    account, _, _ = _identity(
        email="document-approval-denied@vridhi.example",
        principal=OTHER_PRINCIPAL,
        role=ProviderRole.IMPLEMENTATION_CONSULTANT,
    )
    request = _permission_request(
        account,
        "documents.view",
        "documents.review",
    )

    with patch(
        "contexts.authorization.permissions.record_auth_event",
    ):
        with pytest.raises(Exception) as exc:
            DocumentAttachmentAccessPermission().has_permission(
                request,
                SimpleNamespace(action="mark_canonical"),
            )

    assert "documents.approve" in str(exc.value)


def test_document_viewsets_use_certified_permission_classes():
    assert DocumentRequestViewSet.permission_classes == [
        __import__(
            "rest_framework.permissions",
            fromlist=["IsAuthenticated"],
        ).IsAuthenticated,
        DocumentRequestAccessPermission,
    ]

    assert DocumentAttachmentViewSet.permission_classes == [
        __import__(
            "rest_framework.permissions",
            fromlist=["IsAuthenticated"],
        ).IsAuthenticated,
        DocumentAttachmentAccessPermission,
    ]


def test_legacy_header_document_compatibility_remains_test_only():
    request_response = HttpClient().get(
        "/api/v1/document-requests/",
        HTTP_X_TENANT_ID=str(TENANT),
        HTTP_X_PRINCIPAL_ID=str(OTHER_PRINCIPAL),
    )

    attachment_response = HttpClient().get(
        "/api/v1/document-attachments/",
        HTTP_X_TENANT_ID=str(TENANT),
        HTTP_X_PRINCIPAL_ID=str(OTHER_PRINCIPAL),
    )

    assert request_response.status_code == 200
    assert attachment_response.status_code == 200
