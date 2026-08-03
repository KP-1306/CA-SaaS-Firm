"""Expertise engine + skill catalogue tests (Employee Operations V1)."""

from __future__ import annotations

import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"


def _h(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(http):
    return http.post(
        "/api/v1/employees/",
        data={"name": "Exp", "email": f"{uuid.uuid4()}@ex.com"},
        content_type="application/json",
        **_h(),
    ).json()["id"]


@pytest.mark.django_db
def test_expertise_five_level_proficiency():
    from django.test import Client

    http = Client()
    emp = _employee(http)
    resp = http.post(
        "/api/v1/employee-expertise/",
        data={"employee_id": emp, "category": "GST", "proficiency": "SME", "reviewer_eligible": True},
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["proficiency"] == "SME"
    assert resp.json()["reviewer_eligible"] is True


@pytest.mark.django_db
def test_expertise_duplicate_active_rejected():
    from django.test import Client

    http = Client()
    emp = _employee(http)
    a = http.post("/api/v1/employee-expertise/", data={"employee_id": emp, "category": "TDS"}, content_type="application/json", **_h())
    assert a.status_code == 201, a.content
    b = http.post("/api/v1/employee-expertise/", data={"employee_id": emp, "category": "TDS"}, content_type="application/json", **_h())
    assert b.status_code == 400, b.content


@pytest.mark.django_db
def test_skill_catalogue_custom_skill():
    from django.test import Client

    http = Client()
    resp = http.post(
        "/api/v1/skill-catalogue/",
        data={"name": "Ind AS 115", "code": "INDAS115", "is_custom": True},
        content_type="application/json",
        **_h(),
    )
    assert resp.status_code == 201, resp.content
    dup = http.post("/api/v1/skill-catalogue/", data={"name": "x", "code": "INDAS115"}, content_type="application/json", **_h())
    assert dup.status_code == 400, dup.content


@pytest.mark.django_db
def test_proficiency_remap_is_reversible_mapping():
    """Check the migration remap mapping (forward + reverse) is consistent."""
    import importlib

    m = importlib.import_module("contexts.identity.migrations.0005_expertise_engine")
    assert m._FORWARD == {"BASIC": "BEGINNER", "EXPERT": "SME"}
    assert m._REVERSE == {"BEGINNER": "BASIC", "SME": "EXPERT"}
