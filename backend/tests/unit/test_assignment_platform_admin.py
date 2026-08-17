from types import SimpleNamespace

from contexts.assignment import views


def _principal():
    return SimpleNamespace(
        tenant_id="11111111-1111-1111-1111-111111111111",
        principal_id="22222222-2222-2222-2222-222222222222",
    )


def test_platform_admin_has_assignment_management_authority(
    monkeypatch,
):
    monkeypatch.setattr(
        views,
        "is_platform_admin",
        lambda tenant_id, caller: True,
    )
    monkeypatch.setattr(
        views,
        "is_executive",
        lambda tenant_id, caller: False,
    )
    monkeypatch.setattr(
        views,
        "caller_role",
        lambda tenant_id, caller: "STAFF",
    )

    assert views._is_manager(_principal()) is True


def test_regular_staff_without_management_authority_is_denied(
    monkeypatch,
):
    monkeypatch.setattr(
        views,
        "is_platform_admin",
        lambda tenant_id, caller: False,
    )
    monkeypatch.setattr(
        views,
        "is_executive",
        lambda tenant_id, caller: False,
    )
    monkeypatch.setattr(
        views,
        "caller_role",
        lambda tenant_id, caller: "STAFF",
    )

    assert views._is_manager(_principal()) is False
