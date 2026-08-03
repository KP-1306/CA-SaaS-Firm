"""Employee foundation + organisation structure tests (Employee Operations V1)."""

from __future__ import annotations

import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _h(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _mk_employee(http, **over):
    payload = {"name": "Emp", "email": f"{uuid.uuid4()}@ex.com"}
    payload.update(over)
    return http.post("/api/v1/employees/", data=payload, content_type="application/json", **_h())


@pytest.mark.django_db
def test_employee_create_with_employment_fields():
    from django.test import Client

    http = Client()
    resp = _mk_employee(
        http,
        employee_code="E001",
        employment_type="FULL_TIME",
        employment_status="CONFIRMED",
        joining_date="2026-01-01",
        timezone="Asia/Kolkata",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["employment_type"] == "FULL_TIME"
    assert body["timezone"] == "Asia/Kolkata"


@pytest.mark.django_db
def test_employee_email_unique_per_tenant():
    from django.test import Client

    http = Client()
    a = _mk_employee(http, email="dup@ex.com")
    assert a.status_code == 201, a.content
    b = _mk_employee(http, email="dup@ex.com")
    assert b.status_code == 400, b.content


@pytest.mark.django_db
def test_employee_code_unique_when_present():
    from django.test import Client

    http = Client()
    a = _mk_employee(http, employee_code="SAME")
    assert a.status_code == 201, a.content
    b = _mk_employee(http, employee_code="SAME")
    assert b.status_code == 400, b.content
    # Blank codes never collide.
    c = _mk_employee(http, employee_code="")
    d = _mk_employee(http, employee_code="")
    assert c.status_code == 201 and d.status_code == 201, (c.content, d.content)


@pytest.mark.django_db
def test_employee_tenant_isolation():
    from django.test import Client

    http = Client()
    _mk_employee(http)
    listing = http.get("/api/v1/employees/", **_h(tenant=TENANT_B))
    assert listing.status_code == 200
    data = listing.json()
    rows = data.get("results", data) if isinstance(data, dict) else data
    assert len(rows) == 0


@pytest.mark.django_db
def test_department_and_designation_crud():
    from django.test import Client

    http = Client()
    d = http.post("/api/v1/departments/", data={"name": "Direct Tax", "code": "DT"}, content_type="application/json", **_h())
    assert d.status_code == 201, d.content
    dup = http.post("/api/v1/departments/", data={"name": "Direct Tax 2", "code": "DT"}, content_type="application/json", **_h())
    assert dup.status_code == 400, dup.content
    desg = http.post("/api/v1/designations/", data={"name": "Manager", "code": "MGR", "rank": 3}, content_type="application/json", **_h())
    assert desg.status_code == 201, desg.content


@pytest.mark.django_db
def test_team_membership_active_uniqueness():
    from django.test import Client

    http = Client()
    emp = _mk_employee(http).json()["id"]
    team_id = str(uuid.uuid4())
    a = http.post("/api/v1/team-memberships/", data={"employee_id": emp, "team_id": team_id}, content_type="application/json", **_h())
    assert a.status_code == 201, a.content
    b = http.post("/api/v1/team-memberships/", data={"employee_id": emp, "team_id": team_id}, content_type="application/json", **_h())
    assert b.status_code == 400, b.content


@pytest.mark.django_db
def test_reporting_self_report_rejected():
    from django.test import Client

    http = Client()
    emp = _mk_employee(http).json()["id"]
    resp = http.post(
        "/api/v1/reporting-relationships/",
        data={"employee_id": emp, "manager_id": emp},
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 400, resp.content


@pytest.mark.django_db
def test_reporting_circular_rejected():
    from django.test import Client

    http = Client()
    a = _mk_employee(http).json()["id"]
    b = _mk_employee(http).json()["id"]
    # a reports to b
    r1 = http.post("/api/v1/reporting-relationships/", data={"employee_id": a, "manager_id": b}, content_type="application/json", **_h())
    assert r1.status_code == 201, r1.content
    # b reports to a -> cycle -> rejected
    r2 = http.post("/api/v1/reporting-relationships/", data={"employee_id": b, "manager_id": a}, content_type="application/json", **_h())
    assert r2.status_code == 400, r2.content
