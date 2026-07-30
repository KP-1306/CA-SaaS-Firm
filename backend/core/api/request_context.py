from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from rest_framework import authentication, exceptions


@dataclass(frozen=True, slots=True)
class InternalPrincipal:
    principal_id: uuid.UUID
    tenant_id: uuid.UUID
    is_authenticated: bool = True


class HeaderPrincipalAuthentication(authentication.BaseAuthentication):
    """Temporary internal-plane adapter until session authentication is wired."""

    def authenticate(self, request: Any) -> tuple[InternalPrincipal, None]:
        tenant = request.headers.get("X-Tenant-ID")
        principal = request.headers.get("X-Principal-ID")
        if not tenant or not principal:
            raise exceptions.AuthenticationFailed(
                "X-Tenant-ID and X-Principal-ID headers are required."
            )
        try:
            identity = InternalPrincipal(uuid.UUID(principal), uuid.UUID(tenant))
        except ValueError as exc:
            raise exceptions.AuthenticationFailed("Invalid tenant or principal UUID.") from exc
        return identity, None
