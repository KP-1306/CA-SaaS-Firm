"""Canonical authorisation foundation: vocabulary and immutable value objects.

EWP-1.1 supersedes the vocabulary-only package. It provides the pure-Python
authorisation foundation that later authentication, authorisation, workflow and
permission work builds on:

* the canonical string-enum vocabulary, parsed strictly and non-coercively;
* immutable, hashable, dictionary-serialisable identity and scope value objects.

Nothing here evaluates permissions, resolves tenants, touches a database or
imports Django. Enum serialised values are lowercase snake case and are treated
as a stable persisted contract; ``parse`` matches them exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable
from uuid import UUID

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


class StrictStringEnum(StrEnum):
    """String enum with strict, non-coercing external parsing.

    ``parse`` accepts only a plain ``str`` whose content exactly equals one
    canonical value. It never trims, never changes case, never accepts member
    names or aliases, and never accepts an existing enum member (which, though a
    ``str`` subclass instance, is not a plain ``str``).
    """

    @classmethod
    def parse(cls, value: object) -> Self:
        """Return the member whose canonical value exactly equals ``value``.

        Raises ``TypeError`` for any non-``str`` input (including ``bool``,
        ``int`` and enum members) and ``ValueError`` for an unknown string.
        """
        if type(value) is not str:
            raise TypeError(
                f"{cls.__name__}.parse requires a plain str, "
                f"got {type(value).__name__}"
            )
        try:
            return cls(value)
        except ValueError:
            raise ValueError(
                f"{cls.__name__} has no member with value {value!r}"
            ) from None


class PrincipalType(StrictStringEnum):
    """Identity classification of a principal. Not an authority."""

    FIRM_USER = "firm_user"
    CLIENT_USER = "client_user"
    EXTERNAL_COLLABORATOR = "external_collaborator"
    PLATFORM_USER = "platform_user"
    INTEGRATION_SERVICE = "integration_service"
    BACKGROUND_JOB = "background_job"


class PrincipalStatus(StrictStringEnum):
    """Lifecycle status vocabulary for a principal. No transition logic."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AssignmentScope(StrictStringEnum):
    """Scope kind an assignment targets. Does not imply inheritance."""

    TENANT = "tenant"
    CLIENT = "client"
    LEGAL_ENTITY = "legal_entity"
    SERVICE_DOMAIN = "service_domain"
    ENGAGEMENT = "engagement"


class AssignmentStatus(StrictStringEnum):
    """Lifecycle status vocabulary for an assignment. No transition logic."""

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AccessPlane(StrictStringEnum):
    """Access plane through which a request is served. Classification only."""

    INTERNAL = "internal"
    CLIENT_PORTAL = "client_portal"
    SUPPORT = "support"
    API = "api"
    SYSTEM = "system"


class EmploymentDesignation(StrictStringEnum):
    """Descriptive organisational designation. Does not grant permission."""

    PARTNER = "partner"
    DIRECTOR = "director"
    SENIOR_MANAGER = "senior_manager"
    MANAGER = "manager"
    ASSISTANT_MANAGER = "assistant_manager"
    SENIOR_ASSOCIATE = "senior_associate"
    ASSOCIATE = "associate"
    ARTICLE_ASSISTANT = "article_assistant"
    EXECUTIVE = "executive"
    ADMINISTRATOR = "administrator"
    SUPPORT_STAFF = "support_staff"
    CLIENT_USER = "client_user"
    EXTERNAL_COLLABORATOR = "external_collaborator"


class OperationalRole(StrictStringEnum):
    """Scoped operational responsibility. Not a global permission."""

    ENGAGEMENT_OWNER = "engagement_owner"
    MODULE_LEAD = "module_lead"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    QA_REVIEWER = "qa_reviewer"
    APPROVER = "approver"
    CLIENT_COORDINATOR = "client_coordinator"
    CLIENT_DOCUMENT_USER = "client_document_user"
    PLATFORM_SUPPORT = "platform_support"
    SYSTEM = "system"


class ServiceDomain(StrictStringEnum):
    """Canonical service domain vocabulary."""

    GST = "gst"
    INCOME_TAX = "income_tax"
    TDS = "tds"
    ACCOUNTING = "accounting"
    PAYROLL = "payroll"
    AUDIT = "audit"
    ROC = "roc"
    COMPANY_INCORPORATION = "company_incorporation"
    FINANCIAL_REPORTING = "financial_reporting"
    NOTICES = "notices"
    ADVISORY = "advisory"


class DataClassification(StrictStringEnum):
    """Data sensitivity vocabulary. An input to later policy, not a decision."""

    GENERAL_ENGAGEMENT = "general_engagement"
    ASSIGNED_TEAM_ONLY = "assigned_team_only"
    QA_ONLY = "qa_only"
    LEADERSHIP_ONLY = "leadership_only"
    PARTNER_DIRECTOR_ONLY = "partner_director_only"
    ADMINISTRATIVE_ONLY = "administrative_only"
    CLIENT_VISIBLE = "client_visible"
    PLATFORM_SUPPORT_RESTRICTED = "platform_support_restricted"


@dataclass(frozen=True, slots=True)
class TenantIdentity:
    """Immutable tenant identifier.

    Holds a ``uuid.UUID`` verbatim; performs no coercion and grants no access.
    """

    tenant_id: UUID

    def __post_init__(self) -> None:
        """Validate that ``tenant_id`` is an actual UUID."""
        if type(self.tenant_id) is not UUID:
            raise TypeError("tenant_id must be a uuid.UUID")

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain JSON-safe dictionary."""
        return {"tenant_id": str(self.tenant_id)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(tenant_id=UUID(data["tenant_id"]))


@dataclass(frozen=True, slots=True)
class PrincipalIdentity:
    """Immutable identity of an authenticated principal.

    Carries only the principal's UUID and its canonical :class:`PrincipalType`.
    It holds no tenant, status, designation, role or permission data and makes
    no access decision.
    """

    principal_id: UUID
    principal_type: PrincipalType

    def __post_init__(self) -> None:
        """Validate identifier and canonical enum membership exactly."""
        if type(self.principal_id) is not UUID:
            raise TypeError("principal_id must be a uuid.UUID")
        if type(self.principal_type) is not PrincipalType:
            raise TypeError("principal_type must be a PrincipalType")

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "principal_id": str(self.principal_id),
            "principal_type": self.principal_type.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            principal_id=UUID(data["principal_id"]),
            principal_type=PrincipalType.parse(data["principal_type"]),
        )


@dataclass(frozen=True, slots=True)
class AssignmentTarget:
    """Immutable target an assignment applies to.

    ``TENANT`` scope targets the tenant itself and carries no ``resource_id``.
    Every other scope targets an identified resource under that tenant. This
    object verifies structure only: it does not confirm the resource exists,
    consult a database, or imply that a scope expands to child records.
    """

    tenant_id: UUID
    scope: AssignmentScope
    resource_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate identifiers, canonical scope, and the scope/resource rule."""
        if type(self.tenant_id) is not UUID:
            raise TypeError("tenant_id must be a uuid.UUID")
        if type(self.scope) is not AssignmentScope:
            raise TypeError("scope must be an AssignmentScope")
        if self.resource_id is not None and type(self.resource_id) is not UUID:
            raise TypeError("resource_id must be a uuid.UUID or None")
        if self.scope is AssignmentScope.TENANT:
            if self.resource_id is not None:
                raise ValueError("TENANT scope must not carry a resource_id")
        elif self.resource_id is None:
            raise ValueError(f"{self.scope.value} scope requires a resource_id")

    def to_dict(self) -> dict[str, str | None]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "tenant_id": str(self.tenant_id),
            "scope": self.scope.value,
            "resource_id": None if self.resource_id is None else str(self.resource_id),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        raw_resource = data.get("resource_id")
        return cls(
            tenant_id=UUID(data["tenant_id"]),
            scope=AssignmentScope.parse(data["scope"]),
            resource_id=None if raw_resource is None else UUID(raw_resource),
        )


class AuthenticationMethod(StrictStringEnum):
    """How a principal was authenticated. Classification only."""

    PASSWORD = "password"
    SSO = "sso"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"
    SUPPORT_SESSION = "support_session"
    SYSTEM = "system"


class AuthenticationFailureReason(StrictStringEnum):
    """Why an authentication attempt failed. Classification only."""

    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_DISABLED = "account_disabled"
    TENANT_DISABLED = "tenant_disabled"
    AUTHENTICATION_REQUIRED = "authentication_required"
    INVALID_TOKEN = "invalid_token"
    INVALID_API_KEY = "invalid_api_key"
    SESSION_EXPIRED = "session_expired"
    EXPIRED_CREDENTIALS = "expired_credentials"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Immutable outcome of a single authentication attempt.

    A result is either a success carrying the resolved identities and method, or
    a failure carrying a reason. The two shapes are mutually exclusive and are
    enforced in ``__post_init__``. This object records an outcome only; it makes
    no access decision.
    """

    success: bool
    principal_identity: PrincipalIdentity | None = None
    tenant_identity: TenantIdentity | None = None
    authentication_method: AuthenticationMethod | None = None
    failure_reason: AuthenticationFailureReason | None = None

    def __post_init__(self) -> None:
        """Enforce field types and the success/failure exclusivity rule."""
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        self._validate_field_types()
        if self.success:
            self._validate_success_shape()
        else:
            self._validate_failure_shape()

    def _validate_field_types(self) -> None:
        """Validate that populated fields have their declared types."""
        if self.principal_identity is not None and not isinstance(
            self.principal_identity, PrincipalIdentity
        ):
            raise TypeError("principal_identity must be a PrincipalIdentity or None")
        if self.tenant_identity is not None and not isinstance(
            self.tenant_identity, TenantIdentity
        ):
            raise TypeError("tenant_identity must be a TenantIdentity or None")
        if self.authentication_method is not None and type(
            self.authentication_method
        ) is not AuthenticationMethod:
            raise TypeError("authentication_method must be an AuthenticationMethod or None")
        if self.failure_reason is not None and type(
            self.failure_reason
        ) is not AuthenticationFailureReason:
            raise TypeError("failure_reason must be an AuthenticationFailureReason or None")

    def _validate_success_shape(self) -> None:
        """A success carries identities and method, and no failure reason."""
        if self.failure_reason is not None:
            raise ValueError("a successful result must not carry a failure_reason")
        if self.principal_identity is None:
            raise ValueError("a successful result requires a principal_identity")
        if self.tenant_identity is None:
            raise ValueError("a successful result requires a tenant_identity")
        if self.authentication_method is None:
            raise ValueError("a successful result requires an authentication_method")

    def _validate_failure_shape(self) -> None:
        """A failure carries a reason and no identities or method."""
        if self.failure_reason is None:
            raise ValueError("a failed result requires a failure_reason")
        if self.principal_identity is not None:
            raise ValueError("a failed result must not carry a principal_identity")
        if self.tenant_identity is not None:
            raise ValueError("a failed result must not carry a tenant_identity")
        if self.authentication_method is not None:
            raise ValueError("a failed result must not carry an authentication_method")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "success": self.success,
            "principal_identity": (
                None
                if self.principal_identity is None
                else self.principal_identity.to_dict()
            ),
            "tenant_identity": (
                None if self.tenant_identity is None else self.tenant_identity.to_dict()
            ),
            "authentication_method": (
                None
                if self.authentication_method is None
                else self.authentication_method.value
            ),
            "failure_reason": (
                None if self.failure_reason is None else self.failure_reason.value
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        principal = data.get("principal_identity")
        tenant = data.get("tenant_identity")
        method = data.get("authentication_method")
        reason = data.get("failure_reason")
        return cls(
            success=data["success"],
            principal_identity=(
                None if principal is None else PrincipalIdentity.from_dict(principal)
            ),
            tenant_identity=(
                None if tenant is None else TenantIdentity.from_dict(tenant)
            ),
            authentication_method=(
                None if method is None else AuthenticationMethod.parse(method)
            ),
            failure_reason=(
                None if reason is None else AuthenticationFailureReason.parse(reason)
            ),
        )


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    """Immutable identity of an authenticated session.

    Records which principal was authenticated, under which tenant, by which
    method, and at what instant. It holds no expiry, token, cookie or
    persistence concern.
    """

    session_id: UUID
    principal_identity: PrincipalIdentity
    tenant_identity: TenantIdentity
    authentication_method: AuthenticationMethod
    authenticated_at: datetime

    def __post_init__(self) -> None:
        """Validate identifiers, composed identities, method and timestamp."""
        if type(self.session_id) is not UUID:
            raise TypeError("session_id must be a uuid.UUID")
        if not isinstance(self.principal_identity, PrincipalIdentity):
            raise TypeError("principal_identity must be a PrincipalIdentity")
        if not isinstance(self.tenant_identity, TenantIdentity):
            raise TypeError("tenant_identity must be a TenantIdentity")
        if type(self.authentication_method) is not AuthenticationMethod:
            raise TypeError("authentication_method must be an AuthenticationMethod")
        if type(self.authenticated_at) is not datetime:
            raise TypeError("authenticated_at must be a datetime")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "session_id": str(self.session_id),
            "principal_identity": self.principal_identity.to_dict(),
            "tenant_identity": self.tenant_identity.to_dict(),
            "authentication_method": self.authentication_method.value,
            "authenticated_at": self.authenticated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            session_id=UUID(data["session_id"]),
            principal_identity=PrincipalIdentity.from_dict(data["principal_identity"]),
            tenant_identity=TenantIdentity.from_dict(data["tenant_identity"]),
            authentication_method=AuthenticationMethod.parse(
                data["authentication_method"]
            ),
            authenticated_at=datetime.fromisoformat(data["authenticated_at"]),
        )


@dataclass(frozen=True, slots=True)
class AuthenticationContext:
    """Immutable authenticated runtime state: a session on an access plane.

    Represents who is authenticated and through which plane the request arrived.
    It carries no request object, middleware state or permission decision.
    """

    session: SessionIdentity
    access_plane: AccessPlane

    def __post_init__(self) -> None:
        """Validate that both composed fields are present and correctly typed."""
        if not isinstance(self.session, SessionIdentity):
            raise TypeError("session must be a SessionIdentity")
        if type(self.access_plane) is not AccessPlane:
            raise TypeError("access_plane must be an AccessPlane")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "session": self.session.to_dict(),
            "access_plane": self.access_plane.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            session=SessionIdentity.from_dict(data["session"]),
            access_plane=AccessPlane.parse(data["access_plane"]),
        )


class TenantResolutionSource(StrictStringEnum):
    """Authoritative source a tenant reference was obtained from.

    Classifies the source only. It performs no parsing, lookup, validation or
    resolution.
    """

    HOSTNAME = "hostname"
    SUBDOMAIN = "subdomain"
    HEADER = "header"
    JWT = "jwt"
    API_KEY = "api_key"
    SYSTEM = "system"


class TenantResolutionFailureReason(StrictStringEnum):
    """Canonical reason tenant resolution failed. Classification only."""

    TENANT_NOT_FOUND = "tenant_not_found"
    TENANT_DISABLED = "tenant_disabled"
    INVALID_HOST = "invalid_host"
    INVALID_SUBDOMAIN = "invalid_subdomain"
    INVALID_HEADER = "invalid_header"
    INVALID_JWT_REFERENCE = "invalid_jwt_reference"
    INVALID_API_KEY_REFERENCE = "invalid_api_key_reference"
    MULTIPLE_MATCHES = "multiple_matches"
    RESOLUTION_REQUIRED = "resolution_required"
    SOURCE_CONFLICT = "source_conflict"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class TenantResolutionInput:
    """Already-extracted candidate tenant references supplied to a resolver.

    Carries values only. It parses no HTTP request, header, JWT, API key,
    hostname or subdomain; extraction is the caller's responsibility and lookup
    is the future resolver's. Values are stored verbatim (never trimmed or
    normalised); at least one candidate must be populated.
    """

    hostname: str | None = None
    subdomain: str | None = None
    header_reference: str | None = None
    jwt_reference: str | None = None
    api_key_reference: str | None = None
    system_tenant_identity: TenantIdentity | None = None

    def __post_init__(self) -> None:
        """Validate field types, reject blank strings and empty input."""
        string_fields = {
            "hostname": self.hostname,
            "subdomain": self.subdomain,
            "header_reference": self.header_reference,
            "jwt_reference": self.jwt_reference,
            "api_key_reference": self.api_key_reference,
        }
        for name, value in string_fields.items():
            if value is not None:
                if type(value) is not str:
                    raise TypeError(f"{name} must be a str or None")
                if value == "" or value.strip() == "":
                    raise ValueError(f"{name} must not be blank")
        if self.system_tenant_identity is not None and not isinstance(
            self.system_tenant_identity, TenantIdentity
        ):
            raise TypeError("system_tenant_identity must be a TenantIdentity or None")
        populated = any(v is not None for v in string_fields.values()) or (
            self.system_tenant_identity is not None
        )
        if not populated:
            raise ValueError("at least one candidate source must be populated")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "hostname": self.hostname,
            "subdomain": self.subdomain,
            "header_reference": self.header_reference,
            "jwt_reference": self.jwt_reference,
            "api_key_reference": self.api_key_reference,
            "system_tenant_identity": (
                None
                if self.system_tenant_identity is None
                else self.system_tenant_identity.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        system = data.get("system_tenant_identity")
        return cls(
            hostname=data.get("hostname"),
            subdomain=data.get("subdomain"),
            header_reference=data.get("header_reference"),
            jwt_reference=data.get("jwt_reference"),
            api_key_reference=data.get("api_key_reference"),
            system_tenant_identity=(
                None if system is None else TenantIdentity.from_dict(system)
            ),
        )


@dataclass(frozen=True, slots=True)
class TenantResolutionResult:
    """Immutable outcome of a tenant resolution attempt.

    A result is either a success carrying the resolved tenant and its source, or
    a failure carrying a reason. The two shapes are mutually exclusive and are
    enforced in ``__post_init__``. This object records an outcome only.
    """

    success: bool
    tenant_identity: TenantIdentity | None = None
    resolution_source: TenantResolutionSource | None = None
    failure_reason: TenantResolutionFailureReason | None = None

    def __post_init__(self) -> None:
        """Enforce field types and the success/failure exclusivity rule."""
        if type(self.success) is not bool:
            raise TypeError("success must be a bool")
        if self.tenant_identity is not None and not isinstance(
            self.tenant_identity, TenantIdentity
        ):
            raise TypeError("tenant_identity must be a TenantIdentity or None")
        if self.resolution_source is not None and type(
            self.resolution_source
        ) is not TenantResolutionSource:
            raise TypeError("resolution_source must be a TenantResolutionSource or None")
        if self.failure_reason is not None and type(
            self.failure_reason
        ) is not TenantResolutionFailureReason:
            raise TypeError(
                "failure_reason must be a TenantResolutionFailureReason or None"
            )
        if self.success:
            self._validate_success_shape()
        else:
            self._validate_failure_shape()

    def _validate_success_shape(self) -> None:
        """A success carries a tenant and source, and no failure reason."""
        if self.tenant_identity is None:
            raise ValueError("a successful result requires a tenant_identity")
        if self.resolution_source is None:
            raise ValueError("a successful result requires a resolution_source")
        if self.failure_reason is not None:
            raise ValueError("a successful result must not carry a failure_reason")

    def _validate_failure_shape(self) -> None:
        """A failure carries a reason and no tenant or source."""
        if self.failure_reason is None:
            raise ValueError("a failed result requires a failure_reason")
        if self.tenant_identity is not None:
            raise ValueError("a failed result must not carry a tenant_identity")
        if self.resolution_source is not None:
            raise ValueError("a failed result must not carry a resolution_source")

    @classmethod
    def success_result(
        cls,
        tenant_identity: TenantIdentity,
        resolution_source: TenantResolutionSource,
    ) -> Self:
        """Build a successful result from a resolved tenant and its source."""
        return cls(
            success=True,
            tenant_identity=tenant_identity,
            resolution_source=resolution_source,
        )

    @classmethod
    def failure_result(
        cls,
        failure_reason: TenantResolutionFailureReason,
    ) -> Self:
        """Build a failed result from a canonical failure reason."""
        return cls(success=False, failure_reason=failure_reason)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "success": self.success,
            "tenant_identity": (
                None if self.tenant_identity is None else self.tenant_identity.to_dict()
            ),
            "resolution_source": (
                None if self.resolution_source is None else self.resolution_source.value
            ),
            "failure_reason": (
                None if self.failure_reason is None else self.failure_reason.value
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        tenant = data.get("tenant_identity")
        source = data.get("resolution_source")
        reason = data.get("failure_reason")
        return cls(
            success=data["success"],
            tenant_identity=(
                None if tenant is None else TenantIdentity.from_dict(tenant)
            ),
            resolution_source=(
                None if source is None else TenantResolutionSource.parse(source)
            ),
            failure_reason=(
                None if reason is None else TenantResolutionFailureReason.parse(reason)
            ),
        )


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Immutable, already-successfully-resolved tenant context.

    Carries the resolved tenant and the source it was resolved from, and nothing
    else: no resolution result, authentication, principal, request, permission,
    status, failure or mutable state.
    """

    tenant_identity: TenantIdentity
    resolution_source: TenantResolutionSource

    def __post_init__(self) -> None:
        """Validate that both mandatory fields have their canonical types."""
        if not isinstance(self.tenant_identity, TenantIdentity):
            raise TypeError("tenant_identity must be a TenantIdentity")
        if type(self.resolution_source) is not TenantResolutionSource:
            raise TypeError("resolution_source must be a TenantResolutionSource")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "tenant_identity": self.tenant_identity.to_dict(),
            "resolution_source": self.resolution_source.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            tenant_identity=TenantIdentity.from_dict(data["tenant_identity"]),
            resolution_source=TenantResolutionSource.parse(data["resolution_source"]),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Immutable composite: an authenticated principal inside a resolved tenant.

    Composes an :class:`AuthenticationContext` and a :class:`TenantContext`.
    It stores only those two contexts and derives every other value on demand
    through read-only properties, so no nested value is duplicated as state.
    It makes no authorisation decision and performs no orchestration.
    """

    authentication_context: AuthenticationContext
    tenant_context: TenantContext

    def __post_init__(self) -> None:
        """Validate that both composed contexts have their canonical types."""
        if not isinstance(self.authentication_context, AuthenticationContext):
            raise TypeError(
                "authentication_context must be an AuthenticationContext"
            )
        if not isinstance(self.tenant_context, TenantContext):
            raise TypeError("tenant_context must be a TenantContext")
        if (
            self.authentication_context.session.tenant_identity.tenant_id
            != self.tenant_context.tenant_identity.tenant_id
        ):
            raise ValueError(
                "authentication session tenant must match resolved tenant"
            )

    @property
    def principal_identity(self) -> PrincipalIdentity:
        """The authenticated principal, reached through the session."""
        return self.authentication_context.session.principal_identity

    @property
    def session(self) -> SessionIdentity:
        """The authenticated session."""
        return self.authentication_context.session

    @property
    def access_plane(self) -> AccessPlane:
        """The access plane through which the request arrived."""
        return self.authentication_context.access_plane

    @property
    def tenant_identity(self) -> TenantIdentity:
        """The resolved tenant."""
        return self.tenant_context.tenant_identity

    @property
    def tenant_resolution_source(self) -> TenantResolutionSource:
        """The source from which the tenant was resolved."""
        return self.tenant_context.resolution_source

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary without flattening."""
        return {
            "authentication_context": self.authentication_context.to_dict(),
            "tenant_context": self.tenant_context.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            authentication_context=AuthenticationContext.from_dict(
                data["authentication_context"]
            ),
            tenant_context=TenantContext.from_dict(data["tenant_context"]),
        )


@dataclass(frozen=True, slots=True)
class PermissionCode:
    """Immutable canonical permission code.

    Holds a single dotted lowercase identifier such as ``gst.return.view``. It
    is a value only: it performs no catalogue membership, hierarchy, wildcard or
    normalisation, and it stores the supplied string verbatim after validation.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate that ``value`` is a plain str in canonical code syntax."""
        if type(self.value) is not str:
            raise TypeError("value must be a str")
        if re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*", self.value) is None:
            raise ValueError(f"invalid permission code: {self.value!r}")

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain JSON-safe dictionary."""
        return {"value": self.value}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(value=data["value"])


class AuthorizationOutcome(StrictStringEnum):
    """Outcome an evaluator returned for one authorization question.

    ``INDETERMINATE`` means the evaluator could not reliably return ``ALLOW`` or
    ``DENY``; it is never equivalent to ``ALLOW``. Classification only.
    """

    ALLOW = "allow"
    DENY = "deny"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """Immutable permission-evaluation question.

    Binds an :class:`AuthorizationContext`, a :class:`PermissionCode` and an
    :class:`AssignmentTarget`. Beyond type validation it enforces that the
    target's tenant matches the resolved tenant, completing the structural
    chain session tenant == resolved tenant == target tenant. It stores no
    derived state and makes no authorization decision.
    """

    authorization_context: AuthorizationContext
    permission_code: PermissionCode
    target: AssignmentTarget

    def __post_init__(self) -> None:
        """Validate composed types, then the target-tenant alignment rule."""
        if not isinstance(self.authorization_context, AuthorizationContext):
            raise TypeError(
                "authorization_context must be an AuthorizationContext"
            )
        if not isinstance(self.permission_code, PermissionCode):
            raise TypeError("permission_code must be a PermissionCode")
        if not isinstance(self.target, AssignmentTarget):
            raise TypeError("target must be an AssignmentTarget")
        if (
            self.authorization_context.tenant_identity.tenant_id
            != self.target.tenant_id
        ):
            raise ValueError(
                "authorization target tenant must match resolved tenant"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary (nested, not flattened)."""
        return {
            "authorization_context": self.authorization_context.to_dict(),
            "permission_code": self.permission_code.to_dict(),
            "target": self.target.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            authorization_context=AuthorizationContext.from_dict(
                data["authorization_context"]
            ),
            permission_code=PermissionCode.from_dict(data["permission_code"]),
            target=AssignmentTarget.from_dict(data["target"]),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Immutable pairing of an evaluated request with its outcome.

    Retains the complete :class:`AuthorizationRequest` it was decided for, bound
    to a single :class:`AuthorizationOutcome`. It copies no request field and
    carries no reason, policy, evidence or timestamp.
    """

    request: AuthorizationRequest
    outcome: AuthorizationOutcome

    def __post_init__(self) -> None:
        """Validate that the request and outcome have their canonical types."""
        if not isinstance(self.request, AuthorizationRequest):
            raise TypeError("request must be an AuthorizationRequest")
        if type(self.outcome) is not AuthorizationOutcome:
            raise TypeError("outcome must be an AuthorizationOutcome")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain JSON-safe dictionary."""
        return {
            "request": self.request.to_dict(),
            "outcome": self.outcome.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Reconstruct from a dictionary produced by :meth:`to_dict`."""
        return cls(
            request=AuthorizationRequest.from_dict(data["request"]),
            outcome=AuthorizationOutcome.parse(data["outcome"]),
        )


@runtime_checkable
class AuthorizationEvaluator(Protocol):
    """Boundary a future authorization evaluator implementation must satisfy.

    An implementation maps one structurally valid :class:`AuthorizationRequest`
    to one :class:`AuthorizationDecision` bound to that request. This is a
    protocol only; it performs no evaluation and holds no state.
    """

    def evaluate(
        self,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:
        """Evaluate one request and return its decision."""
        ...


@runtime_checkable
class TenantResolver(Protocol):
    """Boundary a future tenant resolver implementation must satisfy.

    An implementation maps already-extracted candidate references to a
    :class:`TenantResolutionResult`. Failure is reported through the result's
    failure contract, never by raising. This is a protocol only.
    """

    def resolve(
        self,
        resolution_input: TenantResolutionInput,
    ) -> TenantResolutionResult:
        """Resolve candidate references to a tenant resolution result."""
        ...
