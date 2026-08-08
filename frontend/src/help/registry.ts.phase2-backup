import type { HelpEntry } from "./types";

export const helpRegistry: Record<string, HelpEntry> = {

  "page.dashboard": {
    id: "page.dashboard",
    title: "Dashboard",
    summary: "Provides an overall operational view of the CA firm's work.",
    purpose: "Helps users quickly understand work health, pending actions and operational status.",
    whoUses: "Partners, Managers, Employees",
    whoCanView: "Authorized users",
    whoCanEdit: "Not editable",
    related: ["page.work.workspace"]
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
    summary: "Shows operational work that needs attention now.",
    purpose: "Helps users prioritize overdue work, client follow-ups, review items and rework.",
    whoUses: "Employees, Managers, Partners",
    whoCanView: "Authorized users within their operational scope.",
    whoCanEdit: "Actions are performed in the underlying Work Workspace.",
    workflowImpact: "Items change automatically as work health and workflow status change."
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
    summary: "Manages the firm's client records and provides access to each Client Workspace.",
    purpose: "Keeps client identity, relationships and operational work connected in one place.",
    whoUses: "Authorized firm users",
    whoCanView: "Based on client-access permissions.",
    whoCanEdit: "Authorized users with client-management permission."
  },

  "page.work": {
    id: "page.work",
    title: "Work",
    summary: "Provides the operational list of work items across clients and services.",
    purpose: "Allows users to find, open and manage work through its lifecycle.",
    whoUses: "Employees, Reviewers, Managers and Partners",
    whoCanView: "Based on work-access permissions.",
    whoCanEdit: "Controlled by work ownership, controller and authorization rules.",
    workflowImpact: "Changes here affect deadlines, review, documents and operational health."
  },

  "page.servicing": {
    id: "page.servicing",
    title: "Servicing",
    summary: "Provides the operational servicing view for client engagements.",
    purpose: "Connects services with the work performed for clients.",
    whoUses: "Operations and authorized management users",
    whoCanView: "Authorized users.",
    whoCanEdit: "Authorized servicing users."
  },

  "page.employee-ops": {
    id: "page.employee-ops",
    title: "Employee Operations",
    summary: "Provides an operational view of employee workload, ownership and execution.",
    purpose: "Helps leadership understand capacity, assignment and operational responsibility.",
    whoUses: "Managers, Partners and authorized operational users",
    whoCanView: "Based on employee-operation permissions.",
    whoCanEdit: "Authorized management users."
  },

  "page.team": {
    id: "page.team",
    title: "Team",
    summary: "Manages the people who participate in the firm's operational workflows.",
    purpose: "Provides visibility into users, roles and operational participation.",
    whoUses: "Managers and administrators",
    whoCanView: "Authorized users.",
    whoCanEdit: "Authorized administrators and management."
  },

  "page.services": {
    id: "page.services",
    title: "Services",
    summary: "Defines and manages the professional services offered by the firm.",
    purpose: "Standardizes the services that are used to create and manage client work.",
    whoUses: "Partners, Managers and authorized administrators",
    whoCanView: "Authorized users.",
    whoCanEdit: "Users with service-management permission."
  },

  "page.reports": {
    id: "page.reports",
    title: "Reports",
    summary: "Provides reporting and operational analysis based on Vridhi records.",
    purpose: "Helps management understand performance, workload and operational outcomes.",
    whoUses: "Managers, Partners and authorized users",
    whoCanView: "Based on reporting permissions.",
    whoCanEdit: "Reports themselves are not edited directly."
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
    summary: "Controls who can access Vridhi and what they are authorized to do.",
    purpose: "Protects firm information and enforces role and permission boundaries.",
    whoUses: "Administrators",
    whoCanView: "Authorized administrators.",
    whoCanEdit: "Authorized administrators only.",
    workflowImpact: "Access changes can affect what users can view and perform throughout Vridhi."
  },

  "page.settings": {
    id: "page.settings",
    title: "Settings",
    summary: "Contains administrative configuration for the Vridhi environment.",
    purpose: "Allows authorized administrators to manage application configuration.",
    whoUses: "Administrators",
    whoCanView: "Authorized administrators.",
    whoCanEdit: "Authorized administrators."
  }
};

export function getHelp(id: string): HelpEntry | undefined {
    return helpRegistry[id];
}

