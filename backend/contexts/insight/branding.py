"""Central tenant-aware branding resolution.

Primary source is the tenant's FirmProfile.name; when absent, a controlled
fallback is used. This is the single source of truth for brand text so no
component hard-codes it.
"""

from __future__ import annotations

from contexts.organisation.models import FirmProfile

BRAND_FALLBACK = "Vridhi Consultants"


def resolve_brand(tenant_id) -> dict:
    profile = FirmProfile.objects.filter(tenant_id=tenant_id).order_by("created_at").first()
    name = (profile.name.strip() if profile and profile.name and profile.name.strip() else "") or BRAND_FALLBACK
    legal = (profile.legal_name.strip() if profile and profile.legal_name else "") or name
    return {
        "firm_name": name,
        "legal_name": legal,
        "source": "firm_profile" if profile and profile.name.strip() else "fallback",
    }
