from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.authorization.admin_service import (
    clone_role,
    create_role,
    get_role_for_tenant,
    list_roles,
    save_access_profile,
    serialize_profile,
    update_role,
)
from contexts.authorization.models import Access
from contexts.authorization.serializers import (
    AccessProfileWriteSerializer,
    RoleCloneSerializer,
    RoleUpdateSerializer,
    RoleWriteSerializer,
    serialize_access,
    serialize_role,
)
from contexts.authorization.services import sync_system_access_catalogue
from contexts.identity.auth_service import VridhiSessionAuthentication
from contexts.identity.consultant_admin_service import require_provider_admin


class AuthorizationAdminBaseView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_provider_admin(request)


class RoleCollectionView(AuthorizationAdminBaseView):
    def get(self, request):
        return Response(
            [serialize_role(role) for role in list_roles(request)]
        )

    def post(self, request):
        sync_system_access_catalogue()
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = create_role(
            request=request,
            **serializer.validated_data,
        )

        return Response(
            serialize_role(role),
            status=status.HTTP_201_CREATED,
        )


class RoleDetailView(AuthorizationAdminBaseView):
    def get(self, request, role_id):
        return Response(
            serialize_role(
                get_role_for_tenant(
                    request=request,
                    role_id=role_id,
                )
            )
        )

    def patch(self, request, role_id):
        serializer = RoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = update_role(
            request=request,
            role=get_role_for_tenant(
                request=request,
                role_id=role_id,
            ),
            values=serializer.validated_data,
        )

        role.refresh_from_db()
        return Response(serialize_role(role))


class RoleCloneView(AuthorizationAdminBaseView):
    def post(self, request, role_id):
        serializer = RoleCloneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = clone_role(
            request=request,
            source=get_role_for_tenant(
                request=request,
                role_id=role_id,
            ),
            **serializer.validated_data,
        )

        return Response(
            serialize_role(role),
            status=status.HTTP_201_CREATED,
        )


class AccessCatalogueView(AuthorizationAdminBaseView):
    def get(self, request):
        sync_system_access_catalogue()

        rows = Access.objects.filter(
            is_active=True,
        ).order_by("module", "name")

        return Response([serialize_access(row) for row in rows])


class UserAccessProfileView(AuthorizationAdminBaseView):
    def get(self, request, account_id):
        membership = require_provider_admin(request)
        return Response(
            serialize_profile(
                tenant_id=membership.tenant_id,
                account_id=account_id,
            )
        )

    def put(self, request, account_id):
        serializer = AccessProfileWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        membership = require_provider_admin(request)

        save_access_profile(
            request=request,
            account_id=account_id,
            values=serializer.validated_data,
        )

        return Response(
            serialize_profile(
                tenant_id=membership.tenant_id,
                account_id=account_id,
            )
        )
