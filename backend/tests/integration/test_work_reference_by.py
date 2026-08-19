"""UX5 Change 1: WorkItem.reference_by persistence contract.

Verifies the new optional free-text ``reference_by`` field:
  * can be supplied on create and is persisted + returned;
  * round-trips on reopen (GET);
  * is optional - a Work Item created without it remains valid ("").
The field is generic Work metadata, not service-specific operational_data.
"""
from __future__ import annotations

import pytest
from django.test import Client as HttpClient

TENANT_A = "11111111-1111-1111-1111-111111111111"
OWNER = "22222222-2222-2222-2222-222222222222"
REVIEWER = "44444444-4444-4444-4444-444444444444"


def _headers(tenant=TENANT_A, principal=OWNER):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _make_client(http):
    resp = http.post(
        "/api/v1/clients/",
        data={"legal_name": "Ref Client", "client_type": "PRIVATE_LIMITED", "pan": "ABCDE1234F"},
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    return resp.json()["id"]


@pytest.mark.django_db
def test_reference_by_persists_on_create_and_reopen():
    http = HttpClient()
    client_id = _make_client(http)
    resp = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Udyam Registration",
            "client_id": client_id,
            "owner_user_id": OWNER,
            "priority": "NORMAL",
            "reference_by": "Referred by CA Sharma",
        },
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["reference_by"] == "Referred by CA Sharma"

    # Reopen (GET) returns the persisted value.
    work_id = body["id"]
    reopened = http.get(f"/api/v1/work-items/{work_id}/", **_headers())
    assert reopened.status_code == 200, reopened.content
    assert reopened.json()["reference_by"] == "Referred by CA Sharma"


@pytest.mark.django_db
def test_reference_by_is_optional():
    http = HttpClient()
    client_id = _make_client(http)
    resp = http.post(
        "/api/v1/work-items/",
        data={
            "title": "No Reference Work",
            "client_id": client_id,
            "owner_user_id": OWNER,
            "priority": "NORMAL",
        },
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    # Optional: absent input yields the blank default, not an error.
    assert resp.json().get("reference_by", "") == ""


@pytest.mark.django_db
def test_reference_by_is_editable_on_existing_work():
    http = HttpClient()
    client_id = _make_client(http)
    created = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Editable Ref",
            "client_id": client_id,
            "owner_user_id": OWNER,
            "priority": "NORMAL",
        },
        content_type="application/json",
        **_headers(),
    ).json()
    work_id = created["id"]
    patched = http.patch(
        f"/api/v1/work-items/{work_id}/",
        data={"reference_by": "Walk-in referral"},
        content_type="application/json",
        **_headers(),
    )
    assert patched.status_code == 200, patched.content
    assert patched.json()["reference_by"] == "Walk-in referral"
