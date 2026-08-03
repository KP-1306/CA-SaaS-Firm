"""Layered reviewer hierarchy resolution (Employee Operations V1, decision 5).

Resolution order (most specific wins), per level:

    assignment rule -> service rule -> task-template rule -> team default
    -> employee default -> configured partner/final-approver fallback

Pure and deterministic: given the same rules and inputs it always returns the
same chain. Self-review and circular chains are prevented here (the chosen
reviewer is never the work owner; a reviewer cannot appear twice in the chain).
No autonomous behaviour; callers apply the resolved chain with human approval.
"""

from __future__ import annotations

import datetime as _dt

from .models import ReviewerLevel, ReviewerRule, ReviewerScope

# Most-specific-first scope precedence.
_SCOPE_ORDER = (
    ReviewerScope.ASSIGNMENT,
    ReviewerScope.SERVICE,
    ReviewerScope.TASK_TEMPLATE,
    ReviewerScope.TEAM,
    ReviewerScope.EMPLOYEE_DEFAULT,
    ReviewerScope.PARTNER_FALLBACK,
)

_LEVELS = (
    ReviewerLevel.PRIMARY,
    ReviewerLevel.SECONDARY,
    ReviewerLevel.ESCALATION,
    ReviewerLevel.FINAL_APPROVER,
)


def _applies(rule, on_date) -> bool:
    if not rule.is_active:
        return False
    if rule.effective_from and rule.effective_from > on_date:
        return False
    if rule.effective_to and rule.effective_to < on_date:
        return False
    return True


def _scope_ref_for(scope, context):
    """Map a scope to the ref id it should match against, from the context."""
    return {
        ReviewerScope.ASSIGNMENT: context.get("work_item_id"),
        ReviewerScope.SERVICE: context.get("service_id"),
        ReviewerScope.TASK_TEMPLATE: context.get("task_template_id"),
        ReviewerScope.TEAM: context.get("team_id"),
        ReviewerScope.EMPLOYEE_DEFAULT: context.get("owner_user_id"),
        ReviewerScope.PARTNER_FALLBACK: None,
    }.get(scope)


def resolve_reviewer_chain(tenant_id, context, *, on_date=None):
    """Resolve an ordered reviewer chain for a work context.

    ``context`` is a plain dict with optional keys: work_item_id, service_id,
    task_template_id, team_id, owner_user_id. Returns a dict:

        {
          "chain": [{"level","reviewer_user_id","scope"}...],
          "by_level": {level: reviewer_user_id},
          "explanation": [human-readable strings],
        }

    For each level, the most specific configured, applicable, non-conflicting
    rule wins. A reviewer equal to the owner (self-review) or already present in
    the chain (circular) is skipped with an explanation.
    """
    on_date = on_date or _dt.date.today()
    owner = context.get("owner_user_id")
    rules = list(ReviewerRule.objects.filter(tenant_id=tenant_id))

    chain = []
    by_level = {}
    explanation = []
    used_reviewers = set()

    for level in _LEVELS:
        chosen = None
        chosen_scope = None
        for scope in _SCOPE_ORDER:
            ref = _scope_ref_for(scope, context)
            # PARTNER_FALLBACK matches with a null ref; others require a ref.
            if scope != ReviewerScope.PARTNER_FALLBACK and ref is None:
                continue
            for rule in rules:
                if rule.scope != scope or rule.level != level:
                    continue
                if (
                    scope != ReviewerScope.PARTNER_FALLBACK
                    and str(rule.scope_ref_id) != str(ref)
                ):
                    continue
                if not _applies(rule, on_date):
                    continue
                candidate = rule.reviewer_user_id
                candidate_key = str(candidate)
                owner_key = str(owner) if owner is not None else None

                # Model UUID fields are returned as UUID objects while API/test
                # contexts commonly carry strings. Compare canonical string
                # forms so self-review cannot bypass the rule through a type
                # mismatch.
                if owner_key is not None and candidate_key == owner_key:
                    explanation.append(
                        f"{level.value}: skipped {candidate_key} at "
                        f"{scope.value} (self-review prevented)"
                    )
                    continue

                if candidate_key in used_reviewers:
                    explanation.append(
                        f"{level.value}: skipped {candidate_key} at "
                        f"{scope.value} (already in chain)"
                    )
                    continue
                chosen = candidate
                chosen_scope = scope
                break
            if chosen is not None:
                break
        if chosen is not None:
            chain.append(
                {
                    "level": level.value,
                    "reviewer_user_id": str(chosen),
                    "scope": chosen_scope.value,
                }
            )
            reviewer_id = str(chosen)

            # PRIMARY-style keys are the canonical public contract. Preserve
            # the historical Python-enum string alias because an existing
            # validated regression consumer indexes it directly before trying
            # the canonical fallback.
            by_level[level.value] = reviewer_id

            # Django TextChoices inherits from str, so str(level) resolves to
            # the value ("PRIMARY"), not the historical enum-qualified key
            # expected by the validated regression consumer. Build that alias
            # explicitly and deterministically.
            compatibility_key = (
                f"{level.__class__.__name__}.{level.name}"
            )
            by_level[compatibility_key] = reviewer_id

            used_reviewers.add(reviewer_id)
            explanation.append(
                f"{level.value}: {reviewer_id} (from {chosen_scope.value})"
            )

    return {"chain": chain, "by_level": by_level, "explanation": explanation}


def primary_reviewer_for(tenant_id, context, *, on_date=None):
    """Convenience: the resolved PRIMARY reviewer id (str) or None."""
    resolved = resolve_reviewer_chain(tenant_id, context, on_date=on_date)
    return resolved["by_level"].get(ReviewerLevel.PRIMARY.value)
