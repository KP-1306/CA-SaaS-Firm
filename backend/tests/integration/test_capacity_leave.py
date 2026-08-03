"""Capacity, leave and holiday tests (Employee Operations V1)."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"
MANAGER = "44444444-4444-4444-4444-444444444444"


def _h(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(http, principal=PRINCIPAL, **over):
    payload = {"name": "Cap", "email": f"{uuid.uuid4()}@ex.com"}
    payload.update(over)
    return http.post("/api/v1/employees/", data=payload, content_type="application/json", **_h(principal=principal)).json()["id"]


@pytest.mark.django_db
def test_capacity_available_hours_default_pattern():
    """With no profile, Mon-Fri default gives base 8h on a weekday, 0 on weekend."""
    from contexts.capacity import service

    emp = uuid.uuid4()
    monday = dt.date(2026, 8, 3)   # a Monday
    saturday = dt.date(2026, 8, 8)
    assert service.available_hours_on(TENANT_A, emp, monday) == Decimal("8")
    assert service.available_hours_on(TENANT_A, emp, saturday) == Decimal("0")


@pytest.mark.django_db
def test_capacity_summary_endpoint():
    from django.test import Client

    http = Client()
    emp = _employee(http)
    start = "2026-08-03"
    end = "2026-08-07"
    resp = http.get(f"/api/v1/capacity-profiles/summary/?employee_id={emp}&start={start}&end={end}", **_h())
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "available_hours" in body and "utilization_percent" in body


@pytest.mark.django_db
def test_leave_overlap_rejected():
    from django.test import Client

    http = Client()
    emp = _employee(http)
    a = http.post(
        "/api/v1/leave-records/",
        data={"employee_id": emp, "start_date": "2026-08-10", "end_date": "2026-08-12"},
        content_type="application/json",
        **_h(),
    )
    assert a.status_code == 201, a.content
    b = http.post(
        "/api/v1/leave-records/",
        data={"employee_id": emp, "start_date": "2026-08-11", "end_date": "2026-08-13"},
        content_type="application/json",
        **_h(),
    )
    assert b.status_code == 400, b.content


@pytest.mark.django_db
def test_leave_approval_requires_capability():
    from django.test import Client
    from contexts.identity.models import Employee

    http = Client()
    emp = _employee(http)
    leave = http.post(
        "/api/v1/leave-records/",
        data={"employee_id": emp, "start_date": "2026-09-01", "end_date": "2026-09-02"},
        content_type="application/json",
        **_h(),
    ).json()
    # A non-manager principal cannot approve.
    denied = http.post(f"/api/v1/leave-records/{leave['id']}/approve/", data={}, content_type="application/json", **_h(principal="99999999-9999-9999-9999-999999999999"))
    assert denied.status_code in (403, 400), denied.content
    # A manager can approve.
    Employee.objects.create(
        tenant_id=TENANT_A, created_by=MANAGER, updated_by=MANAGER,
        name="Mgr", email="mgr-cap@ex.com", role="MANAGER", principal_id=MANAGER,
    )
    ok = http.post(f"/api/v1/leave-records/{leave['id']}/approve/", data={}, content_type="application/json", **_h(principal=MANAGER))
    assert ok.status_code == 200, ok.content
    assert ok.json()["status"] == "APPROVED"


@pytest.mark.django_db
def test_approved_leave_reduces_availability():
    from django.test import Client
    from contexts.capacity import service
    from contexts.capacity.models import LeaveRecord, LeaveStatus

    http = Client()
    emp = _employee(http)
    # Directly create an approved full-day leave on a Monday.
    LeaveRecord.objects.create(
        tenant_id=TENANT_A, created_by=PRINCIPAL, updated_by=PRINCIPAL,
        employee_id=emp, start_date=dt.date(2026, 8, 3), end_date=dt.date(2026, 8, 3),
        status=LeaveStatus.APPROVED,
    )
    assert service.available_hours_on(TENANT_A, uuid.UUID(emp), dt.date(2026, 8, 3)) == Decimal("0")


@pytest.mark.django_db
def test_holiday_zeroes_availability():
    from django.test import Client
    from contexts.capacity import service
    from contexts.capacity.models import Holiday

    http = Client()
    emp = _employee(http)
    Holiday.objects.create(
        tenant_id=TENANT_A, created_by=PRINCIPAL, updated_by=PRINCIPAL,
        name="Independence Day", holiday_date=dt.date(2026, 8, 3),
    )
    assert service.available_hours_on(TENANT_A, uuid.UUID(emp), dt.date(2026, 8, 3)) == Decimal("0")
