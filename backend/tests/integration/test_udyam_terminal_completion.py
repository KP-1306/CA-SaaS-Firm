"""Requirement 1 data-level regression: completed Udyam backend truth.

Proves the authoritative backend signals the frontend terminal projection
depends on are correct after registration completion.
"""
from __future__ import annotations

import io
import pytest
from django.test import Client as HttpClient

from tests.integration.test_udyam_v2_regression import (
    TENANT, _all_steps, _h, _patch_deps, _seed_process,
    _submit, _udyam_service, _work,
)


def _complete(http, item):
    cert = io.BytesIO(b"%PDF-1.4 regression certificate")
    cert.name = "cert.pdf"
    return http.post(
        f"/api/v1/work-items/{item.id}/udyam-complete-registration/",
        data={"certificate": cert, "remarks": "Done."},
        **_h(),
    )


@pytest.mark.django_db
def test_completed_udyam_process_position_is_completion(monkeypatch):
    """Durable process position is COMPLETION after registration completes."""
    from contexts.work.models import WorkProcessState
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()
    _submit(http, item)
    assert _complete(http, item).status_code == 200
    item.refresh_from_db()
    assert item.status == "COMPLETED"
    assert item.completed_at is not None
    state = WorkProcessState.objects.get(tenant_id=TENANT, work_item_id=item.id)
    assert state.current_step_id == steps["completion"].id
    resp = http.get(f"/api/v1/work-items/{item.id}/process-step/", **_h())
    assert resp.status_code == 200
    assert resp.json().get("current_step", {}).get("code") == "COMPLETION"


@pytest.mark.django_db
def test_completed_udyam_health_exposes_no_earlier_stage_action(monkeypatch):
    """Health must not advertise a pre-completion Udyam next action once done."""
    _patch_deps(monkeypatch)
    service = _udyam_service()
    steps = _all_steps(service)
    item = _work(service)
    _seed_process(item, steps["submit"])
    http = HttpClient()
    _submit(http, item)
    assert _complete(http, item).status_code == 200
    resp = http.get(f"/api/v1/work-items/{item.id}/health/", **_h())
    assert resp.status_code == 200
    code = str((resp.json().get("next_action") or {}).get("code", ""))
    assert code not in {"SUBMIT_UDYAM_APPLICATION", "AWAIT_UDYAM_OUTCOME", "RESOLVE_UDYAM_QUERY"}, \
        f"completed item advertised earlier-stage action: {code}"
