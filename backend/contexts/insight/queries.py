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
    }
