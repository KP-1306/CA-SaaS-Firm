"""Authentication and authorisation infrastructure.

``core.auth`` owns the project's authentication and authorisation
infrastructure. It currently provides the pure-Python authorisation and
authentication foundation: the canonical string-enum vocabulary and the
immutable identity, scope, result, session and context value objects.
Authentication implementation, sessions persistence, permission decisions,
middleware, tenant resolution, workflow enforcement, row-level security,
support grants and audit persistence remain later work packages. Nothing
exported here grants authority, evaluates permissions or accesses a database.
"""

from __future__ import annotations

from core.auth.contracts import (
    AccessPlane,
    AssignmentScope,
    AssignmentStatus,
    AssignmentTarget,
    AuthenticationContext,
    AuthenticationFailureReason,
    AuthenticationMethod,
    AuthenticationResult,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationEvaluator,
    AuthorizationOutcome,
    AuthorizationRequest,
    DataClassification,
    EmploymentDesignation,
    OperationalRole,
    PermissionCode,
    PrincipalIdentity,
    PrincipalStatus,
    PrincipalType,
    ServiceDomain,
    SessionIdentity,
    StrictStringEnum,
    TenantContext,
    TenantIdentity,
    TenantResolutionFailureReason,
    TenantResolutionInput,
    TenantResolutionResult,
    TenantResolutionSource,
    TenantResolver,
)

__all__ = (
    "AccessPlane",
    "AssignmentScope",
    "AssignmentStatus",
    "AssignmentTarget",
    "AuthenticationContext",
    "AuthenticationFailureReason",
    "AuthenticationMethod",
    "AuthenticationResult",
    "AuthorizationContext",
    "AuthorizationDecision",
    "AuthorizationEvaluator",
    "AuthorizationOutcome",
    "AuthorizationRequest",
    "DataClassification",
    "EmploymentDesignation",
    "OperationalRole",
    "PermissionCode",
    "PrincipalIdentity",
    "PrincipalStatus",
    "PrincipalType",
    "ServiceDomain",
    "SessionIdentity",
    "StrictStringEnum",
    "TenantContext",
    "TenantIdentity",
    "TenantResolutionFailureReason",
    "TenantResolutionInput",
    "TenantResolutionResult",
    "TenantResolutionSource",
    "TenantResolver",
)
