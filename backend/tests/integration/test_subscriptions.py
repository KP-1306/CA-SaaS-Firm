"""Client service subscription tests (V1 additive, ctx_generation)."""

from __future__ import annotations

import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _headers(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _client_and_service(http):
    c = http.post(
        "/api/v1/clients/",
        data={"legal_name": "Sub Client", "client_type": "INDIVIDUAL"},
        content_type="application/json",
        **_headers(),
    )
    assert c.status_code == 201, c.content
    return c.json()["id"], str(uuid.uuid4())


@pytest.mark.django_db
def test_create_subscription():
    from django.test import Client as HttpClient

    http = HttpClient()
    client_id, service_id = _client_and_service(http)
    resp = http.post(
        "/api/v1/client-service-subscriptions/",
        data={"client_id": client_id, "service_id": service_id, "frequency": "MONTHLY"},
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["status"] == "ACTIVE"


@pytest.mark.django_db
def test_duplicate_subscription_rejected():
    from django.test import Client as HttpClient

    http = HttpClient()
    client_id, service_id = _client_and_service(http)
    payload = {"client_id": client_id, "service_id": service_id}
    first = http.post(
        "/api/v1/client-service-subscriptions/",
        data=payload, content_type="application/json", **_headers(),
    )
    assert first.status_code == 201, first.content
    second = http.post(
        "/api/v1/client-service-subscriptions/",
        data=payload, content_type="application/json", **_headers(),
    )
    assert second.status_code in (400, 409), second.content


@pytest.mark.django_db
def test_subscription_is_tenant_scoped():
    from django.test import Client as HttpClient

    http = HttpClient()
    client_id, service_id = _client_and_service(http)
    http.post(
        "/api/v1/client-service-subscriptions/",
        data={"client_id": client_id, "service_id": service_id},
        content_type="application/json", **_headers(),
    )
    # Tenant B sees none of tenant A's subscriptions.
    listing = http.get(
        "/api/v1/client-service-subscriptions/", **_headers(tenant=TENANT_B)
    )
    assert listing.status_code == 200, listing.content
    data = listing.json()
    rows = data.get("results", data) if isinstance(data, dict) else data
    assert rows == [] or len(rows) == 0
