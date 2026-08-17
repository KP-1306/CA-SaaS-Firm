from __future__ import annotations

import uuid

import pytest
from django.test import Client as HttpClient


TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "33333333-3333-3333-3333-333333333333"

PARTNER = "22222222-2222-2222-2222-222222222222"
STAFF_A = "44444444-4444-4444-4444-444444444444"
STAFF_B = "55555555-5555-5555-5555-555555555555"


def _h(
    tenant=TENANT_A,
    principal=PARTNER,
):
    return {
        "HTTP_X_TENANT_ID": tenant,
        "HTTP_X_PRINCIPAL_ID": principal,
    }


def _employee(
    principal,
    name,
    role="STAFF",
    tenant=TENANT_A,
):
    from contexts.identity.models import Employee

    return Employee.objects.create(
        tenant_id=tenant,
        created_by=principal,
        updated_by=principal,
        name=name,
        email=f"{name}-{principal}@ex.com",
        role=role,
        principal_id=principal,
        is_active=True,
    )


def _step(
    *,
    tenant_id,
    service_id,
    code,
    order,
    active=True,
):
    from contexts.configuration.models import ServiceProcessStep

    return ServiceProcessStep.objects.create(
        tenant_id=tenant_id,
        created_by=PARTNER,
        updated_by=PARTNER,
        service_id=service_id,
        code=code,
        name=code.replace("_", " ").title(),
        description="U3-C3 runtime regression definition.",
        display_order=order,
        is_active=active,
    )


def _work(
    *,
    service_id=None,
    status="NOT_STARTED",
    tenant_id=TENANT_A,
    owner_principal=STAFF_A,
):
    from contexts.work.models import WorkItem

    owner = _employee(
        owner_principal,
        f"Owner-{owner_principal}",
        tenant=tenant_id,
    )

    return WorkItem.objects.create(
        tenant_id=tenant_id,
        created_by=PARTNER,
        updated_by=PARTNER,
        title="U3 Process Runtime Work",
        client_id=uuid.uuid4(),
        service_id=service_id,
        owner_user_id=owner.id,
        priority="NORMAL",
        status=status,
    )


def _post_step(
    work_id,
    step_id=None,
    *,
    principal=STAFF_A,
    tenant=TENANT_A,
    note=None,
):
    body = {}

    if step_id is not None:
        body["step_id"] = str(step_id)

    if note is not None:
        body["note"] = note

    return HttpClient().post(
        f"/api/v1/work-items/{work_id}/process-step/",
        data=body,
        content_type="application/json",
        **_h(
            tenant=tenant,
            principal=principal,
        ),
    )


@pytest.mark.django_db
def test_owner_can_create_first_process_state():
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="CLIENT_INFORMATION",
        order=10,
    )

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        step.id,
        note="Client information received.",
    )

    assert response.status_code == 200, response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    assert state.current_step_id == step.id
    assert str(state.entered_by) == STAFF_A
    assert state.note == "Client information received."
    assert state.entered_at is not None

    payload = response.json()

    assert payload["work_item_id"] == str(work.id)
    assert payload["current_step"]["id"] == str(step.id)
    assert payload["current_step"]["code"] == "CLIENT_INFORMATION"
    assert payload["current_step"]["display_order"] == 10
    assert payload["entered_by"] == STAFF_A
    assert payload["note"] == "Client information received."


@pytest.mark.django_db
def test_second_transition_updates_same_runtime_state():
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    first = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="CLIENT_INFORMATION",
        order=10,
    )

    second = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="VERIFICATION_PREPARATION",
        order=20,
    )

    work = _work(
        service_id=service_id,
    )

    first_response = _post_step(
        work.id,
        first.id,
        note="Initial stage.",
    )

    assert first_response.status_code == 200, first_response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    state_id = state.id
    first_entered_at = state.entered_at

    second_response = _post_step(
        work.id,
        second.id,
        note="Verification started.",
    )

    assert second_response.status_code == 200, second_response.content

    state.refresh_from_db()

    assert state.id == state_id
    assert state.current_step_id == second.id
    assert str(state.entered_by) == STAFF_A
    assert state.note == "Verification started."
    assert state.entered_at >= first_entered_at

    assert (
        WorkProcessState.objects.filter(
            tenant_id=TENANT_A,
            work_item_id=work.id,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_process_stage_does_not_change_work_status():
    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="INTERNAL_REVIEW",
        order=30,
    )

    work = _work(
        service_id=service_id,
        status="IN_PROGRESS",
    )

    response = _post_step(
        work.id,
        step.id,
    )

    assert response.status_code == 200, response.content

    work.refresh_from_db()

    assert work.status == "IN_PROGRESS"
    assert work.submitted_for_review_at is None
    assert work.completed_at is None


@pytest.mark.django_db
def test_cross_service_step_is_rejected_and_state_preserved():
    from contexts.work.models import WorkProcessState

    service_a = uuid.uuid4()
    service_b = uuid.uuid4()

    valid = _step(
        tenant_id=TENANT_A,
        service_id=service_a,
        code="VALID_STEP",
        order=10,
    )

    other_service = _step(
        tenant_id=TENANT_A,
        service_id=service_b,
        code="OTHER_SERVICE",
        order=10,
    )

    work = _work(
        service_id=service_a,
    )

    response = _post_step(
        work.id,
        valid.id,
    )

    assert response.status_code == 200, response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    response = _post_step(
        work.id,
        other_service.id,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_STEP_NOT_AVAILABLE"

    state.refresh_from_db()

    assert state.current_step_id == valid.id


@pytest.mark.django_db
def test_cross_tenant_step_is_rejected():
    service_id = uuid.uuid4()

    foreign_step = _step(
        tenant_id=TENANT_B,
        service_id=service_id,
        code="FOREIGN_TENANT",
        order=10,
    )

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        foreign_step.id,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_STEP_NOT_AVAILABLE"


@pytest.mark.django_db
def test_inactive_step_is_rejected():
    service_id = uuid.uuid4()

    inactive = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="INACTIVE",
        order=10,
        active=False,
    )

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        inactive.id,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_STEP_NOT_AVAILABLE"


@pytest.mark.django_db
def test_work_without_service_is_rejected():
    work = _work(
        service_id=None,
    )

    response = _post_step(
        work.id,
        uuid.uuid4(),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_SERVICE_REQUIRED"


@pytest.mark.django_db
def test_non_owner_is_rejected():
    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="OWNER_ONLY",
        order=10,
    )

    work = _work(
        service_id=service_id,
    )

    _employee(
        STAFF_B,
        "NonOwner",
    )

    response = _post_step(
        work.id,
        step.id,
        principal=STAFF_B,
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_missing_step_id_is_rejected():
    service_id = uuid.uuid4()

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        None,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_STEP_REQUIRED"


@pytest.mark.django_db
def test_invalid_step_uuid_is_rejected():
    service_id = uuid.uuid4()

    work = _work(
        service_id=service_id,
    )

    response = HttpClient().post(
        f"/api/v1/work-items/{work.id}/process-step/",
        data={
            "step_id": "not-a-uuid",
        },
        content_type="application/json",
        **_h(principal=STAFF_A),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PROCESS_STEP_INVALID"


@pytest.mark.django_db
def test_successful_transition_writes_audit_event():
    from contexts.audit.models import AuditEvent
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="CLIENT_INFORMATION",
        order=10,
    )

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        step.id,
        note="Audit this transition.",
    )

    assert response.status_code == 200, response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    event = AuditEvent.objects.get(
        tenant_id=TENANT_A,
        entity_type="WorkProcessState",
        entity_id=state.id,
    )

    assert event.action == "STATUS_CHANGE"

    assert event.previous_values["process_step_id"] == ""
    assert event.previous_values["process_step_code"] == ""

    assert event.new_values["process_step_id"] == str(step.id)
    assert event.new_values["process_step_code"] == "CLIENT_INFORMATION"


@pytest.mark.django_db
def test_audit_failure_rolls_back_initial_state(
    monkeypatch,
):
    from contexts.work import views as work_views
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="AUDIT_FAILURE_INITIAL",
        order=10,
    )

    work = _work(
        service_id=service_id,
    )

    def boom(**kwargs):
        raise RuntimeError("audit db down")

    monkeypatch.setattr(
        work_views,
        "record_event",
        boom,
    )

    response = _post_step(
        work.id,
        step.id,
    )

    assert response.status_code == 503

    assert not WorkProcessState.objects.filter(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    ).exists()


@pytest.mark.django_db
def test_audit_failure_rolls_back_existing_state_update(
    monkeypatch,
):
    from contexts.work import views as work_views
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    first = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="FIRST",
        order=10,
    )

    second = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="SECOND",
        order=20,
    )

    work = _work(
        service_id=service_id,
    )

    initial_response = _post_step(
        work.id,
        first.id,
        note="Stable state.",
    )

    assert initial_response.status_code == 200, initial_response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    original_entered_at = state.entered_at

    def boom(**kwargs):
        raise RuntimeError("audit db down")

    monkeypatch.setattr(
        work_views,
        "record_event",
        boom,
    )

    response = _post_step(
        work.id,
        second.id,
        note="Must roll back.",
    )

    assert response.status_code == 503

    state.refresh_from_db()

    assert state.current_step_id == first.id
    assert state.note == "Stable state."
    assert state.entered_at == original_entered_at


@pytest.mark.django_db
def test_entered_actor_note_and_timestamp_are_persisted():
    from contexts.work.models import WorkProcessState

    service_id = uuid.uuid4()

    step = _step(
        tenant_id=TENANT_A,
        service_id=service_id,
        code="APPLICATION_SUBMISSION",
        order=40,
    )

    work = _work(
        service_id=service_id,
    )

    response = _post_step(
        work.id,
        step.id,
        note="Ready for portal submission.",
    )

    assert response.status_code == 200, response.content

    state = WorkProcessState.objects.get(
        tenant_id=TENANT_A,
        work_item_id=work.id,
    )

    assert str(state.entered_by) == STAFF_A
    assert state.entered_at is not None
    assert state.note == "Ready for portal submission."
    assert str(state.updated_by) == STAFF_A
