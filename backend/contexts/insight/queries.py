"""Deterministic, tenant-scoped read-only aggregation for dashboards.

Insight owns operational intelligence (C14). It never defines Work models or
workflow logic; it queries existing tenant-scoped models and returns plain
dict aggregates. Every metric is current-state or period-based (labelled), uses
deterministic date boundaries, and is safe on empty datasets.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.utils import timezone

from contexts.clients.models import Client
from contexts.identity.models import Employee
from contexts.work.models import DocumentAttachment, DocumentRequest, WorkItem, WorkNote
from contexts.work.work_health import calculate_work_health

_OPEN_EXCLUDED = ("COMPLETED", "CANCELLED")
_AGE_BUCKETS = ((0, 7), (8, 30), (31, 90), (91, None))


def _today():
    return timezone.now().date()


def _period_bounds(period: str):
    """Return (start_date, end_date_inclusive) for a named period."""
    today = _today()
    if period == "today":
        return today, today
    if period == "week":
        return today - timedelta(days=6), today
    if period == "quarter":
        return today - timedelta(days=89), today
    # default: month (last 30 days inclusive)
    return today - timedelta(days=29), today


def _is_overdue(due_date, status) -> bool:
    if not due_date or status in _OPEN_EXCLUDED:
        return False
    return due_date < _today()


def _work_qs(tenant_id):
    return WorkItem.objects.filter(tenant_id=tenant_id)


def _employee_names(tenant_id):
    return {e.id: e.name for e in Employee.objects.filter(tenant_id=tenant_id)}


def _employee_identity_map(tenant_id):
    """Map each employee to the set of ids their work may be owned under.

    Returns {employee_id: (name, {employee_id, principal_id})} so aggregation
    attributes work stored under either representation to the right employee,
    without double counting (each WorkItem has one owner_user_id).
    """
    out = {}
    for e in Employee.objects.filter(tenant_id=tenant_id):
        ids = {e.id}
        if e.principal_id:
            ids.add(e.principal_id)
        out[e.id] = (e.name, ids)
    return out


def _client_names(tenant_id):
    return {c.id: (c.trade_name or c.legal_name) for c in Client.objects.filter(tenant_id=tenant_id)}


# ---------------------------------------------------------------- core counts
def _status_counts(items):
    counts = {}
    for w in items:
        counts[w.status] = counts.get(w.status, 0) + 1
    return counts


def _open_items(items):
    return [w for w in items if w.status not in _OPEN_EXCLUDED]


def _overdue_items(items):
    return [w for w in items if _is_overdue(w.due_date, w.status)]


def _age_days(reference_date):
    if not reference_date:
        return None
    return (_today() - reference_date).days


def _ageing_buckets(items):
    buckets = {"0-7": 0, "8-30": 0, "31-90": 0, "91+": 0}
    for w in _open_items(items):
        age = _age_days(w.created_at.date() if isinstance(w.created_at, datetime) else w.created_at)
        if age is None:
            continue
        if age <= 7:
            buckets["0-7"] += 1
        elif age <= 30:
            buckets["8-30"] += 1
        elif age <= 90:
            buckets["31-90"] += 1
        else:
            buckets["91+"] += 1
    return buckets


def _completed_in_period(items, start, end):
    out = []
    for w in items:
        if w.completed_at:
            d = w.completed_at.date() if isinstance(w.completed_at, datetime) else w.completed_at
            if start <= d <= end:
                out.append(w)
    return out


def _avg_completion_days(items, start, end):
    durations = []
    for w in _completed_in_period(items, start, end):
        created = w.created_at
        done = w.completed_at
        if created and done:
            durations.append((done - created).total_seconds() / 86400.0)
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


# ---------------------------------------------------------------- employee view
def employee_dashboard(tenant_id, identity_ids, period="month", employee_id=None):
    """Aggregate the caller's work.

    ``identity_ids`` is the set of canonical identity references the caller's
    work may be stored under (raw principal UUID and/or Employee.id). Using the
    set covers both ownership representations without missing or double-counting
    records (a WorkItem has exactly one owner_user_id, so ``__in`` cannot double
    count).
    """
    start, end = _period_bounds(period)
    id_list = list(identity_ids) if not isinstance(identity_ids, (list, tuple)) else identity_ids
    if not id_list and employee_id is not None:
        id_list = [employee_id]
    items = list(_work_qs(tenant_id).filter(owner_user_id__in=id_list))
    reviews = list(
        _work_qs(tenant_id).filter(reviewer_user_id__in=id_list, status="READY_FOR_REVIEW")
    )
    open_items = _open_items(items)
    today = _today()
    my_work = {
        "assigned_open": len(open_items),
        "due_today": len([w for w in open_items if w.due_date == today]),
        "overdue": len(_overdue_items(items)),
        "waiting_for_client": len([w for w in items if w.status == "WAITING_FOR_CLIENT"]),
        "ready_for_review": len([w for w in items if w.status == "READY_FOR_REVIEW"]),
        "rework_required": len([w for w in items if w.status == "REWORK_REQUIRED"]),
        "recently_completed": len(_completed_in_period(items, start, end)),
    }
    # document action centre (docs on this employee's work items)
    work_ids = {w.id for w in items}
    docs = [d for d in DocumentRequest.objects.filter(tenant_id=tenant_id) if d.work_item_id in work_ids]
    doc_ids = {d.id for d in docs}
    attachments = [
        a for a in DocumentAttachment.objects.filter(tenant_id=tenant_id)
        if a.document_request_id in doc_ids
    ]
    document_centre = {
        "awaiting_client": len([d for d in docs if d.status in ("REQUESTED", "PARTIALLY_RECEIVED")]),
        "uploads_awaiting_review": len([a for a in attachments if a.review_status == "PENDING_REVIEW"]),
        "rejected_attachments": len([a for a in attachments if a.review_status == "REJECTED"]),
    }
    workload = {
        "open_workload": len(open_items),
        "completed_in_period": len(_completed_in_period(items, start, end)),
        "status_distribution": _status_counts(items),
        "avg_completion_days": _avg_completion_days(items, start, end),
        "pending_reviews_assigned": len(reviews),
    }
    return {
        "period": period,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "my_work": my_work,
        "document_centre": document_centre,
        "workload": workload,
    }



def _executive_work_health(open_items):
    """Aggregate the certified Work Health engine for leadership.

    This function defines no new health rules. Every per-item decision is
    delegated to calculate_work_health(), then summarized for the executive
    dashboard.
    """
    snapshots = []

    for item in open_items:
        health = calculate_work_health(item)

        snapshots.append({
            "work_item": item,
            "health": health,
        })

    healthy = 0
    attention_required = 0
    high_risk = 0
    due_soon = 0
    overdue = 0
    waiting_on_client = 0
    waiting_on_reviewer = 0
    longest_waiting_days = 0

    actions = []

    for entry in snapshots:
        item = entry["work_item"]
        health = entry["health"]

        health_state = health.get("health")
        risk_state = health.get("risk")
        due_state = health.get("due_state")
        controller = health.get("current_controller")
        waiting_days = int(
            health.get("waiting_days") or 0
        )

        if health_state == "GREEN":
            healthy += 1
        elif health_state == "AMBER":
            attention_required += 1

        if (
            health_state == "RED"
            or risk_state == "HIGH"
        ):
            high_risk += 1

        if due_state == "DUE_SOON":
            due_soon += 1
        elif due_state == "OVERDUE":
            overdue += 1

        if controller == "CLIENT":
            waiting_on_client += 1
        elif controller == "REVIEWER":
            waiting_on_reviewer += 1

        longest_waiting_days = max(
            longest_waiting_days,
            waiting_days,
        )

        next_action = health.get("next_action") or {}

        if (
            health_state in ("AMBER", "RED")
            or risk_state == "HIGH"
            or due_state in ("DUE_SOON", "OVERDUE")
            or waiting_days > 0
        ):
            actions.append({
                "work_item_id": str(item.id),
                "title": item.title,
                "client_id": (
                    str(item.client_id)
                    if item.client_id
                    else None
                ),
                "status": item.status,
                "priority": item.priority,
                "health": health_state,
                "risk": risk_state,
                "due_state": due_state,
                "days_to_due": health.get("days_to_due"),
                "current_controller": controller,
                "waiting_days": waiting_days,
                "next_action_code": next_action.get("code"),
                "next_action": next_action.get("label"),
            })

    health_rank = {
        "RED": 3,
        "AMBER": 2,
        "GREEN": 1,
        None: 0,
    }

    risk_rank = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        None: 0,
    }

    due_rank = {
        "OVERDUE": 3,
        "DUE_SOON": 2,
        "ON_TRACK": 1,
        None: 0,
    }

    actions.sort(
        key=lambda row: (
            health_rank.get(row["health"], 0),
            risk_rank.get(row["risk"], 0),
            due_rank.get(row["due_state"], 0),
            row["waiting_days"],
        ),
        reverse=True,
    )

    return {
        "healthy": healthy,
        "attention_required": attention_required,
        "high_risk": high_risk,
        "due_soon": due_soon,
        "overdue": overdue,
        "waiting_on_client": waiting_on_client,
        "waiting_on_reviewer": waiting_on_reviewer,
        "longest_waiting_days": longest_waiting_days,
        "immediate_actions": actions[:10],
    }


# ---------------------------------------------------------------- executive view
def executive_dashboard(tenant_id, period="month"):
    start, end = _period_bounds(period)
    items = list(_work_qs(tenant_id))
    emp_names = _employee_names(tenant_id)
    client_names = _client_names(tenant_id)
    open_items = _open_items(items)
    today = _today()

    overview = {
        "active_clients": Client.objects.filter(tenant_id=tenant_id, engagement_status="ACTIVE").count(),
        "active_work": len(open_items),
        "due_today": len([w for w in open_items if w.due_date == today]),
        "overdue": len(_overdue_items(items)),
        "waiting_for_client": len([w for w in items if w.status == "WAITING_FOR_CLIENT"]),
        "ready_for_review": len([w for w in items if w.status == "READY_FOR_REVIEW"]),
        "rework_required": len([w for w in items if w.status == "REWORK_REQUIRED"]),
        "recently_completed": len(_completed_in_period(items, start, end)),
    }

    operations = {
        "by_status": _status_counts(items),
        "ageing_buckets": _ageing_buckets(items),
        "completed_in_period": len(_completed_in_period(items, start, end)),
        "avg_completion_days": _avg_completion_days(items, start, end),
    }

    # employee workload (attribute work under either ownership representation)
    identity_map = _employee_identity_map(tenant_id)
    workload_rows = []
    for emp_id, (name, id_set) in identity_map.items():
        owned = [w for w in items if w.owner_user_id in id_set]
        owned_open = _open_items(owned)
        if not owned_open and not owned:
            continue
        workload_rows.append({
            "employee_id": str(emp_id),
            "employee_name": name,
            "open_work": len(owned_open),
            "overdue": len(_overdue_items(owned)),
            "completed_in_period": len(_completed_in_period(owned, start, end)),
            "rework_count": len([w for w in owned if w.status == "REWORK_REQUIRED"]),
        })
    workload_rows.sort(key=lambda r: r["open_work"], reverse=True)
    unassigned = len([w for w in open_items if not w.owner_user_id])
    pending_reviews = len([w for w in items if w.status == "READY_FOR_REVIEW"])

    # client health
    client_rows = []
    for client_id, name in client_names.items():
        cwork = [w for w in items if w.client_id == client_id]
        c_open = _open_items(cwork)
        c_overdue = _overdue_items(cwork)
        cdocs = [d for d in DocumentRequest.objects.filter(tenant_id=tenant_id, client_id=client_id)]
        pending_docs = len([d for d in cdocs if d.status in ("REQUESTED", "PARTIALLY_RECEIVED")])
        if not c_open and not c_overdue and not pending_docs:
            continue
        client_rows.append({
            "client_id": str(client_id),
            "client_name": name,
            "open_work": len(c_open),
            "overdue_work": len(c_overdue),
            "pending_documents": pending_docs,
        })
    client_rows.sort(key=lambda r: (r["overdue_work"], r["open_work"]), reverse=True)

    # action centre
    action_centre = {
        "overdue": len(_overdue_items(items)),
        "unassigned": unassigned,
        "awaiting_reviewer": len([w for w in open_items if not w.reviewer_user_id]),
        "review_backlog": pending_reviews,
        "rework_required": len([w for w in items if w.status == "REWORK_REQUIRED"]),
        "long_waiting_documents": len([
            d for d in DocumentRequest.objects.filter(tenant_id=tenant_id)
            if d.status in ("REQUESTED", "PARTIALLY_RECEIVED")
        ]),
    }

    # heatmap: service/status is derivable; keep simple + real
    status_by_priority = {}
    for w in items:
        key = w.priority
        status_by_priority.setdefault(key, {})
        status_by_priority[key][w.status] = status_by_priority[key].get(w.status, 0) + 1

    return {
        "period": period,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "overview": overview,
        "operations": operations,
        "employee_workload": {"rows": workload_rows, "unassigned": unassigned, "pending_reviews": pending_reviews},
        "client_health": {"rows": client_rows},
        "heatmap_priority_status": status_by_priority,
        "action_centre": action_centre,
        "work_health": _executive_work_health(open_items),
    }


def servicing_summary(tenant_id):
    """Read-only, deterministic counts for the servicing layer (V1 additive).

    Every value is a current-state count over tenant-scoped rows and is safe on
    empty datasets. This adds NO workflow logic and reads only the generation
    context models. Imported lazily so insight retains no import-time dependency
    on the generation context.
    """
    from contexts.generation.models import (
        ClientServiceSubscription,
        GeneratedWorkLedger,
        RecurringWorkProfile,
        TaskTemplate,
    )

    subs = ClientServiceSubscription.objects.filter(tenant_id=tenant_id)
    templates = TaskTemplate.objects.filter(tenant_id=tenant_id)
    profiles = RecurringWorkProfile.objects.filter(tenant_id=tenant_id)
    ledger = GeneratedWorkLedger.objects.filter(tenant_id=tenant_id)

    subs_by_status = {}
    for s in subs:
        subs_by_status[s.status] = subs_by_status.get(s.status, 0) + 1

    return {
        "subscriptions_total": subs.count(),
        "subscriptions_by_status": subs_by_status,
        "task_templates_total": templates.count(),
        "task_templates_active": templates.filter(is_active=True).count(),
        "recurring_profiles_total": profiles.count(),
        "recurring_profiles_active": profiles.filter(is_active=True).count(),
        "generated_work_items_total": ledger.count(),
    }


# ---------------------------------------------------------------------------
# Employee Operations V1 — manager & firm operational aggregations (additive).
#
# All functions are read-only, tenant-scoped, deterministic and empty-safe.
# Capacity numbers are DERIVED via contexts.capacity.service (hours base unit);
# nothing is stored here.
# ---------------------------------------------------------------------------


def _emp_index(tenant_id):
    from contexts.identity.models import Employee

    return list(Employee.objects.filter(tenant_id=tenant_id, is_active=True))


def _open_workload_map(items):
    counts = {}
    for w in items:
        if w.status in ("COMPLETED", "CANCELLED"):
            continue
        oid = w.owner_user_id
        if oid is not None:
            counts[oid] = counts.get(oid, 0) + 1
    return counts


def manager_dashboard(tenant_id, manager_employee_id=None, period="month"):
    """Team-oriented operational view for a manager.

    When ``manager_employee_id`` is given, team members are those whose
    ``manager_id`` equals it; otherwise all active employees are considered
    (leadership view). Returns team workload, unassigned work, reviewer load and
    a per-member open-work breakdown. Capacity availability is derived per member
    for the current week.
    """
    import datetime as _dt

    from contexts.capacity import service as capacity_service

    items = list(_work_qs(tenant_id))
    employees = _emp_index(tenant_id)
    if manager_employee_id:
        members = [e for e in employees if str(getattr(e, "manager_id", None)) == str(manager_employee_id)]
    else:
        members = employees
    member_ids = {e.id for e in members}
    names = {e.id: e.name for e in members}

    workload = _open_workload_map(items)
    reviewer_load = {}
    for w in items:
        if w.status in ("COMPLETED", "CANCELLED"):
            continue
        rid = w.reviewer_user_id
        if rid is not None:
            reviewer_load[rid] = reviewer_load.get(rid, 0) + 1

    today = _dt.date.today()
    week_end = today + _dt.timedelta(days=6)
    member_rows = []
    over_allocated = []
    for e in members:
        available = capacity_service.available_hours_range(
            tenant_id, e.id, today, week_end, branch_id=e.branch_id, team_id=e.team_id
        )
        open_count = workload.get(e.id, 0)
        row = {
            "employee_id": str(e.id),
            "name": e.name,
            "open_work": open_count,
            "available_hours_week": float(available),
            "reviewer_open": reviewer_load.get(e.id, 0),
        }
        member_rows.append(row)
        if float(available) <= 0 and open_count > 0:
            over_allocated.append(row)

    unassigned = [w for w in items if w.owner_user_id is None and w.status not in ("COMPLETED", "CANCELLED")]

    return {
        "period": period,
        "team_size": len(members),
        "team_open_work": sum(1 for w in items if w.owner_user_id in member_ids and w.status not in ("COMPLETED", "CANCELLED")),
        "unassigned_work": len(unassigned),
        "over_allocated_count": len(over_allocated),
        "members": sorted(member_rows, key=lambda r: (-r["open_work"], r["name"])),
        "reviewer_bottlenecks": sorted(
            [{"reviewer_user_id": str(k), "name": names.get(k, ""), "open_reviews": v} for k, v in reviewer_load.items()],
            key=lambda r: -r["open_reviews"],
        )[:10],
    }


def firm_capacity_dashboard(tenant_id, period="month"):
    """Firm-wide capacity, utilization and backlog view (leadership).

    Aggregates derived weekly availability across all active employees and
    groups open work by branch/team/service for allocation visibility.
    """
    import datetime as _dt

    from contexts.capacity import service as capacity_service

    items = list(_work_qs(tenant_id))
    employees = _emp_index(tenant_id)
    workload = _open_workload_map(items)

    today = _dt.date.today()
    week_end = today + _dt.timedelta(days=6)

    total_available = 0.0
    per_branch = {}
    per_team = {}
    for e in employees:
        available = float(
            capacity_service.available_hours_range(
                tenant_id, e.id, today, week_end, branch_id=e.branch_id, team_id=e.team_id
            )
        )
        total_available += available
        if e.branch_id is not None:
            per_branch[str(e.branch_id)] = per_branch.get(str(e.branch_id), 0.0) + available
        if e.team_id is not None:
            per_team[str(e.team_id)] = per_team.get(str(e.team_id), 0.0) + available

    open_items = [w for w in items if w.status not in ("COMPLETED", "CANCELLED")]
    backlog_unassigned = sum(1 for w in open_items if w.owner_user_id is None)
    per_service = {}
    for w in open_items:
        if w.service_id is not None:
            per_service[str(w.service_id)] = per_service.get(str(w.service_id), 0) + 1

    return {
        "period": period,
        "active_employees": len(employees),
        "total_available_hours_week": round(total_available, 2),
        "open_work_total": len(open_items),
        "assignment_backlog_unassigned": backlog_unassigned,
        "available_hours_by_branch": {k: round(v, 2) for k, v in per_branch.items()},
        "available_hours_by_team": {k: round(v, 2) for k, v in per_team.items()},
        "open_work_by_service": per_service,
    }
