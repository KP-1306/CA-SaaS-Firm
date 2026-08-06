from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth_service import VridhiSessionAuthentication
from .consultant_admin_service import (
    change_consultant_role,
    create_consultant,
    link_employee,
    require_provider_admin,
    reset_consultant_password,
    revoke_all_consultant_sessions,
    serialize_consultant,
    set_consultant_status,
    unlock_consultant,
)
from .models import (
    AuthenticationEvent,
    AuthSession,
    MembershipStatus,
    ProviderMembership,
    ProviderRole,
    UserAccount,
    UserAccountStatus,
)


class ConsultantCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    display_name = serializers.CharField(max_length=180)
    role = serializers.ChoiceField(choices=ProviderRole.choices)
    employee_id = serializers.UUIDField(required=False, allow_null=True)


class ConsultantStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=UserAccountStatus.choices)
    reason = serializers.CharField(max_length=200)


class ConsultantRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ProviderRole.choices)
    reason = serializers.CharField(max_length=200)


class EmployeeLinkSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()


class ConsultantAdminBaseView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_provider_admin(request)

    @staticmethod
    def resolve(account_id):
        account = UserAccount.objects.filter(id=account_id).first()
        if account is None:
            raise exceptions.NotFound("Consultant account not found.")
        membership = ProviderMembership.objects.filter(
            tenant_id=settings.VRIDHI_PROVIDER_TENANT_ID,
            user_account_id=account.id,
        ).order_by("-created_at").first()
        if membership is None:
            raise exceptions.NotFound("Provider membership not found.")
        return account, membership


class ConsultantCollectionView(ConsultantAdminBaseView):
    def get(self, request):
        rows = UserAccount.objects.all()
        query = request.query_params.get("q", "").strip()
        status_filter = request.query_params.get("status", "").strip()
        role_filter = request.query_params.get("role", "").strip()
        locked = request.query_params.get("locked", "").strip().lower()

        if query:
            rows = rows.filter(
                models.Q(email__icontains=query)
                | models.Q(display_name__icontains=query)
            )
        if status_filter:
            rows = rows.filter(status=status_filter)

        memberships = ProviderMembership.objects.filter(
            tenant_id=settings.VRIDHI_PROVIDER_TENANT_ID,
            user_account_id__in=rows.values_list("id", flat=True),
        )
        if role_filter:
            memberships = memberships.filter(role=role_filter)

        membership_map = {
            row.user_account_id: row
            for row in memberships.order_by("-created_at")
        }

        result = []
        now = timezone.now()
        for account in rows.order_by("display_name", "email"):
            membership = membership_map.get(account.id)
            if membership is None:
                continue
            if locked == "true" and not (
                account.locked_until and account.locked_until > now
            ):
                continue
            if locked == "false" and (
                account.locked_until and account.locked_until > now
            ):
                continue
            result.append(serialize_consultant(account, membership))
        return Response(result)

    def post(self, request):
        serializer = ConsultantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account, membership, temporary_password = create_consultant(
            request=request,
            **serializer.validated_data,
        )
        return Response(
            {
                "consultant": serialize_consultant(account, membership),
                "temporary_password": temporary_password,
                "temporary_password_disclosed_once": True,
            },
            status=status.HTTP_201_CREATED,
        )


class ConsultantDetailView(ConsultantAdminBaseView):
    def get(self, request, account_id):
        account, membership = self.resolve(account_id)
        return Response(serialize_consultant(account, membership))


class ConsultantStatusView(ConsultantAdminBaseView):
    def post(self, request, account_id):
        account, membership = self.resolve(account_id)
        serializer = ConsultantStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_consultant_status(
            request=request,
            account=account,
            membership=membership,
            status_value=serializer.validated_data["status"],
            reason=serializer.validated_data["reason"],
        )
        account.refresh_from_db()
        membership.refresh_from_db()
        return Response(serialize_consultant(account, membership))


class ConsultantRoleView(ConsultantAdminBaseView):
    def post(self, request, account_id):
        account, membership = self.resolve(account_id)
        serializer = ConsultantRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_consultant_role(
            request=request,
            account=account,
            membership=membership,
            **serializer.validated_data,
        )
        membership.refresh_from_db()
        return Response(serialize_consultant(account, membership))


class ConsultantEmployeeLinkView(ConsultantAdminBaseView):
    def post(self, request, account_id):
        account, membership = self.resolve(account_id)
        serializer = EmployeeLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link_employee(
            request=request,
            account=account,
            membership=membership,
            employee_id=str(serializer.validated_data["employee_id"]),
        )
        membership.refresh_from_db()
        return Response(serialize_consultant(account, membership))


class ConsultantPasswordResetView(ConsultantAdminBaseView):
    def post(self, request, account_id):
        account, membership = self.resolve(account_id)
        temporary_password = reset_consultant_password(
            request=request,
            account=account,
            membership=membership,
        )
        return Response(
            {
                "temporary_password": temporary_password,
                "temporary_password_disclosed_once": True,
                "must_change_password": True,
            }
        )


class ConsultantUnlockView(ConsultantAdminBaseView):
    def post(self, request, account_id):
        account, membership = self.resolve(account_id)
        unlock_consultant(
            request=request,
            account=account,
            membership=membership,
        )
        account.refresh_from_db()
        return Response(serialize_consultant(account, membership))


class ConsultantSessionsView(ConsultantAdminBaseView):
    def get(self, request, account_id):
        account, _ = self.resolve(account_id)
        sessions = AuthSession.objects.filter(
            user_account_id=account.id,
        ).order_by("-created_at")
        return Response(
            [
                {
                    "id": str(row.id),
                    "created_at": row.created_at,
                    "last_seen_at": row.last_seen_at,
                    "expires_at": row.expires_at,
                    "revoked_at": row.revoked_at,
                    "ip_address": row.ip_address,
                    "active": row.is_active,
                }
                for row in sessions
            ]
        )

    def delete(self, request, account_id):
        account, _ = self.resolve(account_id)
        count = revoke_all_consultant_sessions(
            request=request,
            account=account,
        )
        return Response({"revoked_sessions": count})


class ConsultantAuditView(ConsultantAdminBaseView):
    def get(self, request, account_id):
        account, _ = self.resolve(account_id)
        rows = AuthenticationEvent.objects.filter(
            user_account_id=account.id,
        ).order_by("-occurred_at")[:200]
        return Response(
            [
                {
                    "id": str(row.id),
                    "occurred_at": row.occurred_at,
                    "event_type": row.event_type,
                    "outcome": row.outcome,
                    "reason": row.reason,
                    "principal_id": (
                        str(row.principal_id)
                        if row.principal_id
                        else None
                    ),
                    "session_id": (
                        str(row.session_id)
                        if row.session_id
                        else None
                    ),
                    "ip_address": row.ip_address,
                    "user_agent": row.user_agent,
                    "metadata": row.metadata,
                }
                for row in rows
            ]
        )
