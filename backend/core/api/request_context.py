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

    def authenticate(self, request: Any):
        from contexts.identity.auth_service import VridhiSessionAuthentication

        session_result = VridhiSessionAuthentication().authenticate(request)
        if session_result is not None:
            return session_result

        from django.conf import settings

        tenant = request.headers.get("X-Tenant-ID")
        principal = request.headers.get("X-Principal-ID")
        if not tenant and not principal:
            return None
        if not settings.ALLOW_HEADER_PRINCIPAL_AUTH:
            raise exceptions.AuthenticationFailed(
                "Header principal authentication is disabled."
            )
        if not tenant or not principal:
            raise exceptions.AuthenticationFailed(
                "X-Tenant-ID and X-Principal-ID must be supplied together."
            )
        try:
            identity = InternalPrincipal(uuid.UUID(principal), uuid.UUID(tenant))
        except ValueError as exc:
            raise exceptions.AuthenticationFailed("Invalid tenant or principal UUID.") from exc
        return identity, None
