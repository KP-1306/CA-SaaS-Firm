export type Row = Record<string, unknown>;

export const CLIENT_TYPES = [
  'INDIVIDUAL', 'PROPRIETORSHIP', 'PARTNERSHIP', 'LLP',
  'PRIVATE_LIMITED', 'PUBLIC_LIMITED', 'TRUST', 'OTHER',
] as const;

export const ENGAGEMENT_STATUS = ['ACTIVE', 'PROSPECT', 'ON_HOLD', 'INACTIVE'] as const;

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
