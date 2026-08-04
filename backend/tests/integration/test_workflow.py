from __future__ import annotations

import io
import uuid

import pytest
from django.test import Client as HttpClient
from django.utils import timezone

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"
REVIEWER = "44444444-4444-4444-4444-444444444444"
OWNER = "22222222-2222-2222-2222-222222222222"


def _headers(tenant=TENANT_A, principal=OWNER):
    return {"HTTP_X_TENANT_ID": tenant, "HTTP_X_PRINCIPAL_ID": principal}


def _make_work(http, *, reviewer=REVIEWER, owner=OWNER, status=None):
    from contexts.identity.models import Employee

    reviewer_employee = Employee.objects.create(
        tenant_id=TENANT_A, created_by=OWNER, updated_by=OWNER,
        name="Reviewer", email=f"reviewer-{reviewer}@example.com",
        principal_id=reviewer,
    )
    client_resp = http.post(
        "/api/v1/clients/",
        data={"legal_name": "WF Client", "client_type": "PRIVATE_LIMITED", "pan": "ABCDE1234F"},
        content_type="application/json",
        **_headers(),
    )
    assert client_resp.status_code == 201, client_resp.content
    client_id = client_resp.json()["id"]
    payload = {
        "title": "GST Return",
        "client_id": client_id,
        "owner_user_id": owner,
        "reviewer_user_id": str(reviewer_employee.id),
        "priority": "NORMAL",
    }
    resp = http.post("/api/v1/work-items/", data=payload, content_type="application/json", **_headers())
    assert resp.status_code == 201, resp.content
    return resp.json()




def _make_eligible_contact(*, client_id, tenant=TENANT_A, principal=OWNER, name="Client POC"):
    from contexts.clients.models import ClientContact

    return ClientContact.objects.create(
        tenant_id=tenant,
        created_by=principal,
        updated_by=principal,
        client_id=client_id,
        name=name,
        email=f"poc-{client_id}@example.com",
        is_active=True,
        can_receive_document_requests=True,
    )

def _set(http, wid, status, comment="", principal=OWNER):
    body = {"status": status}
    if comment:
        body["comment"] = comment
    return http.post(
        f"/api/v1/work-items/{wid}/set_status/",
        data=body,
        content_type="application/json",
        **_headers(principal=principal),
    )


@pytest.mark.django_db
def test_start_work_accepts_in_progress():
    http = HttpClient()
    w = _make_work(http)
    resp = _set(http, w["id"], "IN_PROGRESS")
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.django_db
def test_invalid_transition_rejected():
    http = HttpClient()
    w = _make_work(http)
    # NOT_STARTED -> READY_FOR_REVIEW is invalid
    resp = _set(http, w["id"], "READY_FOR_REVIEW")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_generic_endpoint_cannot_complete_review_work():
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    resp = _set(http, w["id"], "COMPLETED")
    assert resp.status_code == 400, "generic set_status must not complete review work"


@pytest.mark.django_db
def test_no_direct_completion():
    http = HttpClient()
    for start in ("NOT_STARTED",):
        w = _make_work(http)
        resp = _set(http, w["id"], "COMPLETED")
        assert resp.status_code == 400


@pytest.mark.django_db
def test_assigned_reviewer_can_approve():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    resp = http.post(
        f"/api/v1/work-items/{w['id']}/approve/",
        data={}, content_type="application/json", **_headers(principal=REVIEWER),
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["completed_at"] is not None


@pytest.mark.django_db
def test_non_reviewer_cannot_approve():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    resp = http.post(
        f"/api/v1/work-items/{w['id']}/approve/",
        data={}, content_type="application/json", **_headers(principal=OWNER),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_rework_requires_comment():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    no_comment = http.post(
        f"/api/v1/work-items/{w['id']}/return_for_rework/",
        data={}, content_type="application/json", **_headers(principal=REVIEWER),
    )
    assert no_comment.status_code == 400
    ok = http.post(
        f"/api/v1/work-items/{w['id']}/return_for_rework/",
        data={"comment": "Fix totals"}, content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "REWORK_REQUIRED"


@pytest.mark.django_db
def test_rework_returns_to_preparation():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    http.post(
        f"/api/v1/work-items/{w['id']}/return_for_rework/",
        data={"comment": "redo"}, content_type="application/json", **_headers(principal=REVIEWER),
    )
    resp = _set(http, w["id"], "IN_PROGRESS")
    assert resp.status_code == 200
    assert resp.json()["status"] == "IN_PROGRESS"


@pytest.mark.django_db
def test_mandatory_docs_block_completion():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    contact = _make_eligible_contact(client_id=w["client_id"])
    create = http.post(
        "/api/v1/document-requests/",
        data={
            "name": "Bank statement",
            "client_id": w["client_id"],
            "work_item_id": w["id"],
            "mandatory": True,
            "requested_from_contact_id": str(contact.id),
        },
        content_type="application/json", **_headers(),
    )
    assert create.status_code == 201, create.content
    assert create.json()["tenant_id"] == TENANT_A
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    resp = http.post(
        f"/api/v1/work-items/{w['id']}/approve/",
        data={}, content_type="application/json", **_headers(principal=REVIEWER),
    )
    assert resp.status_code == 400

    doc_id = create.json()["id"]
    uploaded = _upload(http, doc_id, "bank-statement.pdf", content=b"%PDF-1.4", ctype="application/pdf")
    assert uploaded.status_code == 201, uploaded.content
    verified = http.post(
        f"/api/v1/document-requests/{doc_id}/verify/",
        data={"status": "ACCEPTED"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert verified.status_code == 200, verified.content
    approved = http.post(
        f"/api/v1/work-items/{w['id']}/approve/",
        data={}, content_type="application/json", **_headers(principal=REVIEWER),
    )
    assert approved.status_code == 200, approved.content


@pytest.mark.django_db
def test_first_attachment_sets_received_date_and_derived_status():
    http = HttpClient()
    w = _make_work(http)
    contact = _make_eligible_contact(client_id=w["client_id"])
    create = http.post(
        "/api/v1/document-requests/",
        data={
            "name": "PAN",
            "client_id": w["client_id"],
            "work_item_id": w["id"],
            "requested_from_contact_id": str(contact.id),
        },
        content_type="application/json", **_headers(),
    )
    assert create.status_code == 201, create.content
    doc = create.json()
    uploaded = _upload(http, doc["id"], "pan.pdf", content=b"%PDF-1.4", ctype="application/pdf")
    assert uploaded.status_code == 201, uploaded.content
    refreshed = http.get(
        f"/api/v1/document-requests/{doc['id']}/",
        **_headers(),
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["received_date"] is not None
    assert refreshed.json()["status"] == "PARTIALLY_RECEIVED"


@pytest.mark.django_db
def test_datetime_values_are_timezone_aware():
    from contexts.work.models import WorkItem

    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    item = WorkItem.objects.get(id=w["id"])
    assert item.submitted_for_review_at is not None
    assert timezone.is_aware(item.submitted_for_review_at)


def _upload(http, doc_id, filename, content=b"hello", ctype="text/plain", tenant=TENANT_A):
    fh = io.BytesIO(content)
    fh.name = filename
    return http.post(
        f"/api/v1/document-requests/{doc_id}/upload/",
        data={"file": fh},
        **_headers(tenant=tenant),
    )


def _make_doc(http, tenant=TENANT_A):
    c = http.post(
        "/api/v1/clients/",
        data={"legal_name": "DocClient", "client_type": "OTHER", "pan": "FGHIJ5678K"},
        content_type="application/json", **_headers(tenant=tenant),
    ).json()
    contact = _make_eligible_contact(client_id=c["id"], tenant=tenant)
    response = http.post(
        "/api/v1/document-requests/",
        data={
            "name": "Doc",
            "client_id": c["id"],
            "requested_from_contact_id": str(contact.id),
        },
        content_type="application/json", **_headers(tenant=tenant),
    )
    assert response.status_code == 201, response.content
    return response.json()


@pytest.mark.django_db
def test_blocked_extension_rejected():
    http = HttpClient()
    doc = _make_doc(http)
    resp = _upload(http, doc["id"], "evil.exe", ctype="application/octet-stream")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_oversized_attachment_rejected():
    http = HttpClient()
    doc = _make_doc(http)
    big = b"x" * (15 * 1024 * 1024 + 10)
    resp = _upload(http, doc["id"], "big.pdf", content=big, ctype="application/pdf")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_tenant_b_cannot_read_tenant_a_attachment():
    http = HttpClient()
    doc = _make_doc(http, tenant=TENANT_A)
    up = _upload(http, doc["id"], "ok.pdf", content=b"%PDF-1.4", ctype="application/pdf", tenant=TENANT_A)
    assert up.status_code == 201, up.content
    payload = up.json()
    assert isinstance(payload, list), payload
    assert len(payload) == 1, payload
    att_id = payload[0]["id"]
    resp = http.get(
        f"/api/v1/document-attachments/{att_id}/download/",
        **_headers(tenant=TENANT_B),
    )
    assert resp.status_code in (403, 404)


@pytest.mark.django_db
def test_non_reviewer_cannot_bypass_rework_with_generic_status():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    resp = _set(http, w["id"], "REWORK_REQUIRED", comment="bypass", principal=OWNER)
    assert resp.status_code == 400


@pytest.mark.django_db
def test_rework_cannot_resubmit_without_returning_to_progress():
    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    _set(http, w["id"], "IN_PROGRESS")
    _set(http, w["id"], "READY_FOR_REVIEW")
    returned = http.post(
        f"/api/v1/work-items/{w['id']}/return_for_rework/",
        data={"comment": "redo"}, content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert returned.status_code == 200
    resp = http.post(
        f"/api/v1/work-items/{w['id']}/submit_for_review/",
        data={}, content_type="application/json", **_headers(),
    )
    assert resp.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_work_notes_are_read_only(method):
    http = HttpClient()
    w = _make_work(http)
    _set(http, w["id"], "IN_PROGRESS")
    history = http.get(f"/api/v1/work-items/{w['id']}/history/", **_headers()).json()
    assert history
    note_id = history[0]["id"]
    url = "/api/v1/work-notes/" if method == "post" else f"/api/v1/work-notes/{note_id}/"
    call = getattr(http, method)
    resp = call(url, data={"entry": "tamper"}, content_type="application/json", **_headers())
    assert resp.status_code == 405


@pytest.mark.django_db
def test_mandatory_document_must_be_accepted_or_waived():
    from django.core.files.base import ContentFile
    from contexts.clients.models import ClientContact
    from contexts.work.models import (
        AttachmentReviewStatus,
        DocumentAttachment,
        DocumentRequest,
        DocumentRequestStatus,
        recalculate_document_request_status,
    )
    from contexts.work.views import WorkItemViewSet

    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    contact = ClientContact.objects.create(
        tenant_id=TENANT_A,
        created_by=OWNER,
        updated_by=OWNER,
        client_id=w["client_id"],
        name="Client POC",
        email="poc@example.com",
        can_receive_document_requests=True,
    )
    doc = DocumentRequest.objects.create(
        tenant_id=TENANT_A,
        created_by=OWNER,
        updated_by=OWNER,
        client_id=w["client_id"],
        work_item_id=w["id"],
        name="Mandatory",
        mandatory=True,
        requested_from_contact_id=contact.id,
        status=DocumentRequestStatus.REQUESTED,
    )
    item = type("I", (), {"tenant_id": TENANT_A, "id": w["id"]})()
    assert WorkItemViewSet()._unresolved_mandatory_docs(item) == 1

    DocumentAttachment.objects.create(
        tenant_id=TENANT_A,
        created_by=OWNER,
        updated_by=OWNER,
        document_request_id=doc.id,
        work_item_id=w["id"],
        uploaded_by=OWNER,
        original_name="accepted.pdf",
        content_type="application/pdf",
        size_bytes=8,
        file=ContentFile(b"%PDF-1.4", name="accepted.pdf"),
        review_status=AttachmentReviewStatus.ACCEPTED,
        reviewed_by=REVIEWER,
    )
    recalculate_document_request_status(doc, updated_by=REVIEWER)
    doc.refresh_from_db()

    assert doc.status == DocumentRequestStatus.ACCEPTED
    assert WorkItemViewSet()._unresolved_mandatory_docs(item) == 0

@pytest.mark.django_db
def test_document_request_requires_eligible_client_contact():
    http = HttpClient()
    w = _make_work(http)
    response = http.post("/api/v1/document-requests/", data={"name":"Bank statement","client_id":w["client_id"],"work_item_id":w["id"],"mandatory":True}, content_type="application/json", **_headers())
    assert response.status_code in (400, 403)


@pytest.mark.django_db
def test_document_attachment_review_fields_default_without_changing_upload_contract():
    from contexts.work.models import AttachmentReviewStatus, DocumentAttachment

    http = HttpClient()
    doc = _make_doc(http)
    response = _upload(http, doc["id"], "review-default.pdf", content=b"%PDF-1.4")

    assert response.status_code == 201, response.content
    payload = response.json()
    assert payload[0]["review_status"] == AttachmentReviewStatus.PENDING_REVIEW
    assert payload[0]["reviewed_at"] is None
    assert payload[0]["reviewed_by"] is None
    assert payload[0]["review_comment"] == ""
    attachment = DocumentAttachment.objects.get(id=payload[0]["id"])
    assert attachment.review_status == AttachmentReviewStatus.PENDING_REVIEW
    assert attachment.reviewed_at is None
    assert attachment.reviewed_by is None
    assert attachment.review_comment == ""


@pytest.mark.django_db
def test_document_attachment_review_status_contract_supports_all_frozen_states():
    from contexts.work.models import AttachmentReviewStatus, DocumentAttachment

    http = HttpClient()
    doc = _make_doc(http)
    response = _upload(http, doc["id"], "review-states.pdf", content=b"%PDF-1.4")
    assert response.status_code == 201, response.content
    attachment = DocumentAttachment.objects.get(id=response.json()[0]["id"])

    expected = {"PENDING_REVIEW", "ACCEPTED", "REJECTED", "SUPERSEDED"}
    assert set(AttachmentReviewStatus.values) == expected
    for state in AttachmentReviewStatus.values:
        attachment.review_status = state
        attachment.save(update_fields=["review_status"])
        attachment.refresh_from_db()
        assert attachment.review_status == state

@pytest.mark.django_db
def test_request_verify_accepts_newest_pending_attachment_and_derives_request_status():
    from contexts.work.models import AttachmentReviewStatus, DocumentAttachment

    http = HttpClient()
    doc = _make_doc(http)
    first = _upload(http, doc["id"], "first.pdf", content=b"%PDF-1.4 first-version", ctype="application/pdf")
    second = _upload(http, doc["id"], "second.pdf", content=b"%PDF-1.4 second-version", ctype="application/pdf")
    assert first.status_code == 201
    assert second.status_code == 201

    response = http.post(
        f"/api/v1/document-requests/{doc['id']}/verify/",
        data={"status": "ACCEPTED"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "ACCEPTED"

    newest = DocumentAttachment.objects.get(id=second.json()[0]["id"])
    older = DocumentAttachment.objects.get(id=first.json()[0]["id"])
    assert newest.review_status == AttachmentReviewStatus.ACCEPTED
    assert newest.reviewed_by == uuid.UUID(REVIEWER)
    assert newest.reviewed_at is not None
    assert older.review_status == AttachmentReviewStatus.PENDING_REVIEW


@pytest.mark.django_db
def test_request_verify_rejects_without_pending_attachment():
    http = HttpClient()
    doc = _make_doc(http)
    response = http.post(
        f"/api/v1/document-requests/{doc['id']}/verify/",
        data={"status": "ACCEPTED"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "No pending attachment is available for review."


@pytest.mark.django_db
def test_rejected_only_attachments_derive_received_and_do_not_complete_mandatory_request():
    from contexts.work.models import DocumentRequest

    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    contact = _make_eligible_contact(client_id=w["client_id"])
    create = http.post(
        "/api/v1/document-requests/",
        data={
            "name": "Rejected mandatory",
            "client_id": w["client_id"],
            "work_item_id": w["id"],
            "mandatory": True,
            "requested_from_contact_id": str(contact.id),
        },
        content_type="application/json",
        **_headers(),
    )
    doc_id = create.json()["id"]
    uploaded = _upload(http, doc_id, "bad.pdf", content=b"%PDF-1.4", ctype="application/pdf")
    assert uploaded.status_code == 201

    rejected = http.post(
        f"/api/v1/document-requests/{doc_id}/verify/",
        data={"status": "REJECTED", "comment": "Unreadable"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert rejected.status_code == 200, rejected.content
    assert rejected.json()["status"] == "RECEIVED"

    doc = DocumentRequest.objects.get(id=doc_id)
    from contexts.work.views import WorkItemViewSet
    item = type("I", (), {"tenant_id": TENANT_A, "id": w["id"]})()
    assert WorkItemViewSet()._unresolved_mandatory_docs(item) == 1
    assert doc.verification_comment == ""


@pytest.mark.django_db
def test_attachment_review_endpoint_updates_attachment_and_request():
    from contexts.work.models import AttachmentReviewStatus, DocumentAttachment

    http = HttpClient()
    doc = _make_doc(http)
    uploaded = _upload(http, doc["id"], "direct-review.pdf", content=b"%PDF-1.4", ctype="application/pdf")
    attachment_id = uploaded.json()[0]["id"]

    response = http.post(
        f"/api/v1/document-attachments/{attachment_id}/review/",
        data={"status": "ACCEPTED"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert response.status_code == 200, response.content
    assert response.json()["review_status"] == AttachmentReviewStatus.ACCEPTED
    assert response.json()["reviewed_at"] is not None

    attachment = DocumentAttachment.objects.get(id=attachment_id)
    assert attachment.reviewed_by == uuid.UUID(REVIEWER)

    request_response = http.get(
        f"/api/v1/document-requests/{doc['id']}/",
        **_headers(),
    )
    assert request_response.status_code == 200
    assert request_response.json()["status"] == "ACCEPTED"


@pytest.mark.django_db
def test_waiver_remains_request_level_and_completes_mandatory_request_without_attachment():
    from contexts.work.models import DocumentRequest
    from contexts.work.views import WorkItemViewSet

    http = HttpClient()
    w = _make_work(http, reviewer=REVIEWER)
    contact = _make_eligible_contact(client_id=w["client_id"])
    create = http.post(
        "/api/v1/document-requests/",
        data={
            "name": "Waivable",
            "client_id": w["client_id"],
            "work_item_id": w["id"],
            "mandatory": True,
            "requested_from_contact_id": str(contact.id),
        },
        content_type="application/json",
        **_headers(),
    )
    doc_id = create.json()["id"]
    waived = http.post(
        f"/api/v1/document-requests/{doc_id}/verify/",
        data={"status": "WAIVED", "comment": "Not applicable for this engagement"},
        content_type="application/json",
        **_headers(principal=REVIEWER),
    )
    assert waived.status_code == 200, waived.content
    assert waived.json()["status"] == "WAIVED"

    doc = DocumentRequest.objects.get(id=doc_id)
    assert doc.verification_comment == "Not applicable for this engagement"
    item = type("I", (), {"tenant_id": TENANT_A, "id": w["id"]})()
    assert WorkItemViewSet()._unresolved_mandatory_docs(item) == 0
