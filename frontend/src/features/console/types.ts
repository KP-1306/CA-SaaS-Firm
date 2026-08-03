export type Row = Record<string, unknown>;

export const CLIENT_TYPES = [
  'INDIVIDUAL', 'PROPRIETORSHIP', 'PARTNERSHIP', 'LLP',
  'PRIVATE_LIMITED', 'PUBLIC_LIMITED', 'TRUST', 'OTHER',
] as const;

export const ENGAGEMENT_STATUS = ['ACTIVE', 'PROSPECT', 'ON_HOLD', 'INACTIVE'] as const;

export const CLIENT_LIFECYCLE_STATUS = [
  'PROSPECT', 'ONBOARDING', 'ACTIVE', 'SUSPENDED', 'CLOSED', 'ARCHIVED',
] as const;

export const WORK_STATUS = [
  'NOT_STARTED', 'IN_PROGRESS', 'WAITING_FOR_CLIENT', 'READY_FOR_REVIEW',
  'REWORK_REQUIRED', 'COMPLETED', 'CANCELLED',
] as const;

export const WORK_PRIORITY = ['LOW', 'NORMAL', 'HIGH', 'URGENT'] as const;

export const DOC_STATUS = ['REQUESTED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'ACCEPTED', 'REJECTED', 'WAIVED'] as const;

export function label(value: string): string {
  return value
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function isOverdue(dueDate: unknown, status: unknown): boolean {
  if (!dueDate || status === 'COMPLETED' || status === 'CANCELLED') return false;
  const due = new Date(String(dueDate));
  return !Number.isNaN(due.getTime()) && due < new Date(new Date().toDateString());
}

export interface WorkItemPermissions {
  current_controller?: string;
  current_controller_name?: string;
  is_locked?: boolean;
  can_edit?: boolean;
  can_submit_for_review?: boolean;
  can_review?: boolean;
  can_upload_internal?: boolean;
}

export function lockMessage(status: unknown, controllerName: unknown): string {
  switch (String(status)) {
    case 'READY_FOR_REVIEW':
      return controllerName
        ? `Submitted for review - controlled by ${String(controllerName)}.`
        : 'Submitted for review and controlled by the reviewer.';
    case 'WAITING_FOR_CLIENT':
      return 'Waiting for client documents - internal editing is locked.';
    case 'COMPLETED':
      return 'This work is completed and read-only.';
    case 'CANCELLED':
      return 'This work is cancelled and read-only.';
    default:
      return 'This work item is read-only for you at its current stage.';
  }
}

// --- Employee Operations V1 (additive) ---
export const EMPLOYMENT_TYPES = [
  'FULL_TIME', 'PART_TIME', 'ARTICLE', 'INTERN', 'CONTRACT', 'CONSULTANT',
] as const;

export const EMPLOYMENT_STATUS = [
  'PROBATION', 'CONFIRMED', 'NOTICE_PERIOD', 'EXITED', 'SUSPENDED',
] as const;

export const PROFICIENCY_LEVELS = [
  'BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'SME', 'REVIEWER',
] as const;

export const EXPERTISE_CATEGORIES = [
  'GST', 'INCOME_TAX', 'TDS', 'ROC', 'STATUTORY_AUDIT', 'INTERNAL_AUDIT',
  'TAX_AUDIT', 'BANK_AUDIT', 'CONCURRENT_AUDIT', 'ACCOUNTING', 'BOOKKEEPING',
  'PAYROLL', 'COMPLIANCE', 'COMPANY_FORMATION', 'PROJECT_FINANCE', 'MSME',
  'FEMA', 'INTERNATIONAL_TAX', 'NRI_TAXATION', 'TRANSFER_PRICING',
] as const;

export const LEAVE_STATUS = ['REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED'] as const;

export const REVIEWER_SCOPES = [
  'ASSIGNMENT', 'SERVICE', 'TASK_TEMPLATE', 'TEAM', 'EMPLOYEE_DEFAULT', 'PARTNER_FALLBACK',
] as const;

export const REVIEWER_LEVELS = ['PRIMARY', 'SECONDARY', 'ESCALATION', 'FINAL_APPROVER'] as const;
