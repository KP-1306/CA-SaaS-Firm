from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path
from rest_framework.routers import DefaultRouter

from contexts.clients.views import ClientBranchViewSet, ClientContactViewSet, ClientGSTRegistrationViewSet, ClientViewSet
from contexts.configuration.views import (
    DomainViewSet,
    ServiceDocumentRequirementSetViewSet,
    ServiceDocumentRequirementViewSet,
    ServiceViewSet,
    VerticalViewSet,
    ServiceOperationalFieldViewSet,
)
from contexts.identity.views import EmployeeExpertiseViewSet, EmployeeViewSet
from contexts.identity.auth_views import (
    VridhiLoginView,
    VridhiLogoutView,
    VridhiMeView,
    VridhiPasswordChangeView,
    VridhiSessionsView,
)
from contexts.identity.consultant_admin_views import (
    ConsultantAuditView,
    ConsultantCollectionView,
    ConsultantDetailView,
    ConsultantEmployeeLinkView,
    ConsultantPasswordResetView,
    ConsultantRoleView,
    ConsultantSessionsView,
    ConsultantStatusView,
    ConsultantUnlockView,
)
from contexts.work.views import (
    DocumentAttachmentViewSet,
    DocumentRequestViewSet,
    WorkItemViewSet,
    WorkNoteViewSet,
)
from contexts.organisation.views import (
    BranchViewSet,
    DepartmentViewSet,
    DesignationViewSet,
    FirmProfileViewSet,
    ReportingRelationshipViewSet,
    TeamMembershipViewSet,
    TeamViewSet,
)
from contexts.audit.views import AuditEventViewSet
from contexts.generation.views import (
    ClientServiceSubscriptionViewSet,
    GeneratedWorkLedgerViewSet,
    RecurringWorkProfileViewSet,
    TaskTemplateViewSet,
)
from contexts.capacity.views import (
    CapacityOverrideViewSet,
    CapacityProfileViewSet,
    CapacityReservationViewSet,
    HolidayViewSet,
    LeaveRecordViewSet,
    LeaveTypeViewSet,
)
from contexts.assignment.views import (
    AssignmentDecisionViewSet,
    AssignmentEventViewSet,
    AssignmentRecommendationViewSet,
    ReviewerRuleViewSet,
)
from contexts.identity.views import SkillCatalogueViewSet
from contexts.quality.views import (
    QAReviewCycleViewSet,
    QAReviewIssueViewSet,
    QAReviewResponseViewSet,
    ServiceQAChecklistItemViewSet,
    ServiceQAChecklistSetViewSet,
)
from contexts.insight.views import (
    BrandingView,
    EmployeeDashboardView,
    ExecutiveDashboardView,
    FirmCapacityDashboardView,
    ManagerDashboardView,
)
from .bootstrap_internal import bootstrap

app_name = "internal"
router = DefaultRouter()
router.register("firm", FirmProfileViewSet, basename="firm")
router.register("branches", BranchViewSet, basename="branch")
router.register("teams", TeamViewSet, basename="team")
router.register("employees", EmployeeViewSet, basename="employee")
router.register("employee-expertise", EmployeeExpertiseViewSet, basename="employee-expertise")
router.register("clients", ClientViewSet, basename="client")
router.register("client-contacts", ClientContactViewSet, basename="client-contact")
router.register("client-gst-registrations", ClientGSTRegistrationViewSet, basename="client-gst-registration")
router.register("client-branches", ClientBranchViewSet, basename="client-branch")
router.register("verticals", VerticalViewSet, basename="vertical")
router.register("domains", DomainViewSet, basename="domain")
router.register("services", ServiceViewSet, basename="service")
router.register(
    "service-operational-fields",
    ServiceOperationalFieldViewSet,
    basename="service-operational-field",
)
router.register(
    "service-document-requirement-sets",
    ServiceDocumentRequirementSetViewSet,
    basename="service-document-requirement-set",
)
router.register(
    "service-document-requirements",
    ServiceDocumentRequirementViewSet,
    basename="service-document-requirement",
)
router.register("work-items", WorkItemViewSet, basename="work-item")
router.register("work-notes", WorkNoteViewSet, basename="work-note")
router.register("document-requests", DocumentRequestViewSet, basename="document-request")
router.register("document-attachments", DocumentAttachmentViewSet, basename="document-attachment")
router.register("audit-events", AuditEventViewSet, basename="audit-event")
router.register("client-service-subscriptions", ClientServiceSubscriptionViewSet, basename="client-service-subscription")
router.register("task-templates", TaskTemplateViewSet, basename="task-template")
router.register("recurring-work-profiles", RecurringWorkProfileViewSet, basename="recurring-work-profile")
router.register("generated-work-ledger", GeneratedWorkLedgerViewSet, basename="generated-work-ledger")
# --- Employee Operations V1 (additive) ---
router.register("departments", DepartmentViewSet, basename="department")
router.register("designations", DesignationViewSet, basename="designation")
router.register("team-memberships", TeamMembershipViewSet, basename="team-membership")
router.register("reporting-relationships", ReportingRelationshipViewSet, basename="reporting-relationship")
router.register("skill-catalogue", SkillCatalogueViewSet, basename="skill-catalogue")
router.register("capacity-profiles", CapacityProfileViewSet, basename="capacity-profile")
router.register("capacity-overrides", CapacityOverrideViewSet, basename="capacity-override")
router.register("capacity-reservations", CapacityReservationViewSet, basename="capacity-reservation")
router.register("leave-types", LeaveTypeViewSet, basename="leave-type")
router.register("leave-records", LeaveRecordViewSet, basename="leave-record")
router.register("holidays", HolidayViewSet, basename="holiday")
router.register("reviewer-rules", ReviewerRuleViewSet, basename="reviewer-rule")
router.register("assignment-decisions", AssignmentDecisionViewSet, basename="assignment-decision")
router.register("assignment-events", AssignmentEventViewSet, basename="assignment-event")
router.register("assignment-recommendations", AssignmentRecommendationViewSet, basename="assignment-recommendation")
router.register(
    "service-qa-checklist-sets",
    ServiceQAChecklistSetViewSet,
    basename="service-qa-checklist-set",
)
router.register(
    "service-qa-checklist-items",
    ServiceQAChecklistItemViewSet,
    basename="service-qa-checklist-item",
)
router.register("qa-review-cycles", QAReviewCycleViewSet, basename="qa-review-cycle")
router.register("qa-review-responses", QAReviewResponseViewSet, basename="qa-review-response")
router.register("qa-review-issues", QAReviewIssueViewSet, basename="qa-review-issue")

urlpatterns: list[URLPattern | URLResolver] = [
    path("auth/login/", VridhiLoginView.as_view(), name="vridhi-login"),
    path("auth/logout/", VridhiLogoutView.as_view(), name="vridhi-logout"),
    path("auth/me/", VridhiMeView.as_view(), name="vridhi-me"),
    path("auth/password-change/", VridhiPasswordChangeView.as_view(), name="vridhi-password-change"),
    path("auth/sessions/", VridhiSessionsView.as_view(), name="vridhi-sessions"),
    path("authorization/", include("contexts.authorization.urls")),
    path("identity/consultants/", ConsultantCollectionView.as_view(), name="consultant-list"),
    path("identity/consultants/<uuid:account_id>/", ConsultantDetailView.as_view(), name="consultant-detail"),
    path("identity/consultants/<uuid:account_id>/status/", ConsultantStatusView.as_view(), name="consultant-status"),
    path("identity/consultants/<uuid:account_id>/role/", ConsultantRoleView.as_view(), name="consultant-role"),
    path("identity/consultants/<uuid:account_id>/employee-link/", ConsultantEmployeeLinkView.as_view(), name="consultant-employee-link"),
    path("identity/consultants/<uuid:account_id>/password-reset/", ConsultantPasswordResetView.as_view(), name="consultant-password-reset"),
    path("identity/consultants/<uuid:account_id>/unlock/", ConsultantUnlockView.as_view(), name="consultant-unlock"),
    path("identity/consultants/<uuid:account_id>/sessions/", ConsultantSessionsView.as_view(), name="consultant-admin-sessions"),
    path("identity/consultants/<uuid:account_id>/audit/", ConsultantAuditView.as_view(), name="consultant-auth-audit"),
    path("", bootstrap, name="bootstrap"),
    path("branding/", BrandingView.as_view(), name="branding"),
    path("dashboard/employee/", EmployeeDashboardView.as_view(), name="dashboard-employee"),
    path("dashboard/executive/", ExecutiveDashboardView.as_view(), name="dashboard-executive"),
    path("dashboard/manager/", ManagerDashboardView.as_view(), name="dashboard-manager"),
    path("dashboard/firm-capacity/", FirmCapacityDashboardView.as_view(), name="dashboard-firm-capacity"),
    path("", include(router.urls)),
]
