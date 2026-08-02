"""Task template tests (V1 additive, ctx_generation)."""

from __future__ import annotations

import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _headers(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


@pytest.mark.django_db
def test_create_task_template():
    from django.test import Client as HttpClient

    http = HttpClient()
    resp = http.post(
        "/api/v1/task-templates/",
        data={"service_id": str(uuid.uuid4()), "name": "GST Monthly", "default_due_days": 20},
        content_type="application/json",
        **_headers(),
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["is_active"] is True


@pytest.mark.django_db
def test_duplicate_template_name_per_service_rejected():
    from django.test import Client as HttpClient

    http = HttpClient()
    service_id = str(uuid.uuid4())
    payload = {"service_id": service_id, "name": "TDS Quarterly"}
    a = http.post("/api/v1/task-templates/", data=payload, content_type="application/json", **_headers())
    assert a.status_code == 201, a.content
    b = http.post("/api/v1/task-templates/", data=payload, content_type="application/json", **_headers())
    assert b.status_code in (400, 409), b.content


@pytest.mark.django_db
def test_same_name_different_service_allowed():
    from django.test import Client as HttpClient

    http = HttpClient()
    a = http.post(
        "/api/v1/task-templates/",
        data={"service_id": str(uuid.uuid4()), "name": "Audit"},
        content_type="application/json", **_headers(),
    )
    b = http.post(
        "/api/v1/task-templates/",
        data={"service_id": str(uuid.uuid4()), "name": "Audit"},
        content_type="application/json", **_headers(),
    )
    assert a.status_code == 201 and b.status_code == 201, (a.content, b.content)
