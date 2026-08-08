import type { HelpEntry } from "./types";

export const helpRegistry: Record<string, HelpEntry> = {

  "page.dashboard": {
    id: "page.dashboard",
    title: "Dashboard",
    summary: "Your starting point for understanding the firm's current operational position and what needs attention.",
    purpose: "Use the Dashboard to quickly review workload, deadlines, pending client actions, review requirements and overall work health before deciding where to focus.",
    whoUses: "Partners, Managers and Employees",
    whoCanView: "Authorized users see information within their permitted operational scope.",
    whoCanEdit: "The Dashboard is not edited directly. Its information is calculated from operational records.",
    workflowImpact: "Dashboard counts and indicators update automatically as work is assigned, progressed, reviewed, completed or becomes overdue.",
    examples: [
      "Review work that is due or overdue",
      "Identify items waiting for client documents",
      "Check work currently awaiting review",
      "Open an important work item directly from the operational view"
    ],
    commonMistakes: [
      "Treating Dashboard figures as manually maintained data",
      "Ignoring overdue or client-dependent work shown as requiring attention",
      "Using the Dashboard as a replacement for updating the underlying Work item"
    ],
    related: ["page.action-centre", "page.work", "page.work.workspace"]
  },

  "page.work.workspace": {
    id: "page.work.workspace",
    title: "Work Workspace",
    summary: "Central place where work items are executed.",
    purpose: "Track, update and complete operational work.",
    whoUses: "Assigned Owner, Reviewer, Leadership",
    whoCanView: "Authorized users",
    whoCanEdit: "Current Controller",
    related: ["page.client.workspace"]
  }
,

  "section.dashboard.my-work-today": {
    id: "section.dashboard.my-work-today",
    title: "My Work Today",
    summary: "Shows the current operational workload that needs your attention.",
    purpose: "Helps you quickly understand assigned work, deadlines, client dependencies, review requirements and recently completed work.",
    whoUses: "Employees, Managers, Partners",
    whoCanView: "Authorized users see information permitted for their role.",
    whoCanEdit: "This section is not edited directly. Work changes are made from the relevant Work Workspace.",
    workflowImpact: "The counts change automatically as work progresses through its operational workflow.",
    related: ["page.dashboard", "page.work.workspace"]
  },

  "section.dashboard.immediate-actions": {
    id: "section.dashboard.immediate-actions",
    title: "Immediate Actions",
    summary: "Prioritizes work items that currently require operational attention.",
    purpose: "Surfaces overdue, due-soon, client-dependent, review and rework items so important work is acted on first.",
    whoUses: "Employees, Managers, Partners",
    whoCanView: "Authorized users see actions available within their operational scope.",
    whoCanEdit: "This section is not edited directly. Actions are completed from the relevant Work Workspace.",
    workflowImpact: "Items move in or out automatically as work health, deadlines, ownership and workflow status change.",
    related: ["page.dashboard", "section.dashboard.my-work-today", "page.work.workspace"]
  },
  "page.action-centre": {
    id: "page.action-centre",
    title: "Action Centre",
    summary: "A prioritized view of work that needs action now rather than a general list of everything in progress.",
    purpose: "Use the Action Centre to focus first on overdue work, approaching deadlines, client dependencies, pending reviews and rework that could delay delivery.",
    whoUses: "Employees, Managers and Partners",
    whoCanView: "Authorized users see actionable items within their permitted operational scope.",
    whoCanEdit: "The Action Centre itself is not edited. Open the underlying Work Workspace to perform the required action.",
    workflowImpact: "Items enter or leave the Action Centre automatically when deadlines, dependencies, ownership, review status or work health change.",
    examples: [
      "Follow up on work waiting for client documents",
      "Open an overdue task and update its progress",
      "Pick up an item waiting for review",
      "Resolve rework returned by a reviewer"
    ],
    commonMistakes: [
      "Treating every open work item as equally urgent",
      "Ignoring client-dependent work because internal processing cannot continue yet",
      "Trying to update an Action Centre card instead of opening the underlying Work Workspace"
    ],
    related: ["page.dashboard", "page.work", "page.work.workspace"]
  },

  "page.my-dashboard": {
    id: "page.my-dashboard",
    title: "My Dashboard",
    summary: "Provides a personal view of your assigned workload and operational performance.",
    purpose: "Helps employees understand their own work, deadlines, dependencies and completion activity.",
    whoUses: "Employees and authorized leadership users",
    whoCanView: "Authorized users.",
    whoCanEdit: "Dashboard information is calculated from operational records."
  },

  "page.firm-overview": {
    id: "page.firm-overview",
    title: "Firm Overview",
    summary: "Provides leadership with a consolidated operational view across the firm.",
    purpose: "Helps management identify workload, risk, client health and operational bottlenecks.",
    whoUses: "Partners, Managers and authorized leadership",
    whoCanView: "Users with firm-level operational access.",
    whoCanEdit: "Not edited directly."
  },

  "page.clients": {
    id: "page.clients",
    title: "Clients",
    summary: "The central record of every client the firm serves, connecting client information with services, contacts and operational work.",
    purpose: "Use Clients to create and maintain client records, review engagement status, open the Client Workspace and move directly into the work being performed for that client.",
    whoUses: "Partners, Managers and authorized firm users",
    whoCanView: "Users see clients permitted by their client-access and operational scope.",
    whoCanEdit: "Users with client-management permission can create and update client records.",
    workflowImpact: "Client information is used throughout Vridhi when creating work, managing services, tracking documents and reporting on client activity.",
    examples: [
      "Onboard a new company or individual client",
      "Update PAN, GSTIN, contact or engagement information",
      "Open a Client Workspace to review active work",
      "Move a client through prospect, active, suspended or closed lifecycle stages"
    ],
    commonMistakes: [
      "Creating a duplicate client instead of checking the existing client list first",
      "Entering incomplete statutory identifiers such as PAN or GSTIN",
      "Changing lifecycle status without recording the relevant reason or date",
      "Creating operational work without linking it to the correct client"
    ],
    related: ["page.work", "page.servicing", "page.dashboard"]
  },

  "page.work": {
    id: "page.work",
    title: "Work",
    summary: "The operational heart of Vridhi, where client assignments are tracked from creation through execution, review and completion.",
    purpose: "Use Work to create and manage client tasks, assign responsibility, monitor deadlines, update workflow status, manage documents and complete deliverables.",
    whoUses: "Employees, Reviewers, Managers and Partners",
    whoCanView: "Users see work items allowed by their role, ownership and operational access.",
    whoCanEdit: "Editing is controlled by ownership, current controller, workflow stage and authorization rules.",
    workflowImpact: "Updates to Work drive dashboards, Action Centre priorities, employee workload, review queues, document requirements, client progress and reporting.",
    examples: [
      "Manage a GST return or TDS filing",
      "Track an income-tax return from preparation through review",
      "Assign an audit or compliance task to the responsible employee",
      "Record client-document dependencies and follow-up",
      "Complete review and close a finished engagement"
    ],
    commonMistakes: [
      "Creating duplicate work for the same client, service and period",
      "Assigning the wrong owner or reviewer",
      "Changing status without completing the required workflow step",
      "Closing work before required documents or review are complete",
      "Ignoring due dates or client dependencies until the item becomes overdue"
    ],
    related: ["page.clients", "page.action-centre", "page.dashboard", "page.work.workspace"]
  },

  "page.servicing": {
    id: "page.servicing",
    title: "Servicing",
    summary: "Shows how the firm's services are being delivered to clients and connects service commitments with active operational work.",
    purpose: "Use Servicing to understand which services are active for each client, review service-level execution and move into the related work when action is required.",
    whoUses: "Operations teams, Managers, Partners and authorized servicing users",
    whoCanView: "Authorized users see servicing information within their permitted client and operational scope.",
    whoCanEdit: "Authorized servicing and management users can update servicing information where permitted.",
    workflowImpact: "Servicing configuration influences which client services are active and how related work is created, tracked and reported.",
    examples: [
      "Review which services are active for a client",
      "Check whether recurring compliance services are being delivered",
      "Open related work for a client service",
      "Identify service gaps or inactive engagements"
    ],
    commonMistakes: [
      "Treating a service record as the same thing as an individual Work item",
      "Keeping services active after the engagement has ended",
      "Creating operational work for a service that is not applicable to the client",
      "Ignoring servicing status when reviewing client coverage"
    ],
    related: ["page.clients", "page.work", "page.services"]
  },

  "page.employee-ops": {
    id: "page.employee-ops",
    title: "Employee Operations",
    summary: "Provides a management view of employee workload, ownership, assignments and operational responsibility across the firm.",
    purpose: "Use Employee Operations to understand who is carrying work, identify capacity pressure, review ownership and support better assignment decisions.",
    whoUses: "Managers, Partners and authorized operational users",
    whoCanView: "Users with employee-operations access see workload and assignment information within their permitted scope.",
    whoCanEdit: "Authorized Managers and administrators can perform permitted assignment and employee-operation actions.",
    workflowImpact: "Assignment and ownership changes affect employee workload, Work visibility, Action Centre priorities and operational accountability.",
    examples: [
      "Review open work assigned to each employee",
      "Identify employees with high workload",
      "Assign or reassign work",
      "Check ownership before upcoming compliance deadlines"
    ],
    commonMistakes: [
      "Assigning work based only on availability without considering expertise",
      "Leaving work without a clear owner",
      "Overloading one employee while others have capacity",
      "Changing ownership without checking the current workflow stage or responsibility"
    ],
    related: ["page.team", "page.work", "page.dashboard"]
  },

  "page.team": {
    id: "page.team",
    title: "Team",
    summary: "Maintains the people who work in the firm and participate in Vridhi's operational workflows.",
    purpose: "Use Team to maintain employee records, roles, expertise and participation so work can be assigned to the right people with the right responsibility.",
    whoUses: "Managers, Partners and administrators",
    whoCanView: "Authorized users see team information permitted by their role and operational scope.",
    whoCanEdit: "Authorized administrators and management users can maintain employee information where permitted.",
    workflowImpact: "Team records influence work assignment, workload visibility, expertise-based allocation, review responsibility and access across the platform.",
    examples: [
      "Add a new employee to the firm",
      "Update an employee's role or contact information",
      "Maintain expertise for GST, Income Tax, Audit or ROC work",
      "Deactivate an employee who has left the firm"
    ],
    commonMistakes: [
      "Creating duplicate employee records",
      "Assigning an incorrect operational role",
      "Leaving expertise information outdated",
      "Deactivating an employee without reviewing their open work",
      "Using Team records as a substitute for Identity & Access permissions"
    ],
    related: ["page.employee-ops", "page.work", "page.identity"]
  },

  "page.services": {
    id: "page.services",
    title: "Services",
    summary: "Defines the standardized professional services the firm offers and uses to organize client work.",
    purpose: "Use Services to maintain the firm's service catalogue so recurring and one-time assignments are created consistently across clients and teams.",
    whoUses: "Partners, Managers and authorized administrators",
    whoCanView: "Authorized users can view services available within the firm's configured catalogue.",
    whoCanEdit: "Users with service-management permission can create and maintain service definitions.",
    workflowImpact: "Service configuration influences client servicing, work creation, task templates, document requirements and operational reporting.",
    examples: [
      "Define GST Return Filing as a service",
      "Maintain Income Tax Return or TDS services",
      "Configure Audit, ROC or Incorporation services",
      "Standardize service information used when creating client work"
    ],
    commonMistakes: [
      "Creating duplicate services with slightly different names",
      "Using vague service names that make work difficult to classify",
      "Changing a service definition without considering existing client work",
      "Creating client work against the wrong service"
    ],
    related: ["page.servicing", "page.work", "page.clients"]
  },

  "page.reports": {
    id: "page.reports",
    title: "Reports",
    summary: "Turns Vridhi's operational records into management information about workload, delivery, deadlines and performance.",
    purpose: "Use Reports to understand operational trends, identify bottlenecks, review workload distribution and support management decisions using recorded firm activity.",
    whoUses: "Partners, Managers and authorized reporting users",
    whoCanView: "Users see reports permitted by their reporting and operational access.",
    whoCanEdit: "Reports are not edited directly. Their results are calculated from the underlying operational records.",
    workflowImpact: "Report results change as client, work, assignment, deadline, review and completion information changes throughout Vridhi.",
    examples: [
      "Review work completion and pending workload",
      "Compare workload across employees or teams",
      "Identify overdue or high-risk operational areas",
      "Review client or service-level operational activity"
    ],
    commonMistakes: [
      "Treating report values as manually maintained figures",
      "Making decisions from incomplete operational records",
      "Ignoring the selected reporting period or filters",
      "Trying to correct a report instead of correcting the underlying source record"
    ],
    related: ["page.dashboard", "page.work", "page.employee-ops"]
  },

  "page.audit": {
    id: "page.audit",
    title: "Audit",
    summary: "Provides traceability of important activities and system changes.",
    purpose: "Supports accountability, investigation and operational governance.",
    whoUses: "Administrators, Managers and authorized reviewers",
    whoCanView: "Users with audit access.",
    whoCanEdit: "Audit history is not editable."
  },

  "page.identity": {
    id: "page.identity",
    title: "Identity & Access",
    summary: "Controls who can sign in to Vridhi and what each user is permitted to view or perform.",
    purpose: "Use Identity & Access to manage user access, roles and permission boundaries so employees receive only the access required for their responsibilities.",
    whoUses: "Platform administrators and authorized firm administrators",
    whoCanView: "Only authorized administrators can view identity and access administration.",
    whoCanEdit: "Only authorized administrators can change user access and permission assignments.",
    workflowImpact: "Access changes can immediately affect which clients, work, administration functions and operational actions a user can access throughout Vridhi.",
    examples: [
      "Activate or manage access for a user",
      "Assign the correct administrative or operational role",
      "Review a user's access profile",
      "Remove or restrict access when responsibilities change"
    ],
    commonMistakes: [
      "Granting broader access than the user's role requires",
      "Confusing an employee's Team role with their system access permissions",
      "Leaving access active after a user no longer requires it",
      "Changing access without considering the user's current operational responsibilities"
    ],
    related: ["page.team", "page.settings", "page.audit"]
  },

  "page.settings": {
    id: "page.settings",
    title: "Settings",
    summary: "Contains the firm-level configuration that controls how the Vridhi environment is set up.",
    purpose: "Use Settings to maintain core firm information and administrative configuration that supports day-to-day operation of the platform.",
    whoUses: "Authorized administrators",
    whoCanView: "Only authorized administrators can view firm-level settings.",
    whoCanEdit: "Only authorized administrators can change firm-level configuration.",
    workflowImpact: "Configuration changes can affect how firm information appears and how administrative or operational features behave across Vridhi.",
    examples: [
      "Maintain the firm's legal and display name",
      "Update PAN, GSTIN, contact or address information",
      "Review firm status and administrative configuration"
    ],
    commonMistakes: [
      "Changing firm-level configuration without confirming the impact",
      "Entering incorrect statutory or contact information",
      "Using Settings for operational data that belongs in Clients, Team or Services"
    ],
    related: ["page.identity", "page.team", "page.services"]
  }
};

export function getHelp(id: string): HelpEntry | undefined {
    return helpRegistry[id];
}

