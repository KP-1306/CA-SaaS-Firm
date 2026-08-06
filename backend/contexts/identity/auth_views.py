from __future__ import annotations

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import exceptions, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth_service import (
    COOKIE_NAME,
    VridhiSessionAuthentication,
    authenticate_credentials,
    revoke_session,
)
from .models import AuthSession, ProviderMembership, UserAccount


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class VridhiLoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf_token": get_token(request)})

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account, membership, session, raw_token = authenticate_credentials(
            request=request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        response = Response(
            {
                "account": {
                    "id": str(account.id),
                    "email": account.email,
                    "display_name": account.display_name,
                    "email_verified": account.email_verified_at is not None,
                },
                "membership": {
                    "id": str(membership.id),
                    "tenant_id": str(membership.tenant_id),
                    "role": membership.role,
                    "status": membership.status,
                },
                "session": {"id": str(session.id), "expires_at": session.expires_at},
            }
        )
        response.set_cookie(
            COOKIE_NAME,
            raw_token,
            max_age=settings.VRIDHI_SESSION_AGE_SECONDS,
            httponly=True,
            secure=settings.VRIDHI_AUTH_COOKIE_SECURE,
            samesite="Strict",
            path="/",
        )
        return response


class VridhiLogoutView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session = request.auth
        if not isinstance(session, AuthSession):
            raise exceptions.AuthenticationFailed("A Vridhi session is required.")
        revoke_session(request=request, session=session)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(COOKIE_NAME, path="/", samesite="Strict")
        return response


class VridhiMeView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account: UserAccount = request.vridhi_account
        membership: ProviderMembership = request.vridhi_membership
        return Response(
            {
                "account": {
                    "id": str(account.id),
                    "email": account.email,
                    "display_name": account.display_name,
                    "status": account.status,
                    "email_verified": account.email_verified_at is not None,
                    "last_login_at": account.last_login_at,
                },
                "membership": {
                    "id": str(membership.id),
                    "tenant_id": str(membership.tenant_id),
                    "employee_id": str(membership.employee_id) if membership.employee_id else None,
                    "role": membership.role,
                    "status": membership.status,
                },
            }
        )


class VridhiSessionsView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        current: AuthSession = request.auth
        rows = AuthSession.objects.filter(
            user_account_id=current.user_account_id,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        return Response(
            [
                {
                    "id": str(row.id),
                    "created_at": row.created_at,
                    "last_seen_at": row.last_seen_at,
                    "expires_at": row.expires_at,
                    "current": row.id == current.id,
                }
                for row in rows
            ]
        )

    def delete(self, request):
        current: AuthSession = request.auth
        session_id = request.data.get("session_id")
        if not session_id:
            raise serializers.ValidationError({"session_id": "This field is required."})
        target = AuthSession.objects.filter(
            id=session_id,
            user_account_id=current.user_account_id,
        ).first()
        if target is None:
            raise exceptions.NotFound("Session not found.")
        revoke_session(request=request, session=target, reason="USER_REVOKED")
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        min_length=12,
    )

    def validate_new_password(self, value):
        if not any(character.islower() for character in value):
            raise serializers.ValidationError("Include a lowercase letter.")
        if not any(character.isupper() for character in value):
            raise serializers.ValidationError("Include an uppercase letter.")
        if not any(character.isdigit() for character in value):
            raise serializers.ValidationError("Include a number.")
        if value.isalnum():
            raise serializers.ValidationError("Include a symbol.")
        return value


class VridhiPasswordChangeView(APIView):
    authentication_classes = [VridhiSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.db import transaction

        from .auth_service import record_auth_event, revoke_session
        from .models import (
            AuthenticationEventType,
            AuthenticationOutcome,
        )

        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account: UserAccount = request.vridhi_account
        membership: ProviderMembership = request.vridhi_membership
        current_session: AuthSession = request.auth

        if not account.check_password(
            serializer.validated_data["current_password"]
        ):
            record_auth_event(
                request=request,
                event_type=AuthenticationEventType.ACCESS_DENIED,
                outcome=AuthenticationOutcome.DENIED,
                account=account,
                membership=membership,
                session=current_session,
                reason="PASSWORD_CHANGE_CURRENT_PASSWORD_INVALID",
            )
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )

        with transaction.atomic():
            account.set_password(serializer.validated_data["new_password"])
            account.must_change_password = False
            account.failed_login_count = 0
            account.locked_until = None
            account.save(
                update_fields=[
                    "password_hash",
                    "password_changed_at",
                    "must_change_password",
                    "failed_login_count",
                    "locked_until",
                    "updated_at",
                ]
            )

            for session in AuthSession.objects.filter(
                user_account_id=account.id,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).exclude(id=current_session.id):
                revoke_session(
                    request=request,
                    session=session,
                    reason="PASSWORD_CHANGED_OTHER_SESSION",
                )

            record_auth_event(
                request=request,
                event_type=AuthenticationEventType.PASSWORD_CHANGED,
                outcome=AuthenticationOutcome.SUCCESS,
                account=account,
                membership=membership,
                session=current_session,
                reason="SELF_SERVICE_PASSWORD_CHANGE",
            )

        return Response(
            {
                "password_changed": True,
                "must_change_password": False,
            }
        )
