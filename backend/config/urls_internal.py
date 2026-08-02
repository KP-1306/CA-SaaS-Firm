from __future__ import annotations

from django.urls import URLPattern, URLResolver, include, path
from rest_framework.routers import DefaultRouter

from contexts.clients.views import ClientBranchViewSet, ClientContactViewSet, ClientGSTRegistrationViewSet, ClientViewSet
from contexts.configuration.views import DomainViewSet, ServiceViewSet, VerticalViewSet
from contexts.identity.views import EmployeeExpertiseViewSet, EmployeeViewSet
from contexts.work.views import (
    DocumentAttachmentViewSet,
    DocumentRequestViewSet,
    WorkItemViewSet,
    WorkNoteViewSet,
)
from contexts.organisation.views import BranchViewSet, FirmProfileViewSet, TeamViewSet
from contexts.audit.views import AuditEventViewSet
from contexts.generation.views import (
    ClientServiceSubscriptionViewSet,
    GeneratedWorkLedgerViewSet,
    RecurringWorkProfileViewSet,
    TaskTemplateViewSet,
)
from contexts.insight.views import BrandingView, EmployeeDashboardView, ExecutiveDashboardView
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
router.register("work-items", WorkItemViewSet, basename="work-item")
router.register("work-notes", WorkNoteViewSet, basename="work-note")
router.register("document-requests", DocumentRequestViewSet, basename="document-request")
router.register("document-attachments", DocumentAttachmentViewSet, basename="document-attachment")
router.register("audit-events", AuditEventViewSet, basename="audit-event")
router.register("client-service-subscriptions", ClientServiceSubscriptionViewSet, basename="client-service-subscription")
router.register("task-templates", TaskTemplateViewSet, basename="task-template")
router.register("recurring-work-profiles", RecurringWorkProfileViewSet, basename="recurring-work-profile")
router.register("generated-work-ledger", GeneratedWorkLedgerViewSet, basename="generated-work-ledger")

urlpatterns: list[URLPattern | URLResolver] = [
    path("", bootstrap, name="bootstrap"),
    path("branding/", BrandingView.as_view(), name="branding"),
    path("dashboard/employee/", EmployeeDashboardView.as_view(), name="dashboard-employee"),
    path("dashboard/executive/", ExecutiveDashboardView.as_view(), name="dashboard-executive"),
    path("", include(router.urls)),
]
