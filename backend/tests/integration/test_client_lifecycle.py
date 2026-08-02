"""Client lifecycle tests (additive V1).

Verifies the new lifecycle_status field and dated transitions, and that the
existing engagement_status field is preserved and independent.
"""

from __future__ import annotations

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _headers(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


@pytest.mark.django_db
def test_new_client_defaults_to_prospect():
    from django.test import Client as HttpClient

    http = HttpClient()
    resp = http.post(
        "/api/v1/clients/",
        data={"legal_name": "LC One", "client_type": "INDIVIDUAL"},
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["lifecycle_status"] == "PROSPECT"
    # engagement_status keeps its own independent default.
    assert body["engagement_status"] == "ACTIVE"


@pytest.mark.django_db
def test_lifecycle_transition_and_dates_persist():
    from django.test import Client as HttpClient

    http = HttpClient()
    create = http.post(
        "/api/v1/clients/",
        data={"legal_name": "LC Two", "client_type": "INDIVIDUAL"},
        content_type="application/json",
        **_headers(),
    )
    assert create.status_code == 201, create.content
    client_id = create.json()["id"]

    patch = http.patch(
        f"/api/v1/clients/{client_id}/",
        data={
            "lifecycle_status": "ACTIVE",
            "activation_date": "2026-04-01",
            "onboarding_date": "2026-03-15",
        },
        content_type="application/json",
        **_headers(),
    )
    assert patch.status_code == 200, patch.content
    body = patch.json()
    assert body["lifecycle_status"] == "ACTIVE"
    assert body["activation_date"] == "2026-04-01"
    assert body["onboarding_date"] == "2026-03-15"


@pytest.mark.django_db
def test_suspension_and_closure_reasons_persist():
    from django.test import Client as HttpClient

    http = HttpClient()
    create = http.post(
        "/api/v1/clients/",
        data={"legal_name": "LC Three", "client_type": "INDIVIDUAL"},
        content_type="application/json",
        **_headers(),
    )
    client_id = create.json()["id"]
    resp = http.patch(
        f"/api/v1/clients/{client_id}/",
        data={
            "lifecycle_status": "SUSPENDED",
            "suspension_date": "2026-05-01",
            "suspension_reason": "Non-payment",
        },
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["suspension_reason"] == "Non-payment"


@pytest.mark.django_db
def test_engagement_status_still_settable_independently():
    from django.test import Client as HttpClient

    http = HttpClient()
    create = http.post(
        "/api/v1/clients/",
        data={
            "legal_name": "LC Four",
            "client_type": "INDIVIDUAL",
            "engagement_status": "ON_HOLD",
        },
        content_type="application/json",
        **_headers(),
    )
    assert create.status_code == 201, create.content
    body = create.json()
    assert body["engagement_status"] == "ON_HOLD"
    assert body["lifecycle_status"] == "PROSPECT"  # unchanged by engagement_status
