"""Read-only insight endpoints: branding and dashboard aggregates.

Authorization:
- Branding: any authenticated internal principal.
- Employee dashboard: the authenticated caller's own dashboard (resolved
  server-side). Ordinary employees cannot request another employee's data;
  only firm leadership (ADMIN/PARTNER) may view another employee via
  ?employee_id=, otherwise 403.
- Executive dashboard: firm leadership only (ADMIN/PARTNER), else 403.

All endpoints are tenant-scoped and compute deterministic aggregates in the
backend.
"""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.authorization.permissions import (
    ClientAccessPermission,
    DocumentRequestAccessPermission,
    WorkItemAccessPermission,
)

from contexts.identity.access import (
    caller_identity_ids,
    can_view_firm_operations,
    employee_for_principal,
    identity_ids_for_employee,
    is_executive,
)
from core.api.request_context import HeaderPrincipalAuthentication

from . import queries
from .branding import resolve_brand


class _InsightView(APIView):
    authentication_classes = [HeaderPrincipalAuthentication]
    permission_classes = [IsAuthenticated]

    def principal(self):
        return self.request.user


class BrandingView(_InsightView):
    def get(self, request):
        principal = self.principal()
        data = resolve_brand(principal.tenant_id)
        # Backend-authorized capability flags for the frontend to consume.
        # The frontend must not invent authorization; it only reflects these.
        emp = employee_for_principal(principal.tenant_id, principal)
        data["capabilities"] = {
            # Firm leadership remains ADMIN/PARTNER only.
            "is_executive": is_executive(
                principal.tenant_id,
                principal,
            ),

            # Separate read-only operational scope consumed by Mission Control.
            "can_view_firm_operations": can_view_firm_operations(
                principal.tenant_id,
                principal,
            ),

            "role": emp.role if emp else None,
        }
        return Response(data)



class ClientWorkspaceView(_InsightView):
    """Read-only Client Workspace projection.

    Uses the existing Client, Work and Document read permissions rather than
    inventing a Client Workspace permission model.
    """

    # ActionAccessPermission classes consume this APIView action exactly as
    # their retrieve actions on the existing domain ViewSets.
    action = "retrieve"

    permission_classes = [
        IsAuthenticated,
        ClientAccessPermission,
        WorkItemAccessPermission,
        DocumentRequestAccessPermission,
    ]

    def get(self, request):
        principal = self.principal()
        tenant_id = principal.tenant_id
        client_id = request.query_params.get("client_id")

        if not client_id:
            return Response(
                {
                    "detail": "client_id is required.",
                },
                status=400,
            )

        data = queries.client_workspace(
            tenant_id,
            client_id,
        )

        if data is None:
            # Do not reveal a client from another tenant.
            return Response(
                {
                    "detail": "Client was not found.",
                },
                status=404,
            )

        return Response(data)

class EmployeeDashboardView(_InsightView):
    def get(self, request):
        principal = self.principal()
        tenant_id = principal.tenant_id
        requested = request.query_params.get("employee_id")

        # Resolve the caller's own identity server-side.
        ids, own_employee_id = caller_identity_ids(tenant_id, principal)

        if requested:
            # Viewing another employee requires firm leadership. Resolve the
            # target employee server-side so BOTH supported identity forms
            # (Employee.id and raw principal UUID) are included.
            if str(requested) != str(own_employee_id) and not is_executive(tenant_id, principal):
                raise PermissionDenied("You are not permitted to view another employee's dashboard.")
            target_ids, target_employee = identity_ids_for_employee(tenant_id, requested)
            if target_employee is None:
                raise PermissionDenied("The requested employee is unavailable in this tenant.")
            target_employee_id = target_employee.id
        else:
            # Own dashboard: use all canonical identity references for the caller.
            if not ids:
                raise PermissionDenied("No employee identity resolved for the caller.")
            target_ids = ids
            target_employee_id = own_employee_id

        period = request.query_params.get("period", "month")
        data = queries.employee_dashboard(tenant_id, target_ids, period, employee_id=target_employee_id)
        return Response(data)


class ExecutiveDashboardView(_InsightView):
    def get(self, request):
        principal = self.principal()
        tenant_id = principal.tenant_id
        if not can_view_firm_operations(
            tenant_id,
            principal,
        ):
            raise PermissionDenied(
                "Firm operational dashboard access is restricted."
            )
        period = request.query_params.get("period", "month")
        data = queries.executive_dashboard(tenant_id, period)
        return Response(data)


class ManagerDashboardView(_InsightView):
    """Team operational view. Manager-capability gated (manager/leadership)."""

    def get(self, request):
        principal = self.principal()
        tenant_id = principal.tenant_id
        from contexts.identity.access import caller_role

        role = caller_role(tenant_id, principal)
        if not (is_executive(tenant_id, principal) or role == "MANAGER"):
            raise PermissionDenied("Manager dashboard access is restricted to managers and leadership.")
        emp = employee_for_principal(tenant_id, principal)
        # Leadership may inspect any manager's team via ?manager_id=, else own.
        requested_manager = request.query_params.get("manager_id")
        if requested_manager and not is_executive(tenant_id, principal):
            raise PermissionDenied("Only leadership may view another manager's team.")
        manager_employee_id = requested_manager or (emp.id if emp else None)
        period = request.query_params.get("period", "month")
        return Response(queries.manager_dashboard(tenant_id, manager_employee_id, period))


class FirmCapacityDashboardView(_InsightView):
    """Firm-wide capacity view. Leadership only."""

    def get(self, request):
        principal = self.principal()
        tenant_id = principal.tenant_id
        if not is_executive(tenant_id, principal):
            raise PermissionDenied("Firm capacity dashboard access is restricted to firm leadership.")
        period = request.query_params.get("period", "month")
        return Response(queries.firm_capacity_dashboard(tenant_id, period))
