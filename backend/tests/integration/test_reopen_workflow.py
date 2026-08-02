"""Controlled reopening tests (V1 additive).

reopen moves COMPLETED -> REWORK_REQUIRED, reviewer-gated, reason required. It
reuses the existing status vocabulary and the existing audited _transition path.
Existing transitions are unchanged (covered by the baseline workflow suite).
"""

from __future__ import annotations

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
REVIEWER = "44444444-4444-4444-4444-444444444444"
OWNER = "22222222-2222-2222-2222-222222222222"


def _h(tenant=TENANT_A, principal=OWNER):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _complete_item(http):
    """Drive a work item all the way to COMPLETED using existing actions."""
    from contexts.identity.models import Employee

    reviewer_emp = Employee.objects.create(
        tenant_id=TENANT_A, created_by=OWNER, updated_by=OWNER,
        name="Rev", email="rev-reopen@example.com", principal_id=REVIEWER,
    )
    client = http.post(
        "/api/v1/clients/",
        data={"legal_name": "RO Client", "client_type": "INDIVIDUAL"},
        content_type="application/json", **_h(),
    )
    client_id = client.json()["id"]
    created = http.post(
        "/api/v1/work-items/",
        data={
            "title": "Reopen Target", "client_id": client_id,
            "owner_user_id": OWNER, "reviewer_user_id": str(reviewer_emp.id),
        },
        content_type="application/json", **_h(),
    )
    assert created.status_code == 201, created.content
    item = created.json()
    wid = item["id"]
    # NOT_STARTED -> IN_PROGRESS (owner)
    http.post(f"/api/v1/work-items/{wid}/set_status/", data={"status": "IN_PROGRESS"}, content_type="application/json", **_h())
    # submit for review (owner)
    http.post(f"/api/v1/work-items/{wid}/submit_for_review/", **_h())
    # approve (reviewer) -> COMPLETED
    approve = http.post(f"/api/v1/work-items/{wid}/approve/", data={}, content_type="application/json", **_h(principal=REVIEWER))
    assert approve.status_code == 200, approve.content
    assert approve.json()["status"] == "COMPLETED"
    return wid, str(reviewer_emp.id)


@pytest.mark.django_db
def test_reviewer_can_reopen_completed_work():
    from django.test import Client as HttpClient

    http = HttpClient()
    wid, _ = _complete_item(http)
    resp = http.post(
        f"/api/v1/work-items/{wid}/reopen/",
        data={"comment": "Client sent revised figures"},
        content_type="application/json", **_h(principal=REVIEWER),
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "REWORK_REQUIRED"


@pytest.mark.django_db
def test_reopen_requires_reason():
    from django.test import Client as HttpClient

    http = HttpClient()
    wid, _ = _complete_item(http)
    resp = http.post(
        f"/api/v1/work-items/{wid}/reopen/",
        data={}, content_type="application/json", **_h(principal=REVIEWER),
    )
    assert resp.status_code == 400, resp.content


@pytest.mark.django_db
def test_non_reviewer_cannot_reopen():
    from django.test import Client as HttpClient

    http = HttpClient()
    wid, _ = _complete_item(http)
    resp = http.post(
        f"/api/v1/work-items/{wid}/reopen/",
        data={"comment": "x"}, content_type="application/json", **_h(principal=OWNER),
    )
    assert resp.status_code in (403, 400), resp.content


@pytest.mark.django_db
def test_cannot_reopen_non_completed_work():
    from django.test import Client as HttpClient

    http = HttpClient()
    wid, _ = _complete_item(http)
    # Reopen once (COMPLETED -> REWORK_REQUIRED)
    http.post(f"/api/v1/work-items/{wid}/reopen/", data={"comment": "again"}, content_type="application/json", **_h(principal=REVIEWER))
    # Second reopen should fail: no longer COMPLETED.
    resp = http.post(f"/api/v1/work-items/{wid}/reopen/", data={"comment": "again2"}, content_type="application/json", **_h(principal=REVIEWER))
    assert resp.status_code == 400, resp.content
