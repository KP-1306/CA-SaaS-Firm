from __future__ import annotations

from rest_framework import serializers

from contexts.authorization.models import Access, RoleTemplate


class RoleWriteSerializer(serializers.Serializer):
    code = serializers.RegexField(
        regex=r"^[A-Z][A-Z0-9_]*$",
        max_length=50,
    )
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    access_codes = serializers.ListField(
        child=serializers.CharField(max_length=150),
        required=False,
        default=list,
    )


class RoleUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    access_codes = serializers.ListField(
        child=serializers.CharField(max_length=150),
        required=False,
    )
    is_active = serializers.BooleanField(required=False)


class RoleCloneSerializer(serializers.Serializer):
    code = serializers.RegexField(
        regex=r"^[A-Z][A-Z0-9_]*$",
        max_length=50,
    )
    name = serializers.CharField(max_length=100)


class AccessProfileWriteSerializer(serializers.Serializer):
    role_id = serializers.IntegerField(required=False, allow_null=True)
    additional_access_codes = serializers.ListField(
        child=serializers.CharField(max_length=150),
        required=False,
        default=list,
    )
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    team_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    service_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    is_active = serializers.BooleanField(required=False, default=True)


def serialize_access(access: Access) -> dict:
    return {
        "id": access.id,
        "module": access.module,
        "code": access.code,
        "name": access.name,
        "description": access.description,
        "is_active": access.is_active,
    }


def serialize_role(role: RoleTemplate) -> dict:
    mappings = role.role_access.select_related("access").order_by(
        "access__module",
        "access__name",
    )

    return {
        "id": role.id,
        "tenant_id": str(role.tenant_id) if role.tenant_id else None,
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "access": [
            serialize_access(mapping.access)
            for mapping in mappings
            if mapping.access.is_active
        ],
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }
