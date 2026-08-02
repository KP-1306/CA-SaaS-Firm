"""Entity-aware PAN policy tests (Vridhi Core Workflow + Client Management V1).

Resolves the documented legacy mismatch explicitly. Runs against the internal
plane exactly like the existing workflow tests.
"""

from __future__ import annotations

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _headers(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _create(http, **fields):
    payload = {"legal_name": "PAN Co", "client_type": "PRIVATE_LIMITED"}
    payload.update(fields)
    return http.post(
        "/api/v1/clients/", data=payload, content_type="application/json", **_headers()
    )


@pytest.mark.django_db
def test_valid_pan_is_accepted_and_uppercased():
    from django.test import Client as HttpClient

    http = HttpClient()
    resp = _create(http, pan="abcde1234f", lifecycle_status="ACTIVE")
    assert resp.status_code == 201, resp.content
    assert resp.json()["pan"] == "ABCDE1234F"


@pytest.mark.django_db
def test_invalid_pan_is_rejected():
    from django.test import Client as HttpClient

    http = HttpClient()
    resp = _create(http, pan="XYZ12", lifecycle_status="ACTIVE")
    assert resp.status_code == 400
    assert "pan" in resp.json()


@pytest.mark.django_db
def test_pan_required_for_company_past_onboarding():
    from django.test import Client as HttpClient

    http = HttpClient()
    # PRIVATE_LIMITED + ACTIVE and no PAN -> required -> rejected.
    resp = _create(http, client_type="PRIVATE_LIMITED", lifecycle_status="ACTIVE")
    assert resp.status_code == 400
    assert "pan" in resp.json()


@pytest.mark.django_db
def test_pan_optional_during_onboarding():
    from django.test import Client as HttpClient

    http = HttpClient()
    # Same company type but still ONBOARDING -> PAN may be absent.
    resp = _create(http, client_type="PRIVATE_LIMITED", lifecycle_status="ONBOARDING")
    assert resp.status_code == 201, resp.content
    assert resp.json()["pan"] == ""


@pytest.mark.django_db
def test_pan_optional_for_individual():
    from django.test import Client as HttpClient

    http = HttpClient()
    resp = _create(http, client_type="INDIVIDUAL", lifecycle_status="ACTIVE")
    assert resp.status_code == 201, resp.content


@pytest.mark.django_db
def test_multiple_blank_pans_do_not_violate_uniqueness():
    from django.test import Client as HttpClient

    http = HttpClient()
    r1 = _create(http, legal_name="Blank One", client_type="INDIVIDUAL")
    r2 = _create(http, legal_name="Blank Two", client_type="INDIVIDUAL")
    assert r1.status_code == 201 and r2.status_code == 201, (r1.content, r2.content)


@pytest.mark.django_db
def test_duplicate_populated_pan_is_rejected():
    from django.test import Client as HttpClient

    http = HttpClient()
    r1 = _create(http, legal_name="Dup One", pan="ABCDE1234F", lifecycle_status="ACTIVE")
    assert r1.status_code == 201, r1.content
    r2 = _create(http, legal_name="Dup Two", pan="ABCDE1234F", lifecycle_status="ACTIVE")
    assert r2.status_code in (400, 409), r2.content
