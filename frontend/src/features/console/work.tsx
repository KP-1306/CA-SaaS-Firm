import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  act,
  ApiRequestError,
  list,
  save,
  uploadMany,
  getObject,
} from './api';
import {
  DOCUMENT_CATEGORIES,
  WORK_PRIORITY,
  WORK_STATUS,
  isOverdue,
  label,
  lockMessage,
} from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';
import type { Field } from './ui';
import { QAOperationalQueue, QAWorkspace } from './qa';
import { AssignmentWorkspace } from './AssignmentWorkspace';
import './work-timeline.css';
export type WorkHealthSnapshot = {
  contract_version: number;
  work_item_id: string;
  progress: number;
  health: 'GREEN' | 'AMBER' | 'RED';
  risk: 'LOW' | 'MEDIUM' | 'HIGH';
  current_controller:
    | 'OWNER'
    | 'CLIENT'
    | 'REVIEWER'
    | 'NONE';
  waiting_days: number;
  waiting_since: string | null;
  due_state:
    | 'ON_TRACK'
    | 'DUE_SOON'
    | 'OVERDUE';
  days_to_due: number | null;
  operational: {
    total: number;
    completed: number;
    remaining: number;
    mandatory_total: number;
    mandatory_completed: number;
    mandatory_remaining: number;
    completion_percent: number | null;
  };
  documents: {
    total: number;
    satisfied: number;
    pending: number;
    mandatory_total: number;
    mandatory_satisfied: number;
    mandatory_missing: number;
    missing: number;
    pending_review: number;
    rejected: number;
    expired: number;
    pending_acceptance: number;
    ready_for_review: boolean;
    readiness_state: string;
    health_score: number;
    blockers: Row[];
  };
  next_action: {
    code: string;
    label: string;
  };
  reasons: string[];
  calculated_at: string;
};

export function workHealthTone(
  health: unknown,
): 'stable' | 'watch' | 'risk' {
  if (health === 'RED') return 'risk';
  if (health === 'AMBER') return 'watch';
  return 'stable';
}

function dueStateText(
  state: WorkHealthSnapshot['due_state'],
  daysToDue: number | null,
): string {
  if (state === 'OVERDUE') {
    const days =
      typeof daysToDue === 'number'
        ? Math.abs(daysToDue)
        : null;

    if (days === null) return 'Overdue';

    return `Overdue by ${days} day${
      days === 1 ? '' : 's'
    }`;
  }

  if (state === 'DUE_SOON') {
    if (daysToDue === 0) {
      return 'Due today';
    }

    if (
      typeof daysToDue === 'number'
    ) {
      return `Due in ${daysToDue} day${
        daysToDue === 1 ? '' : 's'
      }`;
    }

    return 'Due soon';
  }

  if (
    typeof daysToDue === 'number'
  ) {
    return `Due in ${daysToDue} day${
      daysToDue === 1 ? '' : 's'
    }`;
  }

  return 'On track';
}
export function isWorkHealthSnapshot(
  value: unknown,
): value is WorkHealthSnapshot {
  if (
    !value ||
    typeof value !== 'object'
  ) {
    return false;
  }

  const candidate =
    value as Partial<WorkHealthSnapshot>;

  return (
    typeof candidate.progress === 'number' &&
    typeof candidate.health === 'string' &&
    typeof candidate.risk === 'string' &&
    typeof candidate.current_controller ===
      'string' &&
    typeof candidate.waiting_days === 'number' &&
    typeof candidate.due_state === 'string' &&
    !!candidate.operational &&
    typeof candidate.operational === 'object' &&
    !!candidate.documents &&
    typeof candidate.documents === 'object' &&
    !!candidate.next_action &&
    typeof candidate.next_action === 'object' &&
    typeof candidate.next_action.label ===
      'string' &&
    Array.isArray(candidate.reasons)
  );
}



export function WorkHealthCard({
  health,
  loading = false,
  error = '',
}: {
  health: WorkHealthSnapshot | null;
  loading?: boolean;
  error?: string;
}): React.JSX.Element {
  if (loading) {
    return (
      <section
        className="cx-work-health-shell loading"
        aria-label="Work health"
      >
        <span className="cx-work-health-kicker">
          Work health
        </span>
        <strong>
          Calculating operational healthâ€¦
        </strong>
      </section>
    );
  }

  if (!health) {
    return (
      <section
        className="cx-work-health-shell unavailable"
        aria-label="Work health"
      >
        <span className="cx-work-health-kicker">
          Work health
        </span>
        <strong>
          Health unavailable
        </strong>
        <span>
          {error ||
            'Operational health could not be loaded.'}
        </span>
      </section>
    );
  }

  const tone =
    workHealthTone(
      health.health
    );

  const progress =
    Math.max(
      0,
      Math.min(
        100,
        Number(
          health.progress || 0
        ),
      ),
    );

  return (
    <section
      className={
        `cx-work-health-shell ${tone}`
      }
      aria-label="Work health"
      data-health={health.health}
    >
      <div className="cx-work-health-main">
        <div
          className="cx-work-health-progress"
          aria-label={
            `${progress}% complete`
          }
        >
          <strong>
            {progress}%
          </strong>
          <span>complete</span>
        </div>

        <div className="cx-work-health-status">
          <span className="cx-work-health-kicker">
            Work health
          </span>

          <div className="cx-work-health-status-line">
            <strong>
              {label(health.health)}
            </strong>
            <span>Â·</span>
            <span>
              {label(health.risk)} risk
            </span>
          </div>

          <div
            className="cx-work-health-progress-track"
            aria-hidden="true"
          >
            <span
              style={{
                width:
                  `${progress}%`,
              }}
            />
          </div>
        </div>
      </div>

      <div className="cx-work-health-metrics">
        <div>
          <span>
            Waiting on
          </span>
          <strong>
            {
              health.current_controller ===
              'NONE'
                ? 'No one'
                : label(
                    health.current_controller,
                  )
            }
          </strong>
          <small>
            {
              health.waiting_days > 0
                ? `${health.waiting_days} day${
                    health.waiting_days === 1
                      ? ''
                      : 's'
                  }`
                : 'No active wait'
            }
          </small>
        </div>

        <div>
          <span>Due</span>
          <strong>
            {label(
              health.due_state
            )}
          </strong>
          <small>
            {dueStateText(
              health.due_state,
              health.days_to_due,
            )}
          </small>
        </div>

        <div>
          <span>
            Work details
          </span>
          <strong>
            {
              health.operational
                .completed
            }/
            {
              health.operational
                .total
            }
          </strong>
          <small>
            {
              health.operational
                .mandatory_remaining
            } mandatory remaining
          </small>
        </div>

        <div>
          <span>
            Documents
          </span>
          <strong>
            {
              health.documents
                .satisfied
            }/
            {
              health.documents
                .total
            }
          </strong>
          <small>
            {
              health.documents
                .missing
            } missing Â·{' '}
            {
              health.documents
                .pending_review
            } pending review
          </small>
        </div>
      </div>

      <div className="cx-work-health-next">
        <span>
          Next action
        </span>
        <strong>
          {
            health.next_action
              .label
          }
        </strong>
      </div>

      {
        health.reasons.length > 0
          ? (
            <div className="cx-work-health-reasons">
              {
                health.reasons
                  .slice(0, 3)
                  .map(
                    (reason) => (
                      <span key={reason}>
                        {reason}
                      </span>
                    ),
                  )
              }
            </div>
          )
          : null
      }
    </section>
  );
}



function statusTone(s: string): string {
  if (s === 'COMPLETED' || s === 'RECEIVED' || s === 'ACCEPTED') return 'ok';
  if (s === 'CANCELLED' || s === 'REWORK_REQUIRED' || s === 'REJECTED') return 'danger';
  if (
    s === 'WAITING_FOR_CLIENT' ||
    s === 'READY_FOR_REVIEW' ||
    s === 'REQUESTED' ||
    s === 'PARTIALLY_RECEIVED'
  ) return 'warn';
  return 'muted';
}

function formatBytes(value: unknown): string {
  const bytes = Number(value ?? 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB';
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function documentExpiryTone(row: Row): string {
  if (row.is_expired === true) return 'danger';

  const days = Number(row.days_to_expiry);

  if (Number.isFinite(days) && days >= 0 && days <= 30) {
    return 'warn';
  }

  return 'muted';
}

function expiryText(row: Row): string {
  if (!row.expires_on) return 'No expiry';

  if (row.is_expired === true) {
    return `Expired ${String(row.expires_on)}`;
  }

  const days = Number(row.days_to_expiry);

  if (Number.isFinite(days)) {
    if (days === 0) return 'Expires today';
    if (days > 0 && days <= 30) return `Expires in ${days} day${days === 1 ? '' : 's'}`;
  }

  return `Valid until ${String(row.expires_on)}`;
}

function useList(resource: string, params: Record<string, string> = {}): {
  rows: Row[];
  error: string;
  loading: boolean;
  reload: () => void;
} {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify([resource, params]);
  const reload = (): void => {
    setLoading(true);
    list(resource, params)
      .then((r) => {
        setRows(r);
        setError('');
      })
      .catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setLoading(false));
  };
  useEffect(reload, [key]);
  return { rows, error, loading, reload };
}

export type PendingDocumentDecision =
  | {
      kind: 'ATTACHMENT_REVIEW';
      attachmentId: string;
      requestId: string;
      status: 'ACCEPTED' | 'REJECTED';
      label: 'Accept' | 'Reject';
      comment: string;
    }
  | {
      kind: 'REQUEST_WAIVER';
      requestId: string;
      status: 'WAIVED';
      label: 'Waive';
      comment: string;
    };

export async function executePendingDocumentDecision(
  decision: PendingDocumentDecision,
): Promise<Row> {
  if (decision.kind === 'ATTACHMENT_REVIEW') {
    return act('document-attachments', decision.attachmentId, 'review', {
      status: decision.status,
      comment: decision.comment,
    });
  }
  return act('document-requests', decision.requestId, 'verify', {
    status: 'WAIVED',
    comment: decision.comment,
  });
}

type DuplicateResolution =
  | 'CONFIRMED_DUPLICATE'
  | 'KEPT_AS_VERSION';

type AttachmentListProps = {
  rows: Row[];
  pendingDecision?: PendingDocumentDecision | null;
  onSelectReview?: (
    attachment: Row,
    status: 'ACCEPTED' | 'REJECTED',
  ) => void;
  onResolveDuplicate?:
    | ((
        attachment: Row,
        resolution: DuplicateResolution,
      ) => void)
    | undefined;
  onMarkCanonical?:
    | ((attachment: Row) => void)
    | undefined;
  canOperateVersions?: boolean;
};

function AttachmentList({
  rows,
  pendingDecision = null,
  onSelectReview,
  onResolveDuplicate,
  onMarkCanonical,
  canOperateVersions = false,
}: AttachmentListProps): React.JSX.Element {
  if (rows.length === 0) {
    return <p style={{ color: '#64748b', fontSize: 13 }}>No files uploaded.</p>;
  }
  return (
    <ul className="cx-file-list">
      {rows.map((attachment) => {
        const attachmentId = String(attachment.id);

        const reviewStatus = String(
          attachment.review_status || 'PENDING_REVIEW',
        );

        const duplicateResolution = String(
          attachment.duplicate_resolution ||
            'NOT_APPLICABLE',
        );

        const isPending =
          reviewStatus === 'PENDING_REVIEW';

        const isAccepted =
          reviewStatus === 'ACCEPTED';

        const unresolvedDuplicate =
          attachment.is_duplicate === true &&
          duplicateResolution === 'UNRESOLVED';
        const selected =
          pendingDecision?.kind === 'ATTACHMENT_REVIEW' &&
          pendingDecision.attachmentId === attachmentId;
        return (
          <li
            className={`cx-file-row${
              attachment.is_canonical === true
                ? ' canonical'
                : ''
            }${
              unresolvedDuplicate
                ? ' duplicate-unresolved'
                : ''
            }`}
            key={attachmentId}
          >
            <div className="cx-file-main">
              <div className="cx-document-file-title">
                <a href={String(attachment.download_url)}>
                  {String(attachment.original_name)}
                </a>
                <span className="cx-version-badge">
                  {String(
                    attachment.version_label ||
                      `V${String(
                        attachment.version_number || 1,
                      )}`,
                  )}
                </span>

                {attachment.is_canonical === true ? (
                  <span className="cx-canonical-badge">
                    Current
                  </span>
                ) : null}

                {attachment.is_duplicate === true ? (
                  <span className="cx-duplicate-badge">Duplicate</span>
                ) : null}
              </div>

              <div className="cx-muted">
                {label(String(attachment.source))}
                {' Ã‚Â· '}
                {formatBytes(attachment.size_bytes)}
                {' Ã‚Â· '}
                {String(attachment.created_at ?? '').slice(0, 16).replace('T', ' ')}
              </div>

              {attachment.supersedes_attachment_id ? (
                <div className="cx-version-note">
                  New version of the previous uploaded document
                </div>
              ) : null}

              {attachment.is_duplicate === true ? (
                <div className="cx-duplicate-warning">
                  This file has the same content as an earlier version.
                </div>
              ) : null}
              {attachment.reviewed_at ? (
                <div className="cx-muted">
                  Reviewed by {String(attachment.reviewed_by_name || attachment.reviewed_by || 'Unknown reviewer')}
                  {' - '}
                  {String(attachment.reviewed_at).slice(0, 16).replace('T', ' ')}
                </div>
              ) : null}
              {attachment.review_comment ? (
                <div className="cx-review-comment">{String(attachment.review_comment)}</div>
              ) : null}
            </div>
            <div className="cx-file-review">
              <Chip
                value={reviewStatus}
                tone={statusTone(reviewStatus)}
              />

              {attachment.is_canonical === true ? (
                <span className="cx-canonical-status">
                  Authoritative
                </span>
              ) : null}

              {unresolvedDuplicate &&
              canOperateVersions &&
              onResolveDuplicate ? (
                <div className="cx-duplicate-resolution-actions">
                  <span>Duplicate decision required</span>

                  <button
                    type="button"
                    className="cx-btn subtle"
                    onClick={() =>
                      onResolveDuplicate(
                        attachment,
                        'KEPT_AS_VERSION',
                      )
                    }
                  >
                    Keep as version
                  </button>

                  <button
                    type="button"
                    className="cx-btn danger"
                    onClick={() =>
                      onResolveDuplicate(
                        attachment,
                        'CONFIRMED_DUPLICATE',
                      )
                    }
                  >
                    Confirm duplicate
                  </button>
                </div>
              ) : null}

              {attachment.is_duplicate === true &&
              !unresolvedDuplicate ? (
                <span className="cx-duplicate-resolution-status">
                  {label(duplicateResolution)}
                </span>
              ) : null}

              {isAccepted &&
              attachment.is_canonical !== true &&
              !unresolvedDuplicate &&
              canOperateVersions &&
              onMarkCanonical ? (
                <button
                  type="button"
                  className="cx-btn subtle"
                  onClick={() =>
                    onMarkCanonical(attachment)
                  }
                >
                  Mark current
                </button>
              ) : null}

              {isPending && onSelectReview ? (
                <div className="cx-doc-actions">
                  <button
                    type="button"
                    className={`cx-btn${selected && pendingDecision.status === 'ACCEPTED' ? ' pending' : ''}`}
                    onClick={() => onSelectReview(attachment, 'ACCEPTED')}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className={`cx-btn danger${selected && pendingDecision.status === 'REJECTED' ? ' pending' : ''}`}
                    onClick={() => onSelectReview(attachment, 'REJECTED')}
                  >
                    Reject
                  </button>
                </div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

interface DocumentReadinessView {
  ready: boolean;
  state: string;
  healthScore: number;
  mandatoryTotal: number;
  mandatorySatisfied: number;
  mandatoryMissing: number;
  totalDocuments: number;
  satisfiedDocuments: number;
  blockers: Row[];
}

function documentDependencyReason(row: Row): string {
  if (row.is_expired === true) return 'Expired';

  switch (String(row.status)) {
    case 'REJECTED':
      return 'Rejected Ã¢â‚¬â€ upload a corrected document';
    case 'RECEIVED':
      return 'Received Ã¢â‚¬â€ waiting for acceptance';
    case 'PARTIALLY_RECEIVED':
      return 'Partially received';
    case 'REQUESTED':
      return 'Not received';
    default:
      return label(String(row.status || 'Pending'));
  }
}

function calculateReadinessView(
  rows: Row[],
  workItem: Row,
): DocumentReadinessView {
  const evaluated: Array<Row & { satisfied: boolean }> =
    rows.map((row): Row & { satisfied: boolean } => {
      const resolved =
        ['ACCEPTED', 'WAIVED'].includes(String(row.status)) &&
        row.is_expired !== true;

      return {
        ...row,
        satisfied: resolved,
      };
    });

  const mandatory = evaluated.filter(
    (row) => row.mandatory === true,
  );

  const mandatorySatisfied = mandatory.filter(
    (row) => row.satisfied === true,
  );

  const blockers = mandatory.filter(
    (row) => row.satisfied !== true,
  );

  const satisfied = evaluated.filter(
    (row) => row.satisfied === true,
  );

  const backendScore = Number(workItem.document_health_score);
  const calculatedScore = evaluated.length
    ? Math.round((satisfied.length / evaluated.length) * 100)
    : 100;

  let state = String(
    workItem.document_readiness_state || '',
  );

  if (!state || rows.length > 0) {
    if (blockers.length === 0) {
      state = 'READY';
    } else if (
      blockers.some((row) => row.is_expired === true)
    ) {
      state = 'BLOCKED_BY_EXPIRED_DOCUMENT';
    } else if (
      blockers.some((row) => String(row.status) === 'REJECTED')
    ) {
      state = 'BLOCKED_BY_REJECTED_DOCUMENT';
    } else if (
      blockers.some((row) => String(row.status) === 'RECEIVED')
    ) {
      state = 'BLOCKED_PENDING_ACCEPTANCE';
    } else if (
      blockers.some(
        (row) => String(row.status) === 'PARTIALLY_RECEIVED',
      )
    ) {
      state = 'BLOCKED_PARTIALLY_RECEIVED';
    } else {
      state = 'WAITING_FOR_CLIENT';
    }
  }

  return {
    ready: blockers.length === 0,
    state,
    healthScore:
      rows.length > 0 || !Number.isFinite(backendScore)
        ? calculatedScore
        : backendScore,
    mandatoryTotal:
      rows.length > 0
        ? mandatory.length
        : Number(workItem.mandatory_document_total ?? 0),
    mandatorySatisfied:
      rows.length > 0
        ? mandatorySatisfied.length
        : Number(
            workItem.mandatory_document_satisfied ?? 0,
          ),
    mandatoryMissing:
      rows.length > 0
        ? blockers.length
        : Number(workItem.mandatory_document_missing ?? 0),
    totalDocuments: evaluated.length,
    satisfiedDocuments: satisfied.length,
    blockers:
      rows.length > 0
        ? blockers
        : Array.isArray(workItem.document_blockers)
          ? (workItem.document_blockers as Row[])
          : [],
  };
}

function readinessStateText(state: string): string {
  switch (state) {
    case 'READY':
      return 'Ready for review';
    case 'BLOCKED_BY_EXPIRED_DOCUMENT':
      return 'Blocked by expired document';
    case 'BLOCKED_BY_REJECTED_DOCUMENT':
      return 'Blocked by rejected document';
    case 'BLOCKED_PENDING_ACCEPTANCE':
      return 'Documents waiting for acceptance';
    case 'BLOCKED_PARTIALLY_RECEIVED':
      return 'Mandatory documents partially received';
    case 'WAITING_FOR_CLIENT':
      return 'Waiting for client documents';
    default:
      return label(state || 'Document status unavailable');
  }
}

type DocumentQueueKind =
  | 'EXPIRED'
  | 'EXPIRING'
  | 'REJECTED'
  | 'PENDING_REVIEW'
  | 'PARTIAL'
  | 'MISSING';

interface DocumentQueueItem {
  id: string;
  name: string;
  category: string;
  kind: DocumentQueueKind;
  message: string;
  priority: number;
  document: Row;
}

function dateOnly(value: unknown): Date | null {
  if (!value) return null;

  const parsed = new Date(`${String(value)}T00:00:00`);

  return Number.isNaN(parsed.getTime())
    ? null
    : parsed;
}

function daysUntil(value: unknown): number | null {
  const target = dateOnly(value);

  if (!target) return null;

  const today = new Date();
  const start = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );

  return Math.ceil(
    (target.getTime() - start.getTime()) /
      (24 * 60 * 60 * 1000),
  );
}

function buildDocumentActionQueue(
  rows: Row[],
): DocumentQueueItem[] {
  const queue: DocumentQueueItem[] = [];

  for (const row of rows) {
    const status = String(row.status || '');
    const expiryDays = daysUntil(row.expires_on);
    const mandatory = row.mandatory === true;

    if (
      row.is_expired === true ||
      (expiryDays !== null && expiryDays < 0)
    ) {
      queue.push({
        id: `${String(row.id)}-expired`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'EXPIRED',
        message: 'Expired Ã¢â‚¬â€ obtain a valid replacement',
        priority: 10,
        document: row,
      });

      continue;
    }

    if (
      expiryDays !== null &&
      expiryDays >= 0 &&
      expiryDays <= 30
    ) {
      queue.push({
        id: `${String(row.id)}-expiring`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'EXPIRING',
        message:
          expiryDays === 0
            ? 'Expires today'
            : `Expires in ${expiryDays} day${
                expiryDays === 1 ? '' : 's'
              }`,
        priority: 20,
        document: row,
      });
    }

    if (status === 'REJECTED') {
      queue.push({
        id: `${String(row.id)}-rejected`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'REJECTED',
        message: 'Rejected Ã¢â‚¬â€ corrected document required',
        priority: 15,
        document: row,
      });

      continue;
    }

    if (status === 'RECEIVED') {
      queue.push({
        id: `${String(row.id)}-review`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'PENDING_REVIEW',
        message: 'Uploaded Ã¢â‚¬â€ review and accept or reject',
        priority: 30,
        document: row,
      });

      continue;
    }

    if (status === 'PARTIALLY_RECEIVED') {
      queue.push({
        id: `${String(row.id)}-partial`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'PARTIAL',
        message: 'Only part of the required evidence received',
        priority: 40,
        document: row,
      });

      continue;
    }

    if (
      mandatory &&
      status === 'REQUESTED'
    ) {
      queue.push({
        id: `${String(row.id)}-missing`,
        name: String(row.name),
        category: String(row.category || 'OTHER'),
        kind: 'MISSING',
        message: 'Mandatory document not yet received',
        priority: 50,
        document: row,
      });
    }
  }

  return queue.sort(
    (left, right) =>
      left.priority - right.priority ||
      left.name.localeCompare(right.name),
  );
}

function documentQueueLabel(
  kind: DocumentQueueKind,
): string {
  switch (kind) {
    case 'EXPIRED':
      return 'Expired';
    case 'EXPIRING':
      return 'Expiring';
    case 'REJECTED':
      return 'Rejected';
    case 'PENDING_REVIEW':
      return 'Review';
    case 'PARTIAL':
      return 'Partial';
    case 'MISSING':
      return 'Missing';
  }
}

function documentQueueTone(
  kind: DocumentQueueKind,
): 'danger' | 'warn' | 'muted' {
  if (
    kind === 'EXPIRED' ||
    kind === 'REJECTED'
  ) {
    return 'danger';
  }

  if (
    kind === 'EXPIRING' ||
    kind === 'PARTIAL' ||
    kind === 'MISSING'
  ) {
    return 'warn';
  }

  return 'muted';
}


export type ServiceOperationalFieldDefinition = {
  id: string;
  service_id: string;
  key: string;
  label: string;
  field_type:
    | 'TEXT'
    | 'LONG_TEXT'
    | 'NUMBER'
    | 'DATE'
    | 'BOOLEAN'
    | 'SELECT';
  help_text?: string;
  placeholder?: string;
  required?: boolean;
  options?: unknown[];
  display_order?: number;
  is_active?: boolean;
};

export type ChecklistVisualState = {
  key: 'MISSING' | 'PENDING_REVIEW' | 'RECEIVED' | 'REJECTED';
  label: string;
  tone: 'missing' | 'pending' | 'received' | 'rejected';
};

export function checklistVisualState(
  row: Row,
): ChecklistVisualState {
  const accepted = Number(
    row.accepted_attachment_count ?? 0,
  );

  const pendingReview = Number(
    row.pending_review_count ?? 0,
  );

  const attachmentCount = Number(
    row.attachment_count ?? 0,
  );

  const status = String(row.status ?? '');
  const reviewStatus = String(row.review_status ?? '');

  if (
    status === 'REJECTED' ||
    reviewStatus === 'REJECTED'
  ) {
    return {
      key: 'REJECTED',
      label: 'Document rejected',
      tone: 'rejected',
    };
  }

  if (
    status === 'ACCEPTED' ||
    status === 'WAIVED' ||
    accepted > 0
  ) {
    return {
      key: 'RECEIVED',
      label:
        status === 'WAIVED'
          ? 'Requirement waived'
          : 'Received and accepted',
      tone: 'received',
    };
  }

  if (
    pendingReview > 0 ||
    attachmentCount > 0
  ) {
    return {
      key: 'PENDING_REVIEW',
      label: 'Uploaded Ã¢â‚¬â€ pending review',
      tone: 'pending',
    };
  }

  return {
    key: 'MISSING',
    label: 'Required document missing',
    tone: 'missing',
  };
}


function operationalValue(
  values: Row,
  key: string,
): unknown {
  return values[key] ?? '';
}


export function OperationalFieldsPanel({
  definitions,
  values,
  disabled = false,
  loading = false,
  onChange,
}: {
  definitions: ServiceOperationalFieldDefinition[];
  values: Row;
  disabled?: boolean;
  loading?: boolean;
  onChange: (
    key: string,
    value: unknown,
  ) => void;
}): React.JSX.Element | null {
  const activeDefinitions = definitions
    .filter(
      (field) =>
        field.is_active !== false,
    )
    .sort(
      (left, right) =>
        Number(left.display_order ?? 10) -
          Number(right.display_order ?? 10) ||
        left.label.localeCompare(right.label),
    );

  if (loading) {
    return (
      <section
        className="cx-operational-fields"
        aria-label="Operational details"
      >
        <div className="cx-operational-fields-heading">
          <div>
            <h4>Operational details</h4>
            <p>
              Loading fields for the selected serviceÃ¢â‚¬Â¦
            </p>
          </div>
        </div>
      </section>
    );
  }

  if (activeDefinitions.length === 0) {
    return null;
  }

  return (
    <section
      className="cx-operational-fields"
      aria-label="Operational details"
    >
      <div className="cx-operational-fields-heading">
        <div>
          <h4>Operational details</h4>
          <p>
            Complete the information required for the
            selected service.
          </p>
        </div>

        <span className="cx-operational-field-count">
          {activeDefinitions.length}{' '}
          field
          {activeDefinitions.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="cx-operational-fields-grid">
        {activeDefinitions.map((field) => {
          const fieldId =
            `operational-${field.key}`;

          const value = operationalValue(
            values,
            field.key,
          );

          const options = Array.isArray(
            field.options,
          )
            ? field.options.map(
                (option) => String(option),
              )
            : [];

          return (
            <div
              className={
                `cx-field cx-operational-field ${
                  field.field_type === 'LONG_TEXT'
                    ? 'wide'
                    : ''
                }`
              }
              key={field.id || field.key}
            >
              <label htmlFor={fieldId}>
                {field.label}

                {field.required ? (
                  <span
                    className="cx-required-marker"
                    aria-label="required"
                  >
                    {' '}*
                  </span>
                ) : null}
              </label>

              {field.field_type === 'LONG_TEXT' ? (
                <textarea
                  id={fieldId}
                  value={String(value)}
                  placeholder={
                    field.placeholder || ''
                  }
                  disabled={disabled}
                  required={
                    field.required === true
                  }
                  onChange={(event) =>
                    onChange(
                      field.key,
                      event.target.value,
                    )
                  }
                />
              ) : field.field_type === 'SELECT' ? (
                <select
                  id={fieldId}
                  value={String(value)}
                  disabled={disabled}
                  required={
                    field.required === true
                  }
                  onChange={(event) =>
                    onChange(
                      field.key,
                      event.target.value,
                    )
                  }
                >
                  <option value="">
                    Select {field.label}
                  </option>

                  {options.map((option) => (
                    <option
                      key={option}
                      value={option}
                    >
                      {option}
                    </option>
                  ))}
                </select>
              ) : field.field_type === 'BOOLEAN' ? (
                <select
                  id={fieldId}
                  value={
                    typeof value === 'boolean'
                      ? String(value)
                      : ''
                  }
                  disabled={disabled}
                  required={
                    field.required === true
                  }
                  onChange={(event) => {
                    const selected =
                      event.target.value;

                    onChange(
                      field.key,
                      selected === ''
                        ? ''
                        : selected === 'true',
                    );
                  }}
                >
                  <option value="">
                    Select Yes or No
                  </option>
                  <option value="true">
                    Yes
                  </option>
                  <option value="false">
                    No
                  </option>
                </select>
              ) : (
                <input
                  id={fieldId}
                  type={
                    field.field_type === 'NUMBER'
                      ? 'number'
                      : field.field_type === 'DATE'
                        ? 'date'
                        : 'text'
                  }
                  value={String(value)}
                  placeholder={
                    field.placeholder || ''
                  }
                  disabled={disabled}
                  required={
                    field.required === true
                  }
                  step={
                    field.field_type === 'NUMBER'
                      ? 'any'
                      : undefined
                  }
                  onChange={(event) =>
                    onChange(
                      field.key,
                      event.target.value,
                    )
                  }
                />
              )}

              {field.help_text ? (
                <small className="cx-field-help">
                  {field.help_text}
                </small>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}


export function DocumentsPanel({
  workItemId,
  clientId,
  canUploadInternal,
  workItem = {},
}: {
  workItemId: string;
  clientId: string;
  canUploadInternal: boolean;
  workItem?: Row;
}): React.JSX.Element {
  const docs = useList('document-requests', { work_item_id: workItemId });
  const contacts = useList('client-contacts', { client_id: clientId });
  const internalFiles = useList('document-attachments', { work_item_id: workItemId });
  const [editing, setEditing] = useState<Row | null>(null);
  const [attachments, setAttachments] = useState<Record<string, Row[]>>({});
  const [err, setErr] = useState('');
  const [pendingDecision, setPendingDecision] =
    useState<PendingDocumentDecision | null>(null);

  const [uploadIntentByRequest, setUploadIntentByRequest] =
    useState<
      Record<
        string,
        'NEW_VERSION' | 'SEPARATE_DOCUMENT'
      >
    >({});

  const [duplicateUpload, setDuplicateUpload] =
    useState<{
      requestId: string;
      files: File[];
      existingAttachment: Row | null;
    } | null>(null);

  const eligibleContacts = contacts.rows.filter(
    (c) => c.is_active && c.can_receive_document_requests !== false,
  );

  const documentSummary = useMemo(() => {
    const total = docs.rows.length;
    const accepted = docs.rows.filter((row) => String(row.status) === 'ACCEPTED').length;
    const pendingReview = docs.rows.reduce(
      (count, row) => count + Number(row.pending_review_count ?? 0),
      0,
    );
    const expired = docs.rows.filter((row) => row.is_expired === true).length;
    const mandatoryPending = docs.rows.filter(
      (row) =>
        row.mandatory === true &&
        !['ACCEPTED', 'WAIVED'].includes(String(row.status)),
    ).length;

    return {
      total,
      accepted,
      pendingReview,
      expired,
      mandatoryPending,
    };
  }, [docs.rows]);

  const readiness = useMemo(
    () => calculateReadinessView(docs.rows, workItem),
    [docs.rows, workItem],
  );

  const readinessTone = readiness.ready
    ? 'ready'
    : readiness.healthScore >= 70
      ? 'attention'
      : 'blocked';

  const documentActionQueue = useMemo(
    () => buildDocumentActionQueue(docs.rows),
    [docs.rows],
  );

  const actionQueueCounts = useMemo(
    () => ({
      expired: documentActionQueue.filter(
        (item) => item.kind === 'EXPIRED',
      ).length,
      expiring: documentActionQueue.filter(
        (item) => item.kind === 'EXPIRING',
      ).length,
      rejected: documentActionQueue.filter(
        (item) => item.kind === 'REJECTED',
      ).length,
      review: documentActionQueue.filter(
        (item) => item.kind === 'PENDING_REVIEW',
      ).length,
      client: documentActionQueue.filter(
        (item) =>
          item.kind === 'MISSING' ||
          item.kind === 'PARTIAL',
      ).length,
    }),
    [documentActionQueue],
  );

  const loadAttachments = (requestId: string): void => {
    list('document-attachments', { document_request_id: requestId })
      .then((rows) => setAttachments((current) => ({ ...current, [requestId]: rows })))
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };
  useEffect(() => {
    for (const doc of docs.rows) loadAttachments(String(doc.id));
  }, [JSON.stringify(docs.rows.map((d) => d.id))]);

  const submit = (): void => {
    if (!editing) return;
    const body: Row = { ...editing, work_item_id: workItemId, client_id: clientId };
    if (!body.requested_from_contact_id) {
      setErr('Select a client contact before sending a document request.');
      return;
    }
    save('document-requests', body)
      .then(() => {
        setEditing(null);
        setErr('');
        docs.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const selectAttachmentDecision = (
    attachment: Row,
    status: 'ACCEPTED' | 'REJECTED',
  ): void => {
    const attachmentId = String(attachment.id);
    const requestId = String(attachment.document_request_id);
    if (
      pendingDecision?.kind === 'ATTACHMENT_REVIEW' &&
      pendingDecision.attachmentId === attachmentId &&
      pendingDecision.status === status
    ) {
      setPendingDecision(null);
      setErr('');
      return;
    }
    const comment =
      status === 'REJECTED'
        ? (window.prompt('Reject attachment reason?') ?? '').trim()
        : '';
    if (status === 'REJECTED' && !comment) return;
    setPendingDecision({
      kind: 'ATTACHMENT_REVIEW',
      attachmentId,
      requestId,
      status,
      label: status === 'ACCEPTED' ? 'Accept' : 'Reject',
      comment,
    });
    setErr('');
  };

  const selectWaiver = (request: Row): void => {
    const requestId = String(request.id);
    if (
      pendingDecision?.kind === 'REQUEST_WAIVER' &&
      pendingDecision.requestId === requestId
    ) {
      setPendingDecision(null);
      setErr('');
      return;
    }
    const comment = (window.prompt('Waiver reason?') ?? '').trim();
    if (!comment) return;
    setPendingDecision({
      kind: 'REQUEST_WAIVER',
      requestId,
      status: 'WAIVED',
      label: 'Waive',
      comment,
    });
    setErr('');
  };

  const saveDecision = (): void => {
    if (!pendingDecision) return;
    const requestId = pendingDecision.requestId;
    void executePendingDocumentDecision(pendingDecision)
      .then(() => {
        setPendingDecision(null);
        setErr('');
        docs.reload();
        loadAttachments(requestId);
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const runRequestUpload = (
    requestId: string,
    files: File[],
    uploadIntent:
      | 'NEW_VERSION'
      | 'SEPARATE_DOCUMENT',
    allowDuplicate = false,
  ): void => {
    uploadMany(
      'document-requests',
      requestId,
      'upload',
      files,
      {
        source: 'CLIENT',
        upload_intent: uploadIntent,
        allow_duplicate:
          allowDuplicate ? 'true' : 'false',
      },
    )
      .then(() => {
        setDuplicateUpload(null);
        setErr('');
        docs.reload();
        loadAttachments(requestId);
      })
      .catch((error: unknown) => {
        if (
          error instanceof ApiRequestError &&
          error.status === 409 &&
          error.payload?.code ===
            'DUPLICATE_ATTACHMENT'
        ) {
          const existing =
            error.payload.existing_attachment;

          setDuplicateUpload({
            requestId,
            files,
            existingAttachment:
              existing &&
              typeof existing === 'object' &&
              !Array.isArray(existing)
                ? (existing as Row)
                : null,
          });

          setErr('');
          return;
        }

        setErr(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        );
      });
  };

  const uploadRequestFiles = (
    row: Row,
    files: FileList | null,
  ): void => {
    if (!files?.length) return;

    const requestId = String(row.id);

    runRequestUpload(
      requestId,
      Array.from(files),
      uploadIntentByRequest[requestId] ||
        'NEW_VERSION',
    );
  };

  const resolveAttachmentDuplicate = (
    attachment: Row,
    resolution: DuplicateResolution,
  ): void => {
    const requestId = String(
      attachment.document_request_id,
    );

    act(
      'document-attachments',
      String(attachment.id),
      'resolve-duplicate',
      { resolution },
    )
      .then(() => {
        setErr('');
        docs.reload();
        loadAttachments(requestId);
      })
      .catch((error: unknown) =>
        setErr(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        ),
      );
  };

  const markCanonicalAttachment = (
    attachment: Row,
  ): void => {
    const requestId = String(
      attachment.document_request_id,
    );

    act(
      'document-attachments',
      String(attachment.id),
      'mark-canonical',
    )
      .then(() => {
        setErr('');
        loadAttachments(requestId);
      })
      .catch((error: unknown) =>
        setErr(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        ),
      );
  };

  const uploadInternal = (files: FileList | null): void => {
    if (!files?.length) return;
    uploadMany('work-items', workItemId, 'upload_internal', Array.from(files))
      .then(() => internalFiles.reload())
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  return (
    <div>
      <ErrorBar
        error={
          docs.error ||
          contacts.error ||
          internalFiles.error ||
          err
        }
      />

      {duplicateUpload ? (
        <section className="cx-upload-conflict">
          <div>
            <span className="cx-readiness-eyebrow">
              Duplicate file detected
            </span>

            <strong>
              This exact file already exists.
            </strong>

            <p>
              {duplicateUpload.existingAttachment
                ? `Existing file: ${String(
                    duplicateUpload.existingAttachment
                      .original_name ||
                      'Earlier upload',
                  )} Ã‚Â· ${String(
                    duplicateUpload.existingAttachment
                      .version_label ||
                      `V${String(
                        duplicateUpload
                          .existingAttachment
                          .version_number || 1,
                      )}`,
                  )}`
                : 'The uploaded content matches an earlier attachment.'}
            </p>
          </div>

          <div className="cx-upload-conflict-actions">
            <button
              type="button"
              className="cx-btn subtle"
              onClick={() =>
                setDuplicateUpload(null)
              }
            >
              Cancel
            </button>

            <button
              type="button"
              className="cx-btn"
              onClick={() =>
                runRequestUpload(
                  duplicateUpload.requestId,
                  duplicateUpload.files,
                  'NEW_VERSION',
                  true,
                )
              }
            >
              Upload as version
            </button>
          </div>
        </section>
      ) : null}
      <div className="cx-subhead"><h4>Internal work documents</h4>{canUploadInternal ? (<label className="cx-btn subtle" style={{ cursor: 'pointer' }}>Upload files<input type="file" multiple style={{ display: 'none' }} onChange={(e) => uploadInternal(e.target.files)} /></label>) : (<span className="cx-readonly-note">Upload locked at this stage</span>)}</div>
      <AttachmentList rows={internalFiles.rows.filter((a) => !a.document_request_id)} />
      <section
        className={`cx-readiness-card cx-operator-readiness ${readinessTone}`}
        aria-label="Document progress"
      >
        <div className="cx-readiness-score">
          <div
            className="cx-readiness-ring"
            style={{
              background: `conic-gradient(
                currentColor ${readiness.healthScore}%,
                #e5eaf0 ${readiness.healthScore}% 100%
              )`,
            }}
          >
            <span>{readiness.healthScore}%</span>
          </div>

          <div>
            <span className="cx-readiness-eyebrow">
              Document progress
            </span>
            <strong>
              {readinessStateText(readiness.state)}
            </strong>
            <p>
              {readiness.ready
                ? 'All mandatory document dependencies are satisfied.'
                : `${readiness.mandatoryMissing} mandatory document${
                    readiness.mandatoryMissing === 1 ? '' : 's'
                  } still block review.`}
            </p>
          </div>
        </div>

        <div className="cx-readiness-metrics">
          <div>
            <strong>
              {readiness.mandatorySatisfied}/
              {readiness.mandatoryTotal}
            </strong>
            <span>Required complete</span>
          </div>

          <div>
            <strong>
              {readiness.satisfiedDocuments}/
              {readiness.totalDocuments}
            </strong>
            <span>Complete</span>
          </div>

          <div>
            <strong>{readiness.mandatoryMissing}</strong>
            <span>Still needed</span>
          </div>
        </div>

        {!readiness.ready && readiness.blockers.length > 0 ? (
          <div className="cx-readiness-blockers">
            <div className="cx-readiness-blockers-title">
              <strong>Still needed</strong>
              <span>
                Complete these items before review.
              </span>
            </div>

            <div className="cx-readiness-blocker-list">
              {readiness.blockers.map((blocker) => (
                <div
                  className="cx-readiness-blocker"
                  key={String(blocker.id)}
                >
                  <div>
                    <strong>{String(blocker.name)}</strong>
                    <span>
                      {label(
                        String(blocker.category || 'OTHER'),
                      )}
                    </span>
                  </div>

                  <Chip
                    value={documentDependencyReason(blocker)}
                    tone={
                      blocker.is_expired === true ||
                      String(blocker.status) === 'REJECTED'
                        ? 'danger'
                        : 'warn'
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="cx-document-action-queue cx-operator-duplicate">
        <div className="cx-document-action-head">
          <div>
            <span className="cx-readiness-eyebrow">
              Operational queue
            </span>
            <h4>Document actions requiring attention</h4>
            <p>
              Prioritised from critical expiry and rejection
              issues through client follow-up.
            </p>
          </div>

          <strong>
            {documentActionQueue.length}
          </strong>
        </div>

        <div className="cx-document-action-summary">
          <div
            className={
              actionQueueCounts.expired > 0
                ? 'danger'
                : ''
            }
          >
            <strong>{actionQueueCounts.expired}</strong>
            <span>Expired</span>
          </div>

          <div
            className={
              actionQueueCounts.expiring > 0
                ? 'warn'
                : ''
            }
          >
            <strong>{actionQueueCounts.expiring}</strong>
            <span>Expiring soon</span>
          </div>

          <div
            className={
              actionQueueCounts.rejected > 0
                ? 'danger'
                : ''
            }
          >
            <strong>{actionQueueCounts.rejected}</strong>
            <span>Rejected</span>
          </div>

          <div
            className={
              actionQueueCounts.review > 0
                ? 'warn'
                : ''
            }
          >
            <strong>{actionQueueCounts.review}</strong>
            <span>Review pending</span>
          </div>

          <div
            className={
              actionQueueCounts.client > 0
                ? 'warn'
                : ''
            }
          >
            <strong>{actionQueueCounts.client}</strong>
            <span>Client follow-up</span>
          </div>
        </div>

        {documentActionQueue.length > 0 ? (
          <div className="cx-document-action-list">
            {documentActionQueue.map((item) => (
              <button
                type="button"
                className={`cx-document-action-row ${
                  item.kind.toLowerCase()
                }`}
                key={item.id}
                onClick={() => {
                  const element = document.getElementById(
                    `document-request-${String(
                      item.document.id,
                    )}`,
                  );

                  element?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                  });
                }}
              >
                <div className="cx-document-action-marker">
                  {documentQueueLabel(item.kind).slice(0, 1)}
                </div>

                <div className="cx-document-action-main">
                  <strong>{item.name}</strong>
                  <span>{item.message}</span>
                </div>

                <div className="cx-document-action-meta">
                  <span>{label(item.category)}</span>
                  <Chip
                    value={documentQueueLabel(item.kind)}
                    tone={documentQueueTone(item.kind)}
                  />
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="cx-document-action-empty">
            No document action is currently required.
          </div>
        )}
      </section>

      <div className="cx-subhead" style={{ marginTop: 18 }}>
        <div>
          <h4>Documents</h4>
          <span className="cx-muted">
            Documents needed to complete this work
          </span>
        </div>

        <button
          type="button"
          className="cx-btn subtle"
          onClick={() =>
            setEditing({
              name: '',
              status: 'REQUESTED',
              category: 'OTHER',
              financial_year: '',
              assessment_year: '',
              filing_period: '',
              valid_from: '',
              expires_on: '',
              mandatory: false,
              client_visible: true,
              request_channel: 'WHATSAPP',
              requested_from_contact_id:
                eligibleContacts.find((c) => c.is_primary)?.id ?? '',
            })
          }
        >
          Add request
        </button>
      </div>

      <div className="cx-document-summary">
        <div>
          <strong>{documentSummary.total}</strong>
          <span>Total requests</span>
        </div>
        <div>
          <strong>{documentSummary.accepted}</strong>
          <span>Accepted</span>
        </div>
        <div className={documentSummary.pendingReview ? 'warn' : ''}>
          <strong>{documentSummary.pendingReview}</strong>
          <span>Pending review</span>
        </div>
        <div className={documentSummary.mandatoryPending ? 'warn' : ''}>
          <strong>{documentSummary.mandatoryPending}</strong>
          <span>Mandatory pending</span>
        </div>
        <div className={documentSummary.expired ? 'danger' : ''}>
          <strong>{documentSummary.expired}</strong>
          <span>Expired</span>
        </div>
      </div>
      {eligibleContacts.length === 0 ? (
        <p className="cx-warning">
          No eligible document contact exists for this client. Add or enable one under Client Ã¢â€ â€™ Contacts.
        </p>
      ) : null}
      {docs.loading ? <Loading /> : docs.rows.length === 0 ? <p style={{ color: '#64748b', fontSize: 13 }}>No documents requested yet.</p> : docs.rows.map((d) => (
        <div
          id={`document-request-${String(d.id)}`}
          className={`cx-doc-card${d.is_expired === true ? ' expired' : ''}`}
          key={String(d.id)}
        >
          <div className="cx-document-request-head">
            <div>
              <div className="cx-document-title-row">
                <strong>{String(d.name)}</strong>
                <Chip
                  value={String(d.status)}
                  tone={statusTone(String(d.status))}
                />
                <Chip
                  value={String(d.category || 'OTHER')}
                  tone="muted"
                />
                {d.mandatory ? (
                  <span className="cx-mandatory-badge">Mandatory</span>
                ) : null}
              </div>

              <div className="cx-document-metadata">
                <span>
                  Requested from {String(d.requested_from_name || 'Unassigned')}
                </span>
                <span>via {label(String(d.request_channel))}</span>
                {d.financial_year ? (
                  <span>FY {String(d.financial_year)}</span>
                ) : null}
                {d.assessment_year ? (
                  <span>AY {String(d.assessment_year)}</span>
                ) : null}
                {d.filing_period ? (
                  <span>{String(d.filing_period)}</span>
                ) : null}
                {d.due_date ? (
                  <span>Due {String(d.due_date)}</span>
                ) : null}
              </div>
            </div>

            {(() => {
              const visualState =
                checklistVisualState(d);

              return (
                <div
                  className={
                    `cx-checklist-state ${
                      visualState.tone
                    }`
                  }
                  data-state={visualState.key}
                >
                  <span
                    className="cx-checklist-state-icon"
                    aria-hidden="true"
                  >
                    {visualState.key === 'RECEIVED'
                      ? 'Ã¢Å“â€œ'
                      : visualState.key === 'REJECTED'
                        ? '!'
                        : visualState.key ===
                            'PENDING_REVIEW'
                          ? 'Ã¢â‚¬Â¦'
                          : 'Ã¢â€”â€¹'}
                  </span>

                  <span>
                    {visualState.label}
                  </span>
                </div>
              );
            })()}

            <Chip
              value={expiryText(d)}
              tone={documentExpiryTone(d)}
            />
          </div>

          <div className="cx-document-intelligence-strip">
            <span>
              <strong>{Number(d.attachment_count ?? 0)}</strong>
              {' '}file{Number(d.attachment_count ?? 0) === 1 ? '' : 's'}
            </span>
            <span>
              <strong>{Number(d.accepted_attachment_count ?? 0)}</strong>
              {' '}accepted
            </span>
            <span>
              <strong>{Number(d.pending_review_count ?? 0)}</strong>
              {' '}pending review
            </span>
            <span>
              Latest version <strong>V{Number(d.latest_version ?? 0)}</strong>
            </span>
          </div>

          <div className="cx-doc-actions">
            <div className="cx-version-upload-control">
              <select
                aria-label={`Upload intent for ${String(
                  d.name,
                )}`}
                value={
                  uploadIntentByRequest[String(d.id)] ||
                  'NEW_VERSION'
                }
                onChange={(event) =>
                  setUploadIntentByRequest(
                    (current) => ({
                      ...current,
                      [String(d.id)]:
                        event.target.value as
                          | 'NEW_VERSION'
                          | 'SEPARATE_DOCUMENT',
                    }),
                  )
                }
              >
                <option value="NEW_VERSION">
                  Upload as new version
                </option>

                <option value="SEPARATE_DOCUMENT">
                  Upload as separate document
                </option>
              </select>

              <label
                className="cx-btn subtle"
                style={{ cursor: 'pointer' }}
              >
                Upload files

                <input
                  type="file"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(event) => {
                    uploadRequestFiles(
                      d,
                      event.target.files,
                    );

                    event.target.value = '';
                  }}
                />
              </label>
            </div>
            <button className="cx-btn subtle" onClick={() => selectWaiver(d)}>Waive request</button>
          </div>
          {pendingDecision?.requestId === String(d.id) ? (
            <div className="cx-warning" role="status" style={{ marginTop: 10 }}>
              Pending review decision: <strong>{pendingDecision.label}</strong>. This will run only when you save.
              <div className="cx-doc-actions" style={{ marginTop: 8 }}>
                <button type="button" className="cx-btn subtle" onClick={() => setPendingDecision(null)}>Cancel</button>
                <button type="button" className="cx-btn" onClick={saveDecision}>Save &amp; {pendingDecision.label}</button>
              </div>
            </div>
          ) : null}
          <AttachmentList
            rows={attachments[String(d.id)] ?? []}
            pendingDecision={pendingDecision}
            onSelectReview={selectAttachmentDecision}
            onResolveDuplicate={
              workItem.can_review === true
                ? resolveAttachmentDuplicate
                : undefined
            }
            onMarkCanonical={
              workItem.can_review === true
                ? markCanonicalAttachment
                : undefined
            }
            canOperateVersions={
              workItem.can_review === true
            }
          />
        </div>
      ))}
      {editing && (
        <Drawer
          title="New document request"
          value={editing}
          onChange={setEditing}
          onClose={() => setEditing(null)}
          onSave={submit}
          extra={<ErrorBar error={err} />}
          fields={[
            { name: 'name' },
            {
              name: 'category',
              kind: 'select',
              options: DOCUMENT_CATEGORIES,
            },
            { name: 'description', kind: 'textarea' },
            {
              name: 'requested_from_contact_id',
              kind: 'select',
              options: eligibleContacts.map((c) => String(c.id)),
              labels: (value) =>
                String(
                  eligibleContacts.find((contact) => contact.id === value)?.name ??
                    value,
                ),
            },
            {
              name: 'request_channel',
              kind: 'select',
              options: ['WHATSAPP', 'EMAIL', 'PORTAL', 'PHONE', 'MANUAL'],
            },
            { name: 'financial_year' },
            { name: 'assessment_year' },
            { name: 'filing_period' },
            { name: 'due_date', kind: 'date' },
            { name: 'valid_from', kind: 'date' },
            { name: 'expires_on', kind: 'date' },
            { name: 'mandatory', kind: 'checkbox' },
            { name: 'client_visible', kind: 'checkbox' },
            { name: 'remarks', kind: 'textarea' },
          ]}
        />
      )}
    </div>
  );
}

export function TimelinePanel({
  workItemId,
}: {
  workItemId: string;
}): React.JSX.Element {
  const [events, setEvents] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    setLoading(true);
    setError('');

    void list(
      `work-items/${workItemId}/history`,
    )
      .then((rows) => {
        if (!active) return;
        setEvents(rows);
      })
      .catch((reason: unknown) => {
        if (!active) return;

        setError(
          String(
            reason instanceof Error
              ? reason.message
              : reason,
          ),
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [
    workItemId,
  ]);

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return <ErrorBar error={error} />;
  }

  if (events.length === 0) {
    return (
      <p className="cx-timeline-empty">
        No timeline events yet.
      </p>
    );
  }

  return (
    <section
      className="cx-work-timeline"
      aria-label="Work Timeline"
    >
      {events.map((event) => {
        const when = String(
          event.created_at ?? '',
        )
          .slice(0, 16)
          .replace('T', ' ');

        const actor = String(
          event.actor_name ?? '',
        );

        const entry = String(
          event.entry ?? '',
        );

        const detail = String(
          event.detail ?? '',
        );

        const fromStatus = String(
          event.from_status ?? '',
        );

        const toStatus = String(
          event.to_status ?? '',
        );

        return (
          <article
            className="cx-work-timeline-event"
            key={String(event.id)}
          >
            <div
              className="cx-work-timeline-marker"
              aria-hidden="true"
            />

            <div className="cx-work-timeline-time">
              {when}
            </div>

            <div className="cx-work-timeline-content">
              <div className="cx-work-timeline-title">
                <strong>
                  {String(
                    event.title
                    || label(
                      String(
                        event.event_type
                        || 'EVENT',
                      ),
                    ),
                  )}
                </strong>

                {event.event_type ? (
                  <span>
                    {label(
                      String(event.event_type),
                    )}
                  </span>
                ) : null}
              </div>

              {entry ? (
                <p>{entry}</p>
              ) : null}

              {detail ? (
                <small>{detail}</small>
              ) : null}

              {fromStatus && toStatus ? (
                <small>
                  {label(fromStatus)}
                  {' â†’ '}
                  {label(toStatus)}
                </small>
              ) : null}

              {actor ? (
                <small>
                  By {actor}
                </small>
              ) : null}
            </div>
          </article>
        );
      })}
    </section>
  );
}


export type PendingWorkAction =
  | { kind: 'START_WORK'; label: 'Start Work' }
  | { kind: 'SUBMIT_FOR_REVIEW'; label: 'Submit for review' }
  | { kind: 'RESUME_WORK'; label: 'Resume Work' }
  | { kind: 'APPROVE'; label: 'Approve & complete' }
  | { kind: 'RETURN_FOR_REWORK'; label: 'Return for rework'; comment: string };

function cleanWorkItemPayload(editing: Row): Row {
  const body: Row = {};
  for (const [k, v] of Object.entries(editing)) {
    if (
      v !== '' &&
      !['client_name', 'service_name', 'owner_name', 'reviewer_name', 'is_overdue'].includes(k)
    ) {
      body[k] = v;
    }
  }
  return body;
}

export async function executePendingWorkAction(
  workItemId: string,
  pendingAction: PendingWorkAction,
): Promise<Row> {
  if (pendingAction.kind === 'START_WORK' || pendingAction.kind === 'RESUME_WORK') {
    return act('work-items', workItemId, 'set_status', { status: 'IN_PROGRESS' });
  }
  if (pendingAction.kind === 'SUBMIT_FOR_REVIEW') {
    return act('work-items', workItemId, 'submit_for_review');
  }
  if (pendingAction.kind === 'APPROVE') {
    return act('work-items', workItemId, 'approve');
  }
  return act('work-items', workItemId, 'return_for_rework', { comment: pendingAction.comment });
}

export async function persistWorkItem(
  editing: Row,
  closeDrawer: () => void,
  setError: (message: string) => void,
  reload: () => void,
  pendingAction: PendingWorkAction | null = null,
): Promise<void> {
  try {
    const saved = await save('work-items', cleanWorkItemPayload(editing));
    const workItemId = String(saved.id ?? editing.id ?? '');

    if (pendingAction) {
      if (!workItemId) throw new Error('Save the work item before applying a workflow action.');
      await executePendingWorkAction(workItemId, pendingAction);
    }

    setError('');
    closeDrawer();
    reload();
  } catch (e: unknown) {
    setError(String(e instanceof Error ? e.message : e));
  }
}

export type WorkPrimaryAction = 'SUBMIT_FOR_REVIEW' | 'RESUME_WORK' | null;

export function workPrimaryAction(status: unknown): WorkPrimaryAction {
  const value = String(status);
  if (value === 'IN_PROGRESS') return 'SUBMIT_FOR_REVIEW';
  if (value === 'REWORK_REQUIRED') return 'RESUME_WORK';
  return null;
}


export function WorkCatalogueCascade({
  verticalRows,
  domainRows,
  serviceRows,
  selectedVerticalId,
  selectedDomainId,
  selectedServiceId,
  disabled = false,
  onVerticalChange,
  onDomainChange,
  onServiceChange,
}: {
  verticalRows: Row[];
  domainRows: Row[];
  serviceRows: Row[];
  selectedVerticalId: string;
  selectedDomainId: string;
  selectedServiceId: string;
  disabled?: boolean;
  onVerticalChange: (value: string) => void;
  onDomainChange: (value: string) => void;
  onServiceChange: (value: string) => void;
}): React.JSX.Element {
  const availableVerticals = verticalRows
    .filter(
      (row) =>
        row.status === 'ACTIVE' ||
        String(row.id) === selectedVerticalId,
    )
    .sort((left, right) =>
      String(left.name).localeCompare(
        String(right.name),
      ),
    );

  const availableDomains = domainRows
    .filter(
      (row) =>
        String(row.vertical_id) ===
          selectedVerticalId &&
        (
          row.status === 'ACTIVE' ||
          String(row.id) === selectedDomainId
        ),
    )
    .sort((left, right) =>
      String(left.name).localeCompare(
        String(right.name),
      ),
    );

  const availableServices = serviceRows
    .filter(
      (row) =>
        String(row.domain_id) ===
          selectedDomainId &&
        (
          row.status === 'ACTIVE' ||
          String(row.id) === selectedServiceId
        ),
    )
    .sort((left, right) =>
      String(left.name).localeCompare(
        String(right.name),
      ),
    );

  return (
    <section
      className="cx-operational-fields"
      aria-label="Service classification"
    >
      <div className="cx-operational-fields-heading">
        <div>
          <h4>Service classification</h4>
          <p>
            Select the Vridhi vertical, domain and
            service for this work item.
          </p>
        </div>
      </div>

      <div className="cx-operational-fields-grid">
        <div className="cx-field">
          <label htmlFor="work-vertical">
            Vertical
          </label>

          <select
            id="work-vertical"
            value={selectedVerticalId}
            disabled={disabled}
            onChange={(event) =>
              onVerticalChange(
                event.target.value,
              )
            }
          >
            <option value="">
              Select vertical
            </option>

            {availableVerticals.map((row) => (
              <option
                key={String(row.id)}
                value={String(row.id)}
              >
                {String(row.name)}
              </option>
            ))}
          </select>
        </div>

        <div className="cx-field">
          <label htmlFor="work-domain">
            Domain
          </label>

          <select
            id="work-domain"
            value={selectedDomainId}
            disabled={
              disabled ||
              !selectedVerticalId
            }
            onChange={(event) =>
              onDomainChange(
                event.target.value,
              )
            }
          >
            <option value="">
              {selectedVerticalId
                ? 'Select domain'
                : 'Select vertical first'}
            </option>

            {availableDomains.map((row) => (
              <option
                key={String(row.id)}
                value={String(row.id)}
              >
                {String(row.name)}
              </option>
            ))}
          </select>
        </div>

        <div className="cx-field">
          <label htmlFor="work-service">
            Service
          </label>

          <select
            id="work-service"
            value={selectedServiceId}
            disabled={
              disabled ||
              !selectedDomainId
            }
            onChange={(event) =>
              onServiceChange(
                event.target.value,
              )
            }
          >
            <option value="">
              {selectedDomainId
                ? 'Select service'
                : 'Select domain first'}
            </option>

            {availableServices.map((row) => (
              <option
                key={String(row.id)}
                value={String(row.id)}
              >
                {String(row.name)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </section>
  );
}


export function WorkArea({
  initialWorkItemId,
  onInitialWorkOpened,
  initialQuickAction,
  onInitialQuickActionHandled,
}: {
  initialWorkItemId?: string | undefined;
  onInitialWorkOpened?: () => void;
  initialQuickAction?:
    | 'create'
    | 'documents'
    | undefined;
  onInitialQuickActionHandled?: () => void;
} = {}): React.JSX.Element {
  const clients = useList('clients');
  const verticals = useList('verticals');
  const domains = useList('domains');
  const services = useList('services');
  const employees = useList('employees');
  const [statusFilter, setStatusFilter] = useState('');
  const params = useMemo(() => (statusFilter ? { status: statusFilter } : {}), [statusFilter]);
  const work = useList('work-items', params);
  const [editing, setEditing] = useState<Row | null>(null);

  const [
    workHealth,
    setWorkHealth,
  ] = useState<WorkHealthSnapshot | null>(
    null,
  );

  const [
    workHealthLoading,
    setWorkHealthLoading,
  ] = useState(false);

  const [
    workHealthError,
    setWorkHealthError,
  ] = useState('');

  const [selectedVerticalId, setSelectedVerticalId] =
    useState('');
  const [selectedDomainId, setSelectedDomainId] =
    useState('');

  const selectedServiceId = String(
    editing?.service_id ?? '',
  );

  const operationalFields = useList(
    'service-operational-fields',
    selectedServiceId
      ? {
          service_id: selectedServiceId,
          is_active: 'true',
        }
      : {
          service_id: '__none__',
        },
  );

  useEffect(() => {
    if (!selectedServiceId) return;

    const service = services.rows.find(
      (row) =>
        String(row.id) === selectedServiceId,
    );

    if (!service?.domain_id) return;

    const domainId = String(service.domain_id);

    const domain = domains.rows.find(
      (row) =>
        String(row.id) === domainId,
    );

    if (!domain?.vertical_id) return;

    setSelectedDomainId(domainId);
    setSelectedVerticalId(
      String(domain.vertical_id),
    );
  }, [
    selectedServiceId,
    services.rows,
    domains.rows,
  ]);

  const updateWorkField = (
    name: string,
    value: unknown,
  ): void => {
    setEditing((current) => {
      if (!current) return current;

      if (name === 'service_id') {
        return {
          ...current,
          service_id: value,
          operational_data: {},
        };
      }

      return {
        ...current,
        [name]: value,
      };
    });
  };

  const updateOperationalField = (
    key: string,
    value: unknown,
  ): void => {
    setEditing((current) => {
      if (!current) return current;

      const existing =
        current.operational_data &&
        typeof current.operational_data ===
          'object' &&
        !Array.isArray(
          current.operational_data,
        )
          ? current.operational_data as Row
          : {};

      return {
        ...current,
        operational_data: {
          ...existing,
          [key]: value,
        },
      };
    });
  };

  const [err, setErr] = useState('');
  const [tab, setTab] = useState<'details' | 'assignment' | 'documents' | 'qa' | 'history'>('details');
  const [pendingAction, setPendingAction] = useState<PendingWorkAction | null>(null);

  const [
    documentSelectionMode,
    setDocumentSelectionMode,
  ] = useState(false);

  useEffect(() => {
    if (!initialQuickAction) return;

    setPendingAction(null);
    setErr('');

    if (initialQuickAction === 'create') {
      // Same state as the existing Add Work Item button.
      setDocumentSelectionMode(false);
      setEditing({
        title: '',
        priority: 'NORMAL',
        status: 'NOT_STARTED',
      });
      setTab('details');
    } else {
      // Documents remain contextual to Work. Select existing Work first,
      // then enter its certified Documents workspace.
      setDocumentSelectionMode(true);
      setEditing(null);
      setTab('details');
    }

    onInitialQuickActionHandled?.();
  }, [
    initialQuickAction,
  ]);

  useEffect(() => {
    if (!initialWorkItemId) return;

    let active = true;

    setErr('');

    void getObject(
      `work-items/${initialWorkItemId}`,
    )
      .then((row) => {
        if (!active) return;

        // Reuse the same workspace state as opening a Work table row.
        setDocumentSelectionMode(false);
        setEditing({ ...row });
        setPendingAction(null);
        setTab('details');
        setErr('');

        onInitialWorkOpened?.();
      })
      .catch((error: unknown) => {
        if (!active) return;

        setErr(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        );

        onInitialWorkOpened?.();
      });

    return () => {
      active = false;
    };
  }, [
    initialWorkItemId,
  ]);

  const loadWorkHealth = (): void => {
    const workItemId =
      String(
        editing?.id ?? '',
      );

    if (!workItemId) {
      setWorkHealth(null);
      setWorkHealthLoading(false);
      setWorkHealthError('');
      return;
    }

    setWorkHealthLoading(true);

    void getObject(
      `work-items/${workItemId}/health`,
    )
      .then((snapshot) => {
        setWorkHealth(
          isWorkHealthSnapshot(snapshot)
          ? snapshot
          : null,
        );

        setWorkHealthError('');
      })
      .catch((error: unknown) => {
        setWorkHealth(null);

        setWorkHealthError(
          String(
            error instanceof Error
              ? error.message
              : error,
          ),
        );
      })
      .finally(() => {
        setWorkHealthLoading(false);
      });
  };

  useEffect(() => {
    loadWorkHealth();
  }, [
    editing?.id,
    tab,
  ]);


  const closeWorkDrawer = (): void => {
    setWorkHealth(null);
    setWorkHealthError('');

    setPendingAction(null);
    setSelectedVerticalId('');
    setSelectedDomainId('');
    setEditing(null);
  };

  const selectPendingAction = (action: PendingWorkAction): void => {
    setPendingAction((current) => (current?.kind === action.kind ? null : action));
    setErr('');
  };

  const submit = (): void => {
    if (!editing) return;
    void persistWorkItem(editing, closeWorkDrawer, setErr, work.reload, pendingAction);
  };

  const actionButton = (
    action: PendingWorkAction,
    className = 'cx-btn',
  ): React.JSX.Element => {
    const selected = pendingAction?.kind === action.kind;
    return (
      <button
        type="button"
        className={`${className}${selected ? ' pending' : ''}`}
        aria-pressed={selected}
        onClick={() => selectPendingAction(action)}
      >
        {selected ? `v ${action.label} selected` : action.label}
      </button>
    );
  };

  const reviewButtons = (row: Row): React.JSX.Element | null => {
    const action = workPrimaryAction(row.status);
    // C4: reflect backend permission flags, never status alone.
    const canSubmit = row.can_submit_for_review === true;
    const canReview = row.can_review === true;
    if (action === 'SUBMIT_FOR_REVIEW' && canSubmit) {
      return actionButton({ kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' });
    }
    if (action === 'RESUME_WORK' && row.can_edit === true) {
      return actionButton({ kind: 'RESUME_WORK', label: 'Resume Work' });
    }
    const s = String(row.status);
    if (s === 'READY_FOR_REVIEW' && canReview) {
      return (
        <div style={{ display: 'flex', gap: 6 }}>
          {actionButton({ kind: 'APPROVE', label: 'Approve & complete' })}
          <button
            type="button"
            className={`cx-btn danger${pendingAction?.kind === 'RETURN_FOR_REWORK' ? ' pending' : ''}`}
            aria-pressed={pendingAction?.kind === 'RETURN_FOR_REWORK'}
            onClick={() => {
              if (pendingAction?.kind === 'RETURN_FOR_REWORK') {
                setPendingAction(null);
                return;
              }
              const comment = window.prompt('Reason for rework?') ?? '';
              if (comment.trim()) {
                selectPendingAction({
                  kind: 'RETURN_FOR_REWORK',
                  label: 'Return for rework',
                  comment: comment.trim(),
                });
              }
            }}
          >
            {pendingAction?.kind === 'RETURN_FOR_REWORK'
              ? 'v Return for rework selected'
              : 'Return for rework'}
          </button>
        </div>
      );
    }
    if (s === 'NOT_STARTED') {
      return actionButton({ kind: 'START_WORK', label: 'Start Work' });
    }
    return null;
  };

  const fields: Field[] = [
    { name: 'title' },
    { name: 'client_id', kind: 'select', options: clients.rows.map((c) => String(c.id)), labels: (v) => String(clients.rows.find((c) => c.id === v)?.trade_name || clients.rows.find((c) => c.id === v)?.legal_name || v) },
    { name: 'owner_user_id', kind: 'select', options: employees.rows.filter((e) => e.is_active).map((e) => String(e.id)), labels: (v) => String(employees.rows.find((e) => e.id === v)?.name ?? v) },
    { name: 'reviewer_user_id', kind: 'select', options: employees.rows.filter((e) => e.is_active).map((e) => String(e.id)), labels: (v) => String(employees.rows.find((e) => e.id === v)?.name ?? v) },
    { name: 'period' },
    { name: 'due_date', kind: 'date' },
    { name: 'priority', kind: 'select', options: WORK_PRIORITY },
    { name: 'description', kind: 'textarea' },
  ];

  return (
    <>
      <div className="cx-toolbar">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {WORK_STATUS.map((s) => <option key={s} value={s}>{label(s)}</option>)}
        </select>
        <div className="cx-spacer" />
        <button className="cx-btn" onClick={() => { setDocumentSelectionMode(false); setEditing({ title: '', priority: 'NORMAL', status: 'NOT_STARTED' }); setPendingAction(null); setTab('details'); setErr(''); }}>Add Work Item</button>
      </div>
      <ErrorBar error={work.error} />

      {documentSelectionMode ? (
        <div
          className="cx-notice"
          role="status"
        >
          Select a Work Item to upload a client document.
        </div>
      ) : null}

      {!work.loading && !documentSelectionMode ? (
        <QAOperationalQueue
          workRows={work.rows}
          onOpen={(row) => {
            setEditing({ ...row });
            setTab('qa');
            setErr('');
          }}
        />
      ) : null}
      {work.loading ? (
        <Loading />
      ) : (
        <DataTable
          empty="No work items yet. Create one to start tracking client work."
          onRow={(r) => {
            setEditing({ ...r });
            setPendingAction(null);
            setTab(
              documentSelectionMode
                ? 'documents'
                : 'details',
            );
            setDocumentSelectionMode(false);
            setErr('');
          }}
          columns={[
            { key: 'title', header: 'Title' },
            { key: 'client_name', header: 'Client', render: (r) => String(r.client_name || '""') },
            { key: 'service_name', header: 'Service', render: (r) => String(r.service_name || '""') },
            { key: 'owner_name', header: 'Owner', render: (r) => String(r.owner_name || '""') },
            { key: 'due_date', header: 'Due', render: (r) => (r.due_date ? <span className={isOverdue(r.due_date, r.status) ? 'cx-overdue' : ''}>{String(r.due_date)}</span> : '""') },
            {
              key: 'document_health_score',
              header: 'Docs',
              render: (r) => {
                const score = Number(
                  r.document_health_score ?? 100,
                );

                return (
                  <span
                    className={`cx-readiness-table-score ${
                      r.document_ready === true
                        ? 'ready'
                        : score >= 70
                          ? 'attention'
                          : 'blocked'
                    }`}
                    title={readinessStateText(
                      String(r.document_readiness_state || ''),
                    )}
                  >
                    {score}%
                  </span>
                );
              },
            },
            { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} tone={statusTone(String(r.status))} /> },
          ]}
          rows={work.rows}
        />
      )}
      {editing && (
        <div className="cx-workspace-backdrop" onClick={closeWorkDrawer}>
          <div className="cx-workspace-page" onClick={(e) => e.stopPropagation()}>
            <h3>{editing.id ? String(editing.title) : 'New Work Item'}</h3>

            {editing.id ? (
              <WorkHealthCard
                health={workHealth}
                loading={
                  workHealthLoading
                }
                error={
                  workHealthError
                }
              />
            ) : null}

            {editing.id ? (
              <div className="cx-toolbar" style={{ marginBottom: 12 }}>
                {(['details', 'assignment', 'documents', 'qa', 'history'] as const).map((t) => (
                  <button
                    key={t}
                    className={`cx-btn ${t === tab ? '' : 'subtle'}`}
                    onClick={() => setTab(t)}
                  >
                    {t === 'history' ? 'Timeline' : label(t)}
                  </button>
                ))}
              </div>
            ) : null}
            <ErrorBar error={err} />
            {tab === 'details' && (
              <>
                {editing.id ? (
                  <div style={{ marginBottom: 12 }}>
                    <Chip value={String(editing.status)} tone={statusTone(String(editing.status))} />
                    {editing.current_controller_name ? (
                      <span className="cx-controller"> Controller: {String(editing.current_controller_name)}</span>
                    ) : null}
                    {' '}{reviewButtons(editing)}
                  </div>
                ) : null}
                {editing.id && editing.is_locked === true ? (
                  <div className="cx-lock-banner" role="status">
                    {lockMessage(editing.status, editing.current_controller_name)}
                  </div>
                ) : null}
                {pendingAction ? (
                  <div className="cx-warning" role="status" style={{ marginBottom: 12 }}>
                    Pending workflow action: <strong>{pendingAction.label}</strong>. This will run only when you save.
                  </div>
                ) : null}
                {fields.map((f) => (
                  <div className="cx-field" key={f.name}>
                    <label>{label(f.name.replace(/_id$/, '').replace(/_user$/, ''))}</label>
                    {f.kind === 'textarea' ? (
                      <textarea value={String(editing[f.name] ?? '')} onChange={(e) => updateWorkField(f.name, e.target.value)} />
                    ) : f.kind === 'select' ? (
                      <select value={String(editing[f.name] ?? '')} onChange={(e) => updateWorkField(f.name, e.target.value)}>
                        <option value="">""</option>
                        {(f.options ?? []).map((o) => <option key={o} value={o}>{f.labels ? f.labels(o) : label(o)}</option>)}
                      </select>
                    ) : (
                      <input type={f.kind === 'date' ? 'date' : 'text'} value={String(editing[f.name] ?? '')} onChange={(e) => updateWorkField(f.name, e.target.value)} />
                    )}
                  </div>
                ))}

                <WorkCatalogueCascade
                  verticalRows={verticals.rows}
                  domainRows={domains.rows}
                  serviceRows={services.rows}
                  selectedVerticalId={
                    selectedVerticalId
                  }
                  selectedDomainId={
                    selectedDomainId
                  }
                  selectedServiceId={
                    selectedServiceId
                  }
                  disabled={
                    editing.id
                      ? editing.can_edit !== true
                      : false
                  }
                  onVerticalChange={(value) => {
                    setSelectedVerticalId(value);
                    setSelectedDomainId('');

                    updateWorkField(
                      'service_id',
                      '',
                    );
                  }}
                  onDomainChange={(value) => {
                    setSelectedDomainId(value);

                    updateWorkField(
                      'service_id',
                      '',
                    );
                  }}
                  onServiceChange={(value) =>
                    updateWorkField(
                      'service_id',
                      value,
                    )
                  }
                />

                {selectedServiceId ? (
                  <OperationalFieldsPanel
                    definitions={
                      operationalFields.rows as unknown as ServiceOperationalFieldDefinition[]
                    }
                    values={
                      editing.operational_data &&
                      typeof editing.operational_data ===
                        'object' &&
                      !Array.isArray(
                        editing.operational_data,
                      )
                        ? (editing.operational_data as Row)
                        : {}
                    }
                    loading={
                      operationalFields.loading
                    }
                    disabled={
                      editing.id
                        ? editing.can_edit !== true
                        : false
                    }
                    onChange={
                      updateOperationalField
                    }
                  />
                ) : (
                  <div
                    className={
                      "cx-operational-service-prompt"
                    }
                    role="note"
                  >
                    Select a service to display
                    its operational fields and
                    document checklist.
                  </div>
                )}
                <div className="cx-drawer-actions">
                  <button type="button" className="cx-btn subtle" onClick={closeWorkDrawer}>Close</button>
                  {(!editing.id || editing.can_edit === true) ? (
                    <button type="button" className="cx-btn" onClick={submit}>
                      {pendingAction ? `Save & ${pendingAction.label}` : 'Save'}
                    </button>
                  ) : (
                    <button type="button" className="cx-btn" disabled aria-disabled="true" title="Read-only at this stage">
                      Save
                    </button>
                  )}
                </div>
              </>
            )}
            {tab === 'assignment' && editing.id ? (
              <AssignmentWorkspace
                workItem={editing}
                employees={employees.rows}
                onAssigned={(result) => {
                  setEditing((current) =>
                    current
                      ? {
                          ...current,
                          owner_user_id:
                            result.owner_user_id ||
                            current.owner_user_id,
                          reviewer_user_id:
                            result.reviewer_user_id ||
                            current.reviewer_user_id,
                        }
                      : current,
                  );
                  setErr('');
                  work.reload();
                }}
              />
            ) : null}
            {tab === 'documents' && editing.id ? (
              <DocumentsPanel
                workItemId={String(editing.id)}
                clientId={String(editing.client_id)}
                canUploadInternal={
                  editing.can_upload_internal === true
                }
                workItem={editing}
              />
            ) : null}
            {tab === 'qa' && editing.id ? (
              <QAWorkspace
                workItem={editing}
                onWorkChanged={() => {
                  work.reload();
                }}
              />
            ) : null}
            {tab === 'history' && editing.id ? (
              <TimelinePanel
                workItemId={String(editing.id)}
              />
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
