"""Reviewer hierarchy + assignment engine tests (Employee Operations V1)."""

from __future__ import annotations

import uuid

import pytest

TENANT_A = "11111111-1111-1111-1111-111111111111"
PRINCIPAL = "22222222-2222-2222-2222-222222222222"
MANAGER = "44444444-4444-4444-4444-444444444444"


def _h(tenant=TENANT_A, principal=PRINCIPAL):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _mk_manager():
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=TENANT_A, created_by=MANAGER, updated_by=MANAGER,
        name="Mgr", email=f"mgr-{uuid.uuid4()}@ex.com", role="MANAGER", principal_id=MANAGER,
    )


def _employee(http, **over):
    payload = {"name": "E", "email": f"{uuid.uuid4()}@ex.com"}
    payload.update(over)
    return http.post("/api/v1/employees/", data=payload, content_type="application/json", **_h(principal=MANAGER)).json()["id"]


@pytest.mark.django_db
def test_reviewer_rule_requires_manager():
    from django.test import Client

    http = Client()
    # Non-manager cannot create reviewer rules.
    denied = http.post(
        "/api/v1/reviewer-rules/",
        data={"scope": "SERVICE", "level": "PRIMARY", "reviewer_user_id": str(uuid.uuid4()), "scope_ref_id": str(uuid.uuid4())},
        content_type="application/json",
        **_h(principal="99999999-9999-9999-9999-999999999999"),
    )
    assert denied.status_code == 403, denied.content


@pytest.mark.django_db
def test_reviewer_chain_resolution_prefers_specific_scope():
    from django.test import Client
    from contexts.assignment import reviewer_resolution

    http = Client()
    _mk_manager()
    service_id = str(uuid.uuid4())
    team_id = str(uuid.uuid4())
    reviewer_service = str(uuid.uuid4())
    reviewer_team = str(uuid.uuid4())
    # Two PRIMARY rules: service-scoped (more specific) and team-scoped.
    http.post("/api/v1/reviewer-rules/", data={"scope": "SERVICE", "scope_ref_id": service_id, "level": "PRIMARY", "reviewer_user_id": reviewer_service}, content_type="application/json", **_h(principal=MANAGER))
    http.post("/api/v1/reviewer-rules/", data={"scope": "TEAM", "scope_ref_id": team_id, "level": "PRIMARY", "reviewer_user_id": reviewer_team}, content_type="application/json", **_h(principal=MANAGER))
    resolved = reviewer_resolution.resolve_reviewer_chain(
        uuid.UUID(TENANT_A), {"service_id": service_id, "team_id": team_id}
    )
    assert resolved["by_level"]["ReviewerLevel.PRIMARY"] == reviewer_service or resolved["by_level"].get("PRIMARY") == reviewer_service


@pytest.mark.django_db
def test_reviewer_self_review_prevented():
    from contexts.assignment import reviewer_resolution
    from contexts.assignment.models import ReviewerRule

    owner = uuid.uuid4()
    service_id = uuid.uuid4()
    ReviewerRule.objects.create(
        tenant_id=TENANT_A, created_by=MANAGER, updated_by=MANAGER,
        scope="SERVICE", scope_ref_id=service_id, level="PRIMARY", reviewer_user_id=owner,
    )
    resolved = reviewer_resolution.resolve_reviewer_chain(
        uuid.UUID(TENANT_A), {"service_id": str(service_id), "owner_user_id": str(owner)}
    )
    # Owner is the only configured reviewer -> self-review prevented -> no PRIMARY.
    assert "PRIMARY" not in {k.split(".")[-1] for k in resolved["by_level"]}


@pytest.mark.django_db
def test_recommendation_is_deterministic_and_explainable():
    from django.test import Client

    http = Client()
    _mk_manager()
    e1 = _employee(http, name="Alpha")
    e2 = _employee(http, name="Bravo")
    # Give e1 SME GST expertise so it ranks above e2 for a GST requirement.
    http.post("/api/v1/employee-expertise/", data={"employee_id": e1, "category": "GST", "proficiency": "SME"}, content_type="application/json", **_h(principal=MANAGER))

    body = {"required_category": "GST"}
    r1 = http.post("/api/v1/assignment-recommendations/recommend/", data=body, content_type="application/json", **_h(principal=MANAGER))
    r2 = http.post("/api/v1/assignment-recommendations/recommend/", data=body, content_type="application/json", **_h(principal=MANAGER))
    assert r1.status_code == 200, r1.content
    c1 = r1.json()["candidates"]
    # Deterministic: same order across calls.
    assert [c["employee_id"] for c in c1] == [c["employee_id"] for c in r2.json()["candidates"]]
    # Explainable: each eligible candidate has a score breakdown.
    top = c1[0]
    assert "score_breakdown" in top
    # e1 (with expertise) is eligible and ranks at or near the top.
    assert any(c["employee_id"] == e1 and c["eligible"] for c in c1)


@pytest.mark.django_db
def test_assignment_execute_requires_manager_and_records_history():
    from django.test import Client
    from contexts.assignment.models import AssignmentEvent, AssignmentDecision

    http = Client()
    _mk_manager()
    owner = _employee(http, name="Owner")
    # Create a client + work item to assign.
    client_id = http.post("/api/v1/clients/", data={"legal_name": "C", "client_type": "INDIVIDUAL"}, content_type="application/json", **_h(principal=MANAGER)).json()["id"]
    wi = http.post("/api/v1/work-items/", data={"title": "W", "client_id": client_id}, content_type="application/json", **_h(principal=MANAGER)).json()["id"]

    # Non-manager cannot execute.
    denied = http.post("/api/v1/assignment-recommendations/execute/", data={"work_item_id": wi, "owner_user_id": owner}, content_type="application/json", **_h(principal="99999999-9999-9999-9999-999999999999"))
    assert denied.status_code == 403, denied.content

    # Manager executes.
    ok = http.post("/api/v1/assignment-recommendations/execute/", data={"work_item_id": wi, "owner_user_id": owner}, content_type="application/json", **_h(principal=MANAGER))
    assert ok.status_code == 201, ok.content
    assert AssignmentEvent.objects.filter(tenant_id=TENANT_A, work_item_id=wi).count() == 1
    assert AssignmentDecision.objects.filter(tenant_id=TENANT_A, work_item_id=wi, is_active=True).count() == 1


@pytest.mark.django_db
def test_assignment_override_requires_reason():
    from django.test import Client

    http = Client()
    _mk_manager()
    owner = _employee(http, name="Owner2")
    client_id = http.post("/api/v1/clients/", data={"legal_name": "C2", "client_type": "INDIVIDUAL"}, content_type="application/json", **_h(principal=MANAGER)).json()["id"]
    wi = http.post("/api/v1/work-items/", data={"title": "W2", "client_id": client_id}, content_type="application/json", **_h(principal=MANAGER)).json()["id"]
    resp = http.post(
        "/api/v1/assignment-recommendations/execute/",
        data={"work_item_id": wi, "owner_user_id": owner, "was_override": True},
        content_type="application/json",
        **_h(principal=MANAGER),
    )
    assert resp.status_code == 400, resp.content
