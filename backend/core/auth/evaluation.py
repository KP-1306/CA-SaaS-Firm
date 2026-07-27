"""Minimal framework-independent authorization evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.auth.contracts import (
    AuthorizationDecision,
    AuthorizationEvaluator,
    AuthorizationOutcome,
    AuthorizationRequest,
    PermissionCode,
    PrincipalIdentity,
    TenantIdentity,
)

__all__ = (
    "AuthorizationEngine",
    "RolePermissionEvaluator",
    "RolePermissionSource",
)


@dataclass(frozen=True, slots=True)
class AuthorizationEngine:
    """Evaluate ordered evaluators with deny-overrides, fail-closed semantics."""

    evaluators: tuple[AuthorizationEvaluator, ...]

    def __post_init__(self) -> None:
        if type(self.evaluators) is not tuple:
            raise TypeError("evaluators must be a tuple")
        for evaluator in self.evaluators:
            if not isinstance(evaluator, AuthorizationEvaluator):
                raise TypeError("every evaluator must satisfy AuthorizationEvaluator")

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        if not isinstance(request, AuthorizationRequest):
            raise TypeError("request must be an AuthorizationRequest")

        seen_allow = False
        for evaluator in self.evaluators:
            outcome = self._safe_outcome(evaluator, request)
            if outcome is AuthorizationOutcome.DENY:
                return AuthorizationDecision(request, AuthorizationOutcome.DENY)
            if outcome is AuthorizationOutcome.ALLOW:
                seen_allow = True
            # INDETERMINATE is an abstention and evaluation continues.

        return AuthorizationDecision(
            request,
            AuthorizationOutcome.ALLOW
            if seen_allow
            else AuthorizationOutcome.DENY,
        )

    @staticmethod
    def _safe_outcome(
        evaluator: AuthorizationEvaluator,
        request: AuthorizationRequest,
    ) -> AuthorizationOutcome:
        try:
            decision = evaluator.evaluate(request)
        except (KeyboardInterrupt, SystemExit, GeneratorExit):
            raise
        except Exception:
            return AuthorizationOutcome.DENY

        if type(decision) is not AuthorizationDecision:
            return AuthorizationOutcome.DENY
        if decision.request is not request:
            return AuthorizationOutcome.DENY
        if decision.outcome is AuthorizationOutcome.ALLOW:
            return AuthorizationOutcome.ALLOW
        if decision.outcome is AuthorizationOutcome.DENY:
            return AuthorizationOutcome.DENY
        if decision.outcome is AuthorizationOutcome.INDETERMINATE:
            return AuthorizationOutcome.INDETERMINATE
        return AuthorizationOutcome.DENY


@runtime_checkable
class RolePermissionSource(Protocol):
    """Provide one permission fact for a principal inside a tenant."""

    def has_permission(
        self,
        tenant_identity: TenantIdentity,
        principal_identity: PrincipalIdentity,
        permission: PermissionCode,
    ) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class RolePermissionEvaluator:
    """Allow only when the source returns the exact bool value True."""

    source: RolePermissionSource

    def __post_init__(self) -> None:
        if not isinstance(self.source, RolePermissionSource):
            raise TypeError("source must satisfy RolePermissionSource")

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        if not isinstance(request, AuthorizationRequest):
            raise TypeError("request must be an AuthorizationRequest")

        result = self.source.has_permission(
            request.authorization_context.tenant_identity,
            request.authorization_context.principal_identity,
            request.permission_code,
        )
        return AuthorizationDecision(
            request,
            AuthorizationOutcome.ALLOW
            if type(result) is bool and result is True
            else AuthorizationOutcome.DENY,
        )
