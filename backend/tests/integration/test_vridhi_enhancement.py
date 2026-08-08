"""Vridhi Consultants enhancement tests (V2).

Covers branding, normalized expertise, dashboard aggregation with authorization
and dual identity resolution, and the transactional audit trail. Additive only;
existing tests are untouched.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
PARTNER = "22222222-2222-2222-2222-222222222222"
STAFF_A = "44444444-4444-4444-4444-444444444444"
STAFF_B = "55555555-5555-5555-5555-555555555555"


def _h(tenant=TENANT_A, principal=PARTNER):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(principal, name, role="STAFF", tenant=TENANT_A):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=tenant, created_by=principal, updated_by=principal,
        name=name, email=f"{name}-{principal}@ex.com", role=role,
        principal_id=principal, is_active=True,
    )


def _rows(payload):
    return payload["results"] if isinstance(payload, dict) and "results" in payload else payload


# ---------------- Branding ----------------
@pytest.mark.django_db
def test_branding_fallback():
    http = HttpClient()
    _employee(PARTNER, "P", "PARTNER")
    data = http.get("/api/v1/branding/", **_h()).json()
    assert data["firm_name"] == "Vridhi Consultants"
    assert data["source"] == "fallback"
    assert data["capabilities"]["is_executive"] is True


@pytest.mark.django_db
def test_branding_uses_firm_profile():
    from contexts.organisation.models import FirmProfile

    _employee(PARTNER, "P", "PARTNER")
    FirmProfile.objects.create(tenant_id=TENANT_A, created_by=PARTNER, updated_by=PARTNER, name="Vridhi Consultants", legal_name="Vridhi LLP")
    data = HttpClient().get("/api/v1/branding/", **_h()).json()
    assert data["firm_name"] == "Vridhi Consultants"
    assert data["source"] == "firm_profile"


@pytest.mark.django_db
def test_branding_capability_false_for_staff():
    _employee(STAFF_A, "S", "STAFF")
    data = HttpClient().get("/api/v1/branding/", **_h(principal=STAFF_A)).json()
    assert data["capabilities"]["is_executive"] is False


# ---------------- Expertise ----------------
@pytest.mark.django_db
def test_expertise_crud_uniqueness_and_filter():
    emp = _employee(STAFF_A, "Alpha", "STAFF")
    http = HttpClient()
    body = {"employee_id": str(emp.id), "category": "GST", "proficiency": "ADVANCED"}
    assert http.post("/api/v1/employee-expertise/", data=body, content_type="application/json", **_h()).status_code == 201
    dup = http.post("/api/v1/employee-expertise/", data=body, content_type="application/json", **_h())
    assert dup.status_code in (400, 409)
    filtered = _rows(http.get("/api/v1/employees/?expertise=GST", **_h()).json())
    assert any(r["name"] == "Alpha" for r in filtered)


@pytest.mark.django_db
def test_expertise_tenant_isolation():
    emp = _employee(STAFF_A, "Iso", "STAFF")
    http = HttpClient()
    http.post("/api/v1/employee-expertise/", data={"employee_id": str(emp.id), "category": "TDS", "proficiency": "BASIC"}, content_type="application/json", **_h())
    other = _rows(http.get(f"/api/v1/employee-expertise/?employee_id={emp.id}", **_h(tenant=TENANT_B, principal=STAFF_B)).json())
    assert other == []


# ---------------- Executive dashboard authorization (3.4) ----------------
@pytest.mark.django_db
def test_executive_dashboard_allows_partner():
    _employee(PARTNER, "P", "PARTNER")
    resp = HttpClient().get("/api/v1/dashboard/executive/", **_h(principal=PARTNER))
    assert resp.status_code == 200
    assert "overview" in resp.json()


@pytest.mark.django_db
def test_executive_dashboard_denies_staff():
    _employee(STAFF_A, "S", "STAFF")
    resp = HttpClient().get("/api/v1/dashboard/executive/", **_h(principal=STAFF_A))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_executive_dashboard_denies_unknown_principal():
    # no Employee row for this principal -> no role -> 403
    resp = HttpClient().get("/api/v1/dashboard/executive/", **_h(principal=str(uuid.uuid4())))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_executive_dashboard_tenant_isolation():
    _employee(PARTNER, "P", "PARTNER")
    # partner in tenant A cannot get tenant B data (different principal/tenant -> 403 no role there)
    resp = HttpClient().get("/api/v1/dashboard/executive/", **_h(tenant=TENANT_B, principal=PARTNER))
    assert resp.status_code == 403


# ---------------- Audit viewer authorization (3.5) ----------------
@pytest.mark.django_db
def test_audit_viewer_allows_partner():
    _employee(PARTNER, "P", "PARTNER")
    resp = HttpClient().get("/api/v1/audit-events/", **_h(principal=PARTNER))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_audit_viewer_denies_staff():
    _employee(STAFF_A, "S", "STAFF")
    resp = HttpClient().get("/api/v1/audit-events/", **_h(principal=STAFF_A))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_audit_is_append_only():
    _employee(PARTNER, "P", "PARTNER")
    resp = HttpClient().post("/api/v1/audit-events/", data={"action": "CREATE", "entity_type": "x", "entity_id": PARTNER}, content_type="application/json", **_h(principal=PARTNER))
    assert resp.status_code in (403, 405)


# ---------------- Employee dashboard privacy (3.6) ----------------
@pytest.mark.django_db
def test_employee_dashboard_self_service():
    _employee(STAFF_A, "Self", "STAFF")
    data = HttpClient().get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert "my_work" in data


@pytest.mark.django_db
def test_employee_cannot_view_another_employee():
    _employee(STAFF_A, "A", "STAFF")
    b = _employee(STAFF_B, "B", "STAFF")
    resp = HttpClient().get(f"/api/v1/dashboard/employee/?employee_id={b.id}", **_h(principal=STAFF_A))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_partner_can_view_another_employee():
    _employee(PARTNER, "P", "PARTNER")
    b = _employee(STAFF_B, "B", "STAFF")
    resp = HttpClient().get(f"/api/v1/dashboard/employee/?employee_id={b.id}", **_h(principal=PARTNER))
    assert resp.status_code == 200


# ---------------- Identity resolution (3.7) ----------------
def _client(http):
    return http.post("/api/v1/clients/", data={"legal_name": "C", "client_type": "OTHER", "pan": "ABCDE1234F"}, content_type="application/json", **_h()).json()


@pytest.mark.django_db
def test_dashboard_counts_work_owned_by_employee_id():
    owner = _employee(STAFF_A, "OwnerEmp", "STAFF")
    http = HttpClient()
    c = _client(http)
    http.post("/api/v1/work-items/", data={"title": "W", "client_id": c["id"], "owner_user_id": str(owner.id), "priority": "NORMAL"}, content_type="application/json", **_h())
    data = http.get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["my_work"]["assigned_open"] >= 1


@pytest.mark.django_db
def test_dashboard_counts_work_owned_by_raw_principal():
    owner = _employee(STAFF_A, "OwnerRaw", "STAFF")
    http = HttpClient()
    c = _client(http)
    # owner stored as the raw principal UUID, not the Employee.id
    http.post("/api/v1/work-items/", data={"title": "W2", "client_id": c["id"], "owner_user_id": STAFF_A, "priority": "NORMAL"}, content_type="application/json", **_h())
    data = http.get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["my_work"]["assigned_open"] >= 1


@pytest.mark.django_db
def test_dashboard_no_double_count_when_both_representations_present():
    owner = _employee(STAFF_A, "OwnerBoth", "STAFF")
    http = HttpClient()
    c = _client(http)
    # one item owned by Employee.id, one by principal UUID -> total 2, no double count
    http.post("/api/v1/work-items/", data={"title": "A", "client_id": c["id"], "owner_user_id": str(owner.id), "priority": "NORMAL"}, content_type="application/json", **_h())
    http.post("/api/v1/work-items/", data={"title": "B", "client_id": c["id"], "owner_user_id": STAFF_A, "priority": "NORMAL"}, content_type="application/json", **_h())
    data = http.get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["my_work"]["assigned_open"] == 2


# ---------------- Audit transaction (3.3) ----------------
@pytest.mark.django_db
def test_status_change_writes_audit():
    owner = _employee(STAFF_A, "OwnerS", "STAFF")
    http = HttpClient()
    c = _client(http)
    w = http.post("/api/v1/work-items/", data={"title": "W", "client_id": c["id"], "owner_user_id": STAFF_A, "priority": "NORMAL"}, content_type="application/json", **_h()).json()
    http.post(f"/api/v1/work-items/{w['id']}/set_status/", data={"status": "IN_PROGRESS"}, content_type="application/json", **_h(principal=STAFF_A))
    _employee(PARTNER, "P", "PARTNER")
    events = _rows(http.get(f"/api/v1/audit-events/?entity_id={w['id']}", **_h(principal=PARTNER)).json())
    assert any(e["action"] == "STATUS_CHANGE" for e in events)


@pytest.mark.django_db
def test_optional_metadata_failure_does_not_block():
    # Optional metadata that would fail sanitization is dropped (reduced data),
    # while the mandatory audit row is still written.
    from contexts.audit.recording import record_event
    from contexts.audit.models import AuditEvent

    class Unstringable:
        def __str__(self):
            raise RuntimeError("cannot stringify")

    eid = str(uuid.uuid4())
    ev = record_event(
        tenant_id=TENANT_A, principal_id=PARTNER, action="UPDATE",
        entity_type="X", entity_id=eid,
        new={"bad": Unstringable(), "ok": "value"},
    )
    assert ev is not None
    stored = AuditEvent.objects.get(entity_id=eid)
    # sanitization fell back safely; row persisted regardless
    assert isinstance(stored.new_values, dict)


@pytest.mark.django_db
def test_core_audit_persistence_failure_propagates():
    # record_event must RAISE on core persistence failure (not swallow)
    from contexts.audit.recording import record_event

    with pytest.raises(Exception):
        # entity_id must be a valid UUID; an invalid one forces a persistence error
        record_event(tenant_id=TENANT_A, principal_id=PARTNER, action="UPDATE", entity_type="X", entity_id="not-a-uuid")


@pytest.mark.django_db
def test_mandatory_audit_failure_rolls_back_business_mutation(monkeypatch):
    # If audit persistence fails inside _transition, the status change rolls back.
    from contexts.work import views as work_views
    from contexts.work.models import WorkItem

    owner = _employee(STAFF_A, "OwnerRB", "STAFF")
    http = HttpClient()
    c = _client(http)
    w = http.post("/api/v1/work-items/", data={"title": "RB", "client_id": c["id"], "owner_user_id": STAFF_A, "priority": "NORMAL"}, content_type="application/json", **_h()).json()

    def boom(**kwargs):
        raise RuntimeError("audit db down")

    monkeypatch.setattr(work_views, "record_event", boom)
    resp = http.post(f"/api/v1/work-items/{w['id']}/set_status/", data={"status": "IN_PROGRESS"}, content_type="application/json", **_h(principal=STAFF_A))
    assert resp.status_code >= 500 or resp.status_code == 400
    # the status must NOT have persisted
    item = WorkItem.objects.get(id=w["id"])
    assert item.status == "NOT_STARTED"


@pytest.mark.django_db
def test_partner_viewing_employee_counts_employee_id_and_raw_principal_ownership():
    _employee(PARTNER, "P", "PARTNER")
    target = _employee(STAFF_B, "Target", "STAFF")
    http = HttpClient()
    c = _client(http)
    http.post("/api/v1/work-items/", data={"title": "EmpForm", "client_id": c["id"], "owner_user_id": str(target.id), "priority": "NORMAL"}, content_type="application/json", **_h())
    http.post("/api/v1/work-items/", data={"title": "PrincipalForm", "client_id": c["id"], "owner_user_id": STAFF_B, "priority": "NORMAL"}, content_type="application/json", **_h())
    data = http.get(f"/api/v1/dashboard/employee/?employee_id={target.id}", **_h(principal=PARTNER)).json()
    assert data["my_work"]["assigned_open"] == 2


@pytest.mark.django_db
def test_pending_reviews_counts_reviewer_employee_id():
    reviewer = _employee(STAFF_A, "ReviewerEmp", "STAFF")
    from contexts.work.models import WorkItem
    WorkItem.objects.create(
        tenant_id=TENANT_A, created_by=PARTNER, updated_by=PARTNER,
        title="ReviewEmp", client_id=uuid.uuid4(), owner_user_id=uuid.uuid4(),
        reviewer_user_id=reviewer.id, status="READY_FOR_REVIEW", priority="NORMAL",
    )
    data = HttpClient().get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["workload"]["pending_reviews_assigned"] == 1


@pytest.mark.django_db
def test_pending_reviews_counts_reviewer_raw_principal():
    _employee(STAFF_A, "ReviewerRaw", "STAFF")
    from contexts.work.models import WorkItem
    WorkItem.objects.create(
        tenant_id=TENANT_A, created_by=PARTNER, updated_by=PARTNER,
        title="ReviewRaw", client_id=uuid.uuid4(), owner_user_id=uuid.uuid4(),
        reviewer_user_id=STAFF_A, status="READY_FOR_REVIEW", priority="NORMAL",
    )
    data = HttpClient().get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["workload"]["pending_reviews_assigned"] == 1


@pytest.mark.django_db
def test_pending_reviews_no_double_count_across_reviewer_representations():
    reviewer = _employee(STAFF_A, "ReviewerBoth", "STAFF")
    from contexts.work.models import WorkItem
    for title, reviewer_id in (("R1", reviewer.id), ("R2", STAFF_A)):
        WorkItem.objects.create(
            tenant_id=TENANT_A, created_by=PARTNER, updated_by=PARTNER,
            title=title, client_id=uuid.uuid4(), owner_user_id=uuid.uuid4(),
            reviewer_user_id=reviewer_id, status="READY_FOR_REVIEW", priority="NORMAL",
        )
    data = HttpClient().get("/api/v1/dashboard/employee/", **_h(principal=STAFF_A)).json()
    assert data["workload"]["pending_reviews_assigned"] == 2
@pytest.mark.django_db
def test_executive_dashboard_exposes_certified_work_health():
    from contexts.work.models import WorkItem

    _employee(PARTNER, "P", "PARTNER")

    WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Executive Health Work",
        client_id=uuid.uuid4(),
        owner_user_id=PARTNER,
        priority="HIGH",
        status="IN_PROGRESS",
    )

    response = HttpClient().get(
        "/api/v1/dashboard/executive/",
        **_h(principal=PARTNER),
    )

    assert response.status_code == 200

    health = response.json()["work_health"]

    assert "healthy" in health
    assert "attention_required" in health
    assert "high_risk" in health
    assert "due_soon" in health
    assert "overdue" in health
    assert "waiting_on_client" in health
    assert "waiting_on_reviewer" in health
    assert "longest_waiting_days" in health
    assert "immediate_actions" in health



# ---------------- Mission Control Phase 5.1 ----------------

@pytest.mark.django_db
def test_employee_dashboard_mission_control_reuses_work_health():
    from datetime import timedelta
    from django.utils import timezone
    from contexts.work.models import WorkItem, WorkNote

    employee = _employee(STAFF_A, "Mission Employee", "STAFF")
    client_id = uuid.uuid4()

    work = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=STAFF_A,
        updated_by=STAFF_A,
        title="Mission Employee Work",
        client_id=client_id,
        owner_user_id=employee.id,
        priority="HIGH",
        status="IN_PROGRESS",
        due_date=timezone.now().date() + timedelta(days=1),
    )

    WorkNote.objects.create(
        tenant_id=TENANT_A,
        created_by=STAFF_A,
        updated_by=STAFF_A,
        work_item_id=work.id,
        author_user_id=STAFF_A,
        entry="Mission activity",
        from_status="NOT_STARTED",
        to_status="IN_PROGRESS",
    )

    response = HttpClient().get(
        "/api/v1/dashboard/employee/",
        **_h(principal=STAFF_A),
    )

    assert response.status_code == 200

    data = response.json()

    assert "work_health" in data
    assert "immediate_actions" in data["work_health"]
    assert "recent_activity" in data
    assert "upcoming_deadlines" in data

    assert any(
        row["work_item_id"] == str(work.id)
        for row in data["recent_activity"]
    )

    deadline = next(
        row
        for row in data["upcoming_deadlines"]
        if row["work_item_id"] == str(work.id)
    )

    assert deadline["due_state"] == "DUE_SOON"
    assert deadline["next_action"]


@pytest.mark.django_db
def test_executive_dashboard_mission_control_is_tenant_scoped():
    from contexts.work.models import WorkItem, WorkNote

    _employee(PARTNER, "Mission Partner", "PARTNER")

    local_work = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Tenant A Mission Activity",
        client_id=uuid.uuid4(),
        owner_user_id=PARTNER,
        priority="NORMAL",
        status="IN_PROGRESS",
    )

    other_work = WorkItem.objects.create(
        tenant_id=TENANT_B,
        created_by=STAFF_B,
        updated_by=STAFF_B,
        title="Tenant B Must Stay Hidden",
        client_id=uuid.uuid4(),
        owner_user_id=STAFF_B,
        priority="NORMAL",
        status="IN_PROGRESS",
    )

    WorkNote.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=local_work.id,
        author_user_id=PARTNER,
        entry="Visible activity",
    )

    WorkNote.objects.create(
        tenant_id=TENANT_B,
        created_by=STAFF_B,
        updated_by=STAFF_B,
        work_item_id=other_work.id,
        author_user_id=STAFF_B,
        entry="Hidden activity",
    )

    response = HttpClient().get(
        "/api/v1/dashboard/executive/",
        **_h(principal=PARTNER),
    )

    assert response.status_code == 200

    data = response.json()

    assert "recent_activity" in data
    assert "client_activity" in data
    assert "upcoming_deadlines" in data

    titles = {
        row["title"]
        for row in data["recent_activity"]
    }

    assert "Tenant A Mission Activity" in titles
    assert "Tenant B Must Stay Hidden" not in titles



# --- Phase 5.1 PLATFORM_ADMIN firm operational scope ---

@pytest.mark.django_db
def test_platform_admin_firm_operation_capability_is_not_firm_leadership():
    from types import SimpleNamespace

    from contexts.identity.access import (
        can_view_firm_operations,
        is_executive,
        is_platform_admin,
    )
    from contexts.identity.models import (
        MembershipStatus,
        ProviderMembership,
        ProviderRole,
    )

    principal_id = uuid.uuid4()

    ProviderMembership.objects.create(
        tenant_id=TENANT_A,
        created_by=principal_id,
        updated_by=principal_id,
        user_account_id=principal_id,
        role=ProviderRole.PLATFORM_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    principal = SimpleNamespace(
        principal_id=principal_id,
        tenant_id=uuid.UUID(TENANT_A),
    )

    assert is_platform_admin(
        uuid.UUID(TENANT_A),
        principal,
    )

    assert can_view_firm_operations(
        uuid.UUID(TENANT_A),
        principal,
    )

    # Critical boundary: operational visibility != firm leadership.
    assert not is_executive(
        uuid.UUID(TENANT_A),
        principal,
    )


@pytest.mark.django_db
def test_operations_admin_does_not_inherit_platform_operational_scope():
    from types import SimpleNamespace

    from contexts.identity.access import (
        can_view_firm_operations,
        is_platform_admin,
    )
    from contexts.identity.models import (
        MembershipStatus,
        ProviderMembership,
        ProviderRole,
    )

    principal_id = uuid.uuid4()

    ProviderMembership.objects.create(
        tenant_id=TENANT_A,
        created_by=principal_id,
        updated_by=principal_id,
        user_account_id=principal_id,
        role=ProviderRole.OPERATIONS_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    principal = SimpleNamespace(
        principal_id=principal_id,
        tenant_id=uuid.UUID(TENANT_A),
    )

    assert not is_platform_admin(
        uuid.UUID(TENANT_A),
        principal,
    )

    assert not can_view_firm_operations(
        uuid.UUID(TENANT_A),
        principal,
    )


@pytest.mark.django_db
def test_platform_admin_firm_operational_scope_is_tenant_local():
    from types import SimpleNamespace

    from contexts.identity.access import (
        can_view_firm_operations,
    )
    from contexts.identity.models import (
        MembershipStatus,
        ProviderMembership,
        ProviderRole,
    )

    principal_id = uuid.uuid4()

    ProviderMembership.objects.create(
        tenant_id=TENANT_A,
        created_by=principal_id,
        updated_by=principal_id,
        user_account_id=principal_id,
        role=ProviderRole.PLATFORM_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    foreign_principal = SimpleNamespace(
        principal_id=principal_id,
        tenant_id=uuid.UUID(TENANT_B),
    )

    assert not can_view_firm_operations(
        uuid.UUID(TENANT_B),
        foreign_principal,
    )


@pytest.mark.django_db
def test_platform_admin_can_read_existing_firm_operational_dashboard():
    from contexts.identity.models import (
        MembershipStatus,
        ProviderMembership,
        ProviderRole,
    )

    principal_id = uuid.uuid4()

    ProviderMembership.objects.create(
        tenant_id=TENANT_A,
        created_by=principal_id,
        updated_by=principal_id,
        user_account_id=principal_id,
        role=ProviderRole.PLATFORM_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    response = HttpClient().get(
        "/api/v1/dashboard/executive/",
        **_h(principal=str(principal_id)),
    )

    assert response.status_code == 200

    payload = response.json()

    assert "operations" in payload
    assert "employee_workload" in payload
    assert "client_health" in payload
    assert "work_health" in payload


@pytest.mark.django_db
def test_operations_admin_remains_denied_from_firm_operational_dashboard():
    from contexts.identity.models import (
        MembershipStatus,
        ProviderMembership,
        ProviderRole,
    )

    principal_id = uuid.uuid4()

    ProviderMembership.objects.create(
        tenant_id=TENANT_A,
        created_by=principal_id,
        updated_by=principal_id,
        user_account_id=principal_id,
        role=ProviderRole.OPERATIONS_ADMIN,
        status=MembershipStatus.ACTIVE,
    )

    response = HttpClient().get(
        "/api/v1/dashboard/executive/",
        **_h(principal=str(principal_id)),
    )

    assert response.status_code == 403



# --- Phase 5.2 Client Workspace ---

@pytest.mark.django_db
def test_client_workspace_reuses_existing_operational_projections():
    from datetime import timedelta

    from django.utils import timezone

    from contexts.work.models import (
        DocumentRequest,
        WorkItem,
        WorkNote,
    )

    http = HttpClient()
    client = _client(http)

    item = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Client Workspace GST",
        client_id=client["id"],
        owner_user_id=PARTNER,
        priority="NORMAL",
        due_date=timezone.now().date() + timedelta(days=2),
    )

    WorkNote.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=item.id,
        author_user_id=PARTNER,
        entry="Documents requested from client",
    )

    DocumentRequest.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        name="Bank Statement",
        client_id=client["id"],
        work_item_id=item.id,
        mandatory=True,
    )

    response = http.get(
        "/api/v1/client-workspace/",
        {
            "client_id": client["id"],
        },
        **_h(),
    )

    assert response.status_code == 200, response.content

    payload = response.json()

    assert payload["client_id"] == client["id"]
    assert "work_health" in payload
    assert "recent_activity" in payload
    assert "history" in payload
    assert "upcoming_deadlines" in payload

    assert any(
        row["work_item_id"] == str(item.id)
        for row in payload["recent_activity"]
    )

    assert any(
        row["work_item_id"] == str(item.id)
        for row in payload["history"]
    )

    assert any(
        row["work_item_id"] == str(item.id)
        for row in payload["upcoming_deadlines"]
    )


@pytest.mark.django_db
def test_client_workspace_is_tenant_isolated():
    http = HttpClient()
    client = _client(http)

    response = http.get(
        "/api/v1/client-workspace/",
        {
            "client_id": client["id"],
        },
        **_h(
            tenant=TENANT_B,
        ),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_client_workspace_requires_client_id():
    response = HttpClient().get(
        "/api/v1/client-workspace/",
        **_h(),
    )

    assert response.status_code == 400



# --- Phase 5.3 Work Timeline ---

@pytest.mark.django_db
def test_work_timeline_projects_existing_durable_event_sources():
    from contexts.assignment.models import AssignmentEvent
    from contexts.work.models import (
        DocumentRequest,
        WorkItem,
        WorkNote,
    )

    http = HttpClient()
    client = _client(http)

    item = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Timeline GST Return",
        client_id=client["id"],
        owner_user_id=PARTNER,
        priority="NORMAL",
    )

    AssignmentEvent.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=item.id,
        event_type="REASSIGNED",
        owner_user_id=PARTNER,
        actor_user_id=PARTNER,
        reason="Capacity balancing",
    )

    DocumentRequest.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=item.id,
        client_id=client["id"],
        name="Bank Statement",
        mandatory=True,
    )

    WorkNote.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=item.id,
        author_user_id=PARTNER,
        entry="Submitted for review.",
        from_status="IN_PROGRESS",
        to_status="READY_FOR_REVIEW",
    )

    response = http.get(
        f"/api/v1/work-items/{item.id}/history/",
        **_h(),
    )

    assert response.status_code == 200, response.content

    events = response.json()
    event_types = [
        event["event_type"]
        for event in events
    ]

    assert event_types[0] == "WORK_CREATED"
    assert "REASSIGNED" in event_types
    assert "DOCUMENT_REQUESTED" in event_types
    assert "SUBMITTED_FOR_REVIEW" in event_types

    timestamps = [
        event["created_at"]
        for event in events
    ]

    assert timestamps == sorted(timestamps)


@pytest.mark.django_db
def test_work_timeline_remains_tenant_scoped():
    from contexts.work.models import WorkItem

    item = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Tenant Timeline",
        client_id=uuid.uuid4(),
        priority="NORMAL",
    )

    response = HttpClient().get(
        f"/api/v1/work-items/{item.id}/history/",
        **_h(
            tenant=TENANT_B,
        ),
    )

    assert response.status_code == 404


# --- Phase 5.3 deterministic ordering regression ---

@pytest.mark.django_db
def test_work_timeline_keeps_creation_first_when_event_timestamps_tie():
    from contexts.assignment.models import AssignmentEvent
    from contexts.work.models import WorkItem

    http = HttpClient()

    item = WorkItem.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="Timeline ordering invariant",
        client_id=uuid.uuid4(),
        owner_user_id=PARTNER,
        priority="NORMAL",
    )

    assignment = AssignmentEvent.objects.create(
        tenant_id=TENANT_A,
        created_by=PARTNER,
        updated_by=PARTNER,
        work_item_id=item.id,
        event_type="REASSIGNED",
        owner_user_id=PARTNER,
        actor_user_id=PARTNER,
    )

    # Reproduce the precise ordering edge explicitly rather than relying
    # on execution timing or database timestamp precision.
    AssignmentEvent.objects.filter(
        id=assignment.id,
    ).update(
        created_at=item.created_at,
    )

    response = http.get(
        f"/api/v1/work-items/{item.id}/history/",
        **_h(),
    )

    assert response.status_code == 200, response.content

    events = response.json()

    assert events[0]["event_type"] == "WORK_CREATED"
    assert events[1]["event_type"] == "REASSIGNED"