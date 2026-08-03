"""Deterministic assignment eligibility and recommendation engine.

Approved decision 10: recommendations are computed transiently and never persisted;
only the approved decision is stored (by the viewset). This engine is pure and
explainable — given the same data it returns the same ranked list with the same
score breakdown. It NEVER assigns automatically and NEVER uses randomness or a
learned model.

Eligibility (hard filters) and scoring (soft, weighted) are separated so a
recommendation can always explain both why someone was eligible and why they
ranked where they did.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from contexts.identity.models import Employee, EmployeeExpertise
from contexts.capacity import service as capacity_service


# Deterministic, documented weights (see ASSIGNMENT_RULE_CONTRACT.md).
_WEIGHTS = {
    "expertise": 40,
    "availability": 30,
    "workload": 20,
    "designation": 10,
}


def _active_employees(tenant_id):
    return list(Employee.objects.filter(tenant_id=tenant_id, is_active=True))


def _expertise_map(tenant_id, category):
    """employee_id -> proficiency for a category (active rows only)."""
    out = {}
    if not category:
        return out
    qs = EmployeeExpertise.objects.filter(
        tenant_id=tenant_id, category=category, is_active=True
    )
    for e in qs:
        out[e.employee_id] = e.proficiency
    return out


def _open_workload(tenant_id):
    """employee_id -> count of open work items (owner), for load balancing."""
    from contexts.work.models import WorkItem

    counts = {}
    qs = WorkItem.objects.filter(tenant_id=tenant_id).exclude(status__in=("COMPLETED", "CANCELLED"))
    for w in qs.values_list("owner_user_id", flat=True):
        if w is not None:
            counts[w] = counts.get(w, 0) + 1
    return counts


_PROFICIENCY_SCORE = {
    "BEGINNER": 0.4,
    "INTERMEDIATE": 0.6,
    "ADVANCED": 0.8,
    "SME": 1.0,
    "REVIEWER": 1.0,
    # legacy values tolerated pre-migration
    "BASIC": 0.4,
    "EXPERT": 1.0,
}


def eligibility(employee, *, context, expertise_map):
    """Return (is_eligible, reasons[]) for hard filters.

    Hard filters: active (already filtered), branch/department/team/designation
    match when the context constrains them, and expertise presence when a
    required category is given.
    """
    reasons = []
    ok = True

    def require(cond, ok_msg, fail_msg):
        nonlocal ok
        if cond:
            reasons.append(ok_msg)
        else:
            ok = False
            reasons.append(fail_msg)

    if context.get("branch_id"):
        require(employee.branch_id == context["branch_id"], "branch match", "branch mismatch")
    if context.get("department_id"):
        require(employee.department_id == context["department_id"], "department match", "department mismatch")
    if context.get("team_id"):
        require(employee.team_id == context["team_id"], "team match", "team mismatch")
    if context.get("designation_id"):
        require(employee.designation_id == context["designation_id"], "designation match", "designation mismatch")
    if context.get("required_category"):
        has = employee.id in expertise_map
        require(has, "has required expertise", "missing required expertise")
    if context.get("reviewer_required"):
        # reviewer eligibility: an active reviewer_eligible expertise row in category
        from contexts.identity.models import EmployeeExpertise as EE

        elig = EE.objects.filter(
            tenant_id=employee.tenant_id, employee_id=employee.id,
            category=context.get("required_category"), reviewer_eligible=True, is_active=True,
        ).exists()
        require(elig, "reviewer eligible", "not reviewer eligible")

    return ok, reasons


def _score_breakdown(employee, *, context, expertise_map, workload, availability_hours, max_workload):
    """Deterministic weighted score with a per-factor breakdown (0..100)."""
    breakdown = {}

    prof = expertise_map.get(employee.id)
    expertise_factor = _PROFICIENCY_SCORE.get(prof, 0.0) if prof else 0.0
    breakdown["expertise"] = round(_WEIGHTS["expertise"] * expertise_factor, 2)

    # Availability: normalize against the requested estimated hours (or 8h/day baseline).
    needed = float(context.get("estimated_hours") or 0) or 8.0
    avail_factor = min(float(availability_hours) / needed, 1.0) if needed > 0 else 0.0
    breakdown["availability"] = round(_WEIGHTS["availability"] * avail_factor, 2)

    # Workload: fewer open items scores higher (inverse, normalized).
    my_load = workload.get(employee.id, 0)
    load_factor = 1.0 - (my_load / max_workload if max_workload > 0 else 0.0)
    breakdown["workload"] = round(_WEIGHTS["workload"] * load_factor, 2)

    # Designation: exact match to a requested designation gives full weight.
    des_factor = 1.0 if (context.get("designation_id") and employee.designation_id == context["designation_id"]) else 0.0
    breakdown["designation"] = round(_WEIGHTS["designation"] * des_factor, 2)

    total = round(sum(breakdown.values()), 2)
    return total, breakdown


def recommend(tenant_id, context, *, on_date=None, limit=10):
    """Return a deterministic, ranked, explainable recommendation list.

    ``context`` keys (all optional): required_category, service_id, branch_id,
    department_id, team_id, designation_id, estimated_hours, due_date,
    priority, reviewer_required.

    Returns ``{"generated_on", "context", "candidates": [...]}`` where each
    candidate has employee_id, name, eligible, eligibility_reasons, score and
    score_breakdown. Ties break deterministically by (‑score, name, id).
    """
    on_date = on_date or _dt.date.today()
    category = context.get("required_category")
    expertise_map = _expertise_map(tenant_id, category)
    workload = _open_workload(tenant_id)
    max_workload = max(workload.values(), default=0)

    # Availability window: today .. due_date (or a 7-day default horizon).
    due = context.get("due_date")
    if isinstance(due, str) and due:
        try:
            due = _dt.date.fromisoformat(due)
        except ValueError:
            due = None
    end_date = due if isinstance(due, _dt.date) else on_date + _dt.timedelta(days=7)

    rows = []
    for emp in _active_employees(tenant_id):
        eligible, reasons = eligibility(emp, context=context, expertise_map=expertise_map)
        availability = capacity_service.available_hours_range(
            tenant_id, emp.id, on_date, end_date,
            branch_id=emp.branch_id, team_id=emp.team_id,
        )
        score, breakdown = _score_breakdown(
            emp, context=context, expertise_map=expertise_map,
            workload=workload, availability_hours=availability, max_workload=max_workload,
        )
        rows.append(
            {
                "employee_id": str(emp.id),
                "name": emp.name,
                "eligible": eligible,
                "eligibility_reasons": reasons,
                "available_hours": float(availability),
                "open_workload": workload.get(emp.id, 0),
                "score": score if eligible else 0.0,
                "score_breakdown": breakdown if eligible else {},
            }
        )

    # Eligible first, then score desc, then deterministic tiebreak.
    rows.sort(key=lambda r: (not r["eligible"], -r["score"], r["name"], r["employee_id"]))
    return {
        "generated_on": on_date.isoformat(),
        "context": {k: (v.isoformat() if isinstance(v, _dt.date) else v) for k, v in context.items()},
        "weights": dict(_WEIGHTS),
        "candidates": rows[: max(1, int(limit))],
    }
