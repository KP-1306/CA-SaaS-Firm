"""C4 ownership / locking authorization tests.

These are NEW tests (added per approval). They do not modify existing tests.
Owner and reviewer are both created as real Employee rows linked to their
principal ids, matching the existing Employee-to-principal mapping used by the
C4 ownership helpers.
"""

from __future__ import annotations

import io

import pytest
from django.test import Client as HttpClient

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
OWNER = "22222222-2222-2222-2222-222222222222"
REVIEWER = "44444444-4444-4444-4444-444444444444"
OTHER = "55555555-5555-5555-5555-555555555555"


def _headers(tenant=TENANT_A, principal=OWNER):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _employee(principal, name, tenant=TENANT_A):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=tenant, created_by=OWNER, updated_by=OWNER,
        name=name, email=f"{name}-{principal}@example.com", principal_id=principal,
    )


def _make_work(http):
    owner_emp = _employee(OWNER, "Owner")
    reviewer_emp = _employee(REVIEWER, "Reviewer")
    client_resp = http.post(
        "/api/v1/clients/",
        data={"legal_name": "C4 Client", "client_type": "PRIVATE_LIMITED", "pan": "ABCDE1234F"},
        content_type="application/json", **_headers(),
    )
    assert client_resp.status_code == 201, client_resp.content
    payload = {
        "title": "C4 Work", "client_id": client_resp.json()["id"],
        "owner_user_id": str(owner_emp.id), "reviewer_user_id": str(reviewer_emp.id),
        "priority": "NORMAL",
    }
    resp = http.post("/api/v1/work-items/", data=payload, content_type="application/json", **_headers())
    assert resp.status_code == 201, resp.content
    return resp.json()


def _set(http, wid, status, comment="", principal=OWNER):
    body = {"status": status}
    if comment:
        body["comment"] = comment
    return http.post(f"/api/v1/work-items/{wid}/set_status/", data=body,
                     content_type="application/json", **_headers(principal=principal))


def _to_ready(http, w):
    assert _set(http, w["id"], "IN_PROGRESS").status_code == 200
    assert _set(http, w["id"], "READY_FOR_REVIEW").status_code == 200


# ---- owner-controlled states ----
@pytest.mark.django_db
def test_owner_can_edit_in_not_started():
    http = HttpClient()
    w = _make_work(http)
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "Edited"},
                      content_type="application/json", **_headers(principal=OWNER))
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_owner_can_edit_in_in_progress():
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "Edited2"},
                      content_type="application/json", **_headers(principal=OWNER))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_reviewer_cannot_owner_edit_in_in_progress():
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "X"},
                      content_type="application/json", **_headers(principal=REVIEWER))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_other_user_cannot_edit():
    http = HttpClient()
    w = _make_work(http)
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "X"},
                      content_type="application/json", **_headers(principal=OTHER))
    assert resp.status_code == 403


# ---- READY_FOR_REVIEW lock ----
@pytest.mark.django_db
def test_owner_cannot_patch_in_ready():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "X"},
                      content_type="application/json", **_headers(principal=OWNER))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_owner_cannot_set_status_in_ready():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    resp = _set(http, w["id"], "IN_PROGRESS", principal=OWNER)
    # The established generic-transition contract reports an invalid transition
    # as 400; dedicated reviewer actions remain the only route out of review.
    assert resp.status_code == 400


@pytest.mark.django_db
def test_owner_cannot_upload_internal_in_ready():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    fh = io.BytesIO(b"%PDF-1.4")
    fh.name = "x.pdf"
    resp = http.post(f"/api/v1/work-items/{w['id']}/upload_internal/", data={"file": fh},
                     **_headers(principal=OWNER))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_owner_cannot_change_control_fields_via_patch():
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"status": "COMPLETED"},
                      content_type="application/json", **_headers(principal=OWNER))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assigned_reviewer_can_approve_in_ready():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    resp = http.post(f"/api/v1/work-items/{w['id']}/approve/", data={},
                     content_type="application/json", **_headers(principal=REVIEWER))
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


@pytest.mark.django_db
def test_unassigned_reviewer_cannot_review():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    resp = http.post(f"/api/v1/work-items/{w['id']}/approve/", data={},
                     content_type="application/json", **_headers(principal=OTHER))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_cross_tenant_cannot_access():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    resp = http.post(f"/api/v1/work-items/{w['id']}/approve/", data={},
                     content_type="application/json", **_headers(tenant=TENANT_B, principal=REVIEWER))
    assert resp.status_code in (403, 404)


# ---- REWORK restores owner ----
@pytest.mark.django_db
def test_rework_restores_owner_edit():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    http.post(f"/api/v1/work-items/{w['id']}/return_for_rework/", data={"comment": "fix"},
              content_type="application/json", **_headers(principal=REVIEWER))
    resp = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "Reworked"},
                      content_type="application/json", **_headers(principal=OWNER))
    assert resp.status_code == 200


# ---- terminal immutability ----
@pytest.mark.django_db
def test_completed_is_read_only():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    http.post(f"/api/v1/work-items/{w['id']}/approve/", data={},
              content_type="application/json", **_headers(principal=REVIEWER))
    patch = http.patch(f"/api/v1/work-items/{w['id']}/", data={"title": "X"},
                       content_type="application/json", **_headers(principal=OWNER))
    assert patch.status_code == 403
    delete = http.delete(f"/api/v1/work-items/{w['id']}/", **_headers(principal=OWNER))
    assert delete.status_code == 403


@pytest.mark.django_db
def test_work_item_delete_is_blocked():
    http = HttpClient()
    w = _make_work(http)
    resp = http.delete(f"/api/v1/work-items/{w['id']}/", **_headers(principal=OWNER))
    assert resp.status_code == 403


# ---- permission-field output ----
@pytest.mark.django_db
def test_permission_fields_owner_in_owner_state():
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    data = http.get(f"/api/v1/work-items/{w['id']}/", **_headers(principal=OWNER)).json()
    assert data["can_edit"] is True
    assert data["can_submit_for_review"] is True
    assert data["can_review"] is False
    assert data["is_locked"] is False
    assert data["current_controller"] == "OWNER"


@pytest.mark.django_db
def test_permission_fields_owner_in_ready_is_locked():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    data = http.get(f"/api/v1/work-items/{w['id']}/", **_headers(principal=OWNER)).json()
    assert data["can_edit"] is False
    assert data["can_review"] is False
    assert data["is_locked"] is True
    assert data["current_controller"] == "REVIEWER"


@pytest.mark.django_db
def test_permission_fields_reviewer_in_ready():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    data = http.get(f"/api/v1/work-items/{w['id']}/", **_headers(principal=REVIEWER)).json()
    assert data["can_review"] is True
    assert data["can_edit"] is False
    assert data["is_locked"] is False


@pytest.mark.django_db
def test_permission_fields_terminal_read_only():
    http = HttpClient()
    w = _make_work(http)
    _to_ready(http, w)
    http.post(f"/api/v1/work-items/{w['id']}/approve/", data={},
              content_type="application/json", **_headers(principal=REVIEWER))
    data = http.get(f"/api/v1/work-items/{w['id']}/", **_headers(principal=OWNER)).json()
    assert data["can_edit"] is False
    assert data["is_locked"] is True
    assert data["current_controller"] == "NONE"


# ======================================================================
# V2 corrective coverage: dual owner representation + standalone docs
# ======================================================================

def _make_work_raw_principal_owner(http):
    """WorkItem whose owner_user_id is the raw acting principal (legacy rep)."""
    reviewer_emp = _employee(REVIEWER, "ReviewerRaw")
    client = http.post(
        "/api/v1/clients/",
        data={"legal_name": "Raw Client", "client_type": "OTHER", "pan": "RAWPAN123Z"},
        content_type="application/json", **_headers(),
    ).json()
    payload = {
        "title": "Raw-owner Work", "client_id": client["id"],
        "owner_user_id": OWNER, "reviewer_user_id": str(reviewer_emp.id),
        "priority": "NORMAL",
    }
    resp = http.post("/api/v1/work-items/", data=payload, content_type="application/json", **_headers())
    assert resp.status_code == 201, resp.content
    return resp.json()


@pytest.mark.django_db
def test_legacy_raw_principal_owner_can_transition():
    http = HttpClient()
    w = _make_work_raw_principal_owner(http)
    resp = _set(http, w["id"], "IN_PROGRESS", principal=OWNER)
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.django_db
def test_legacy_raw_principal_owner_blocks_other_principal():
    http = HttpClient()
    w = _make_work_raw_principal_owner(http)
    resp = _set(http, w["id"], "IN_PROGRESS", principal=OTHER)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_canonical_employee_owner_can_transition():
    http = HttpClient()
    w = _make_work(http)  # owner is Employee.id linked to OWNER
    resp = _set(http, w["id"], "IN_PROGRESS", principal=OWNER)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_unresolved_owner_does_not_grant_open_access():
    http = HttpClient()
    # owner_user_id is a random UUID belonging to no one; no actor should own it.
    reviewer_emp = _employee(REVIEWER, "RevX")
    client = http.post(
        "/api/v1/clients/",
        data={"legal_name": "Orphan", "client_type": "OTHER", "pan": "ORPHAN123Z"},
        content_type="application/json", **_headers(),
    ).json()
    import uuid as _uuid
    w = http.post("/api/v1/work-items/", data={
        "title": "Orphan Work", "client_id": client["id"],
        "owner_user_id": str(_uuid.uuid4()), "reviewer_user_id": str(reviewer_emp.id),
        "priority": "NORMAL",
    }, content_type="application/json", **_headers()).json()
    assert _set(http, w["id"], "IN_PROGRESS", principal=OWNER).status_code == 403
    assert _set(http, w["id"], "IN_PROGRESS", principal=OTHER).status_code == 403


@pytest.mark.django_db
def test_invalid_transition_returns_400_not_403():
    http = HttpClient()
    w = _make_work_raw_principal_owner(http)
    # NOT_STARTED -> READY_FOR_REVIEW is structurally invalid -> must be 400
    resp = _set(http, w["id"], "READY_FOR_REVIEW", principal=OWNER)
    assert resp.status_code == 400, resp.content


@pytest.mark.django_db
def test_standalone_document_request_still_supported():
    http = HttpClient()
    from contexts.clients.models import ClientContact

    client = http.post(
        "/api/v1/clients/",
        data={"legal_name": "SA Client", "client_type": "OTHER", "pan": "STAND123ZZ"},
        content_type="application/json", **_headers(),
    ).json()
    contact = ClientContact.objects.create(
        tenant_id=TENANT_A, created_by=OWNER, updated_by=OWNER, client_id=client["id"],
        name="POC", email="poc@example.com", is_active=True, can_receive_document_requests=True,
    )
    resp = http.post("/api/v1/document-requests/", data={
        "name": "Standalone Doc", "client_id": client["id"],
        "requested_from_contact_id": str(contact.id),
    }, content_type="application/json", **_headers())
    assert resp.status_code == 201, resp.content
    assert not resp.json().get("work_item_id")


@pytest.mark.django_db
def test_linked_document_request_requires_owner():
    http = HttpClient()
    from contexts.clients.models import ClientContact

    w = _make_work_raw_principal_owner(http)
    contact = ClientContact.objects.create(
        tenant_id=TENANT_A, created_by=OWNER, updated_by=OWNER, client_id=w["client_id"],
        name="POC2", email="poc2@example.com", is_active=True, can_receive_document_requests=True,
    )
    body = {
        "name": "Linked Doc", "client_id": w["client_id"], "work_item_id": w["id"],
        "requested_from_contact_id": str(contact.id),
    }
    # owner OK
    ok = http.post("/api/v1/document-requests/", data=body, content_type="application/json", **_headers(principal=OWNER))
    assert ok.status_code == 201, ok.content
    # non-owner blocked
    bad = http.post("/api/v1/document-requests/", data=body, content_type="application/json", **_headers(principal=OTHER))
    assert bad.status_code == 403


@pytest.mark.django_db
def test_invalid_work_item_id_does_not_fall_back_to_standalone():
    http = HttpClient()
    from contexts.clients.models import ClientContact
    import uuid as _uuid

    client = http.post(
        "/api/v1/clients/",
        data={"legal_name": "IW Client", "client_type": "OTHER", "pan": "INVWI1234Z"},
        content_type="application/json", **_headers(),
    ).json()
    contact = ClientContact.objects.create(
        tenant_id=TENANT_A, created_by=OWNER, updated_by=OWNER, client_id=client["id"],
        name="POC3", email="poc3@example.com", is_active=True, can_receive_document_requests=True,
    )
    resp = http.post("/api/v1/document-requests/", data={
        "name": "Bad Link", "client_id": client["id"], "work_item_id": str(_uuid.uuid4()),
        "requested_from_contact_id": str(contact.id),
    }, content_type="application/json", **_headers())
    assert resp.status_code == 403, resp.content


@pytest.mark.django_db
def test_generic_attachment_mutation_blocked():
    http = HttpClient()
    # generic create/update on attachments must be blocked (403), not allowed
    import uuid as _uuid
    resp = http.post("/api/v1/document-attachments/", data={"original_name": "x"},
                     content_type="application/json", **_headers())
    assert resp.status_code in (403, 405)
    patch = http.patch(f"/api/v1/document-attachments/{_uuid.uuid4()}/", data={"original_name": "y"},
                       content_type="application/json", **_headers())
    assert patch.status_code in (403, 404, 405)


@pytest.mark.django_db
def test_history_created_after_valid_transition():
    http = HttpClient()
    w = _make_work_raw_principal_owner(http)
    _set(http, w["id"], "IN_PROGRESS", principal=OWNER)
    hist = http.get(f"/api/v1/work-items/{w['id']}/history/", **_headers(principal=OWNER)).json()
    assert len(hist) >= 1
