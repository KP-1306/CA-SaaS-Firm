import type * as React from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';
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
          Calculating operational health…
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
            <span>·</span>
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
            } missing ·{' '}
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
                {' · '}
                {formatBytes(attachment.size_bytes)}
                {' · '}
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
      return 'Rejected • upload a corrected document';
    case 'RECEIVED':
      return 'Received • waiting for acceptance';
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
        message: 'Expired • obtain a valid replacement',
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
        message: 'Rejected • corrected document required',
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
        message: 'Uploaded • review and accept or reject',
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


export type ServiceProcessStepDefinition = {
  id: string;
  service_id: string;
  code: string;
  name: string;
  description?: string;
  display_order?: number;
  is_active?: boolean;
};

export type WorkProcessStateSnapshot = {
  work_item_id: string;
  current_step: {
    id: string;
    code: string;
    name: string;
    display_order?: number;
  } | null;
  entered_at: string | null;
  entered_by: string | null;
  note: string;
};

export function isWorkProcessStateSnapshot(
  value: unknown,
): value is WorkProcessStateSnapshot {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate =
    value as Partial<WorkProcessStateSnapshot>;

  if (typeof candidate.work_item_id !== 'string') {
    return false;
  }

  if (candidate.current_step === null) {
    return true;
  }

  return (
    !!candidate.current_step &&
    typeof candidate.current_step === 'object' &&
    typeof candidate.current_step.id === 'string' &&
    typeof candidate.current_step.code === 'string' &&
    typeof candidate.current_step.name === 'string'
  );
}

/*
 * UDYAM 8-STAGE VISUAL JOURNEY
 *
 * The analyst-facing Udyam process has EIGHT business stages.  The backend
 * persists SIX durable process-step codes; "Application Reviewed" and "Submit
 * Application" are display milestones derived from existing authoritative
 * signals (health.next_action, WorkProcessState.current_step) — no fake
 * backend codes are introduced.
 *
 * Stage codes used here:
 *   CLIENT_INFORMATION         durable seed code
 *   VERIFICATION_PREPARATION   durable seed code
 *   INTERNAL_REVIEW            durable seed code
 *   APPLICATION_REVIEWED       display-only — derived from approved state
 *   SUBMIT_APPLICATION         backend guard code (not seeded, action only)
 *   APPLICATION_SUBMISSION     durable seed code
 *   QUERY_RESOLUTION           durable seed code
 *   COMPLETION                 durable seed code
 */
export const UDYAM_JOURNEY = [
  { code: 'CLIENT_INFORMATION',       name: 'Client Information & Documents' },
  { code: 'VERIFICATION_PREPARATION', name: 'Verification & Preparation' },
  { code: 'INTERNAL_REVIEW',          name: 'Internal Review & Approval' },
  { code: 'APPLICATION_REVIEWED',     name: 'Application Reviewed' },
  { code: 'SUBMIT_APPLICATION',       name: 'Submit Application' },
  { code: 'APPLICATION_SUBMISSION',   name: 'Application Submitted' },
  { code: 'QUERY_RESOLUTION',         name: 'Query / OTP / Technical Resolution' },
  { code: 'COMPLETION',               name: 'Registration Completion & Certificate' },
] as const;

export type UdyamStageCode = typeof UDYAM_JOURNEY[number]['code'];

/*
 * Analyst guidance for all 8 visual stages.
 * Fields: meaning, todo, required, next.
 * Language is business-facing only — no developer/API terminology.
 */
export const UDYAM_STAGE_GUIDANCE: Record<string, { meaning: string; todo: string; required: string; next: string }> = {
  CLIENT_INFORMATION: {
    meaning: 'Establish the client and collect the documents needed for Udyam registration before preparation can begin.',
    todo: 'Confirm the client, verify useful contact information, collect the required documents, and resolve any outstanding mandatory items.',
    required: 'Aadhaar card, PAN card, and Business / Enterprise details (mandatory). Bank account and GST details (optional but useful).',
    next: 'When mandatory documents and information are satisfied the case advances to Verification & Preparation.',
  },
  VERIFICATION_PREPARATION: {
    meaning: 'Verify the collected client and business details and prepare the registration case for internal review.',
    todo: 'Review captured client and business information, check documents for accuracy and completeness, resolve any missing mandatory details, and prepare the application.',
    required: 'Completed, accurate business/operational information; all mandatory documents collected and verified.',
    next: 'Submit for Review to hand the prepared case to an internal reviewer.',
  },
  INTERNAL_REVIEW: {
    meaning: 'An independent internal review validates the prepared application before it is submitted to the government portal.',
    todo: 'The reviewer checks the prepared information and supporting documents. Approve if correct, or return for correction with a clear explanation of what needs changing.',
    required: 'Prepared application ready for review. A justification comment is required when returning for rework.',
    next: 'Approval marks the application as reviewed and ready for government submission. Returning it sends the case back for correction.',
  },
  APPLICATION_REVIEWED: {
    meaning: 'Internal review has been approved. The application is confirmed ready for government submission — no further internal action is needed at this stage.',
    todo: 'Confirm the reviewed application details are correct. This milestone is reached automatically once the reviewer approves — no separate action is needed to mark it.',
    required: 'Internal approval already recorded.',
    next: 'Proceed to Submit Application to record the actual government submission.',
  },
  SUBMIT_APPLICATION: {
    meaning: 'The reviewed application is ready to be submitted through the government/MSME Udyam portal. Record the submission details once you have submitted externally.',
    todo: 'Submit the application through the government portal, then return here and record the submission evidence accurately — this evidence is permanent.',
    required: 'Application / Reference Number, Submission Date, and Submission Time (all required to record submission).',
    next: 'Record the submission to advance the case to Application Submitted.',
  },
  APPLICATION_SUBMISSION: {
    meaning: 'The government application has been submitted and recorded. The case is now awaiting the government outcome or any follow-up.',
    todo: 'Monitor the government portal for the outcome. When a response is received, record it using the appropriate action below.',
    required: 'Submission reference, date and time already recorded.',
    next: 'Record a query / OTP / technical issue if one arrives, or complete registration when the certificate is received.',
  },
  QUERY_RESOLUTION: {
    meaning: 'The government portal has raised a query, OTP requirement or technical issue that must be resolved before the registration can proceed.',
    todo: 'Record the issue type and full details, perform the required resolution (supply OTP, resolve document query, etc.), then record the resolution remarks.',
    required: 'Issue type (portal query, OTP, technical issue, additional information required, document query, or other) and remarks; resolution remarks when closing.',
    next: 'Resolving the issue returns the case to Application Submitted to await the final outcome.',
  },
  COMPLETION: {
    meaning: 'The Udyam registration has been successfully completed and the certificate received.',
    todo: 'Confirm registration success, upload or link the Udyam certificate using the document facility, and complete the registration to close the Work Item.',
    required: 'The official Udyam registration certificate.',
    next: 'Work completed. No further analyst action is required.',
  },
};

/*
 * Derive the current visual stage index (0–7) from authoritative backend state.
 *
 * Priority (highest wins):
 *   forceTerminalComplete  → always Stage 8 (index 7) for COMPLETED Udyam
 *   persistedStepCode      → maps directly to a journey index
 *   nextActionCode         → fallback from Health projection
 *   health readiness       → earlier stage derivation
 *
 * APPLICATION_REVIEWED (index 3) is current when internal review has approved
 * but submission recording has not yet begun.  The signal is
 * SUBMIT_UDYAM_APPLICATION appearing as the next action while the durable
 * process position has not yet moved to SUBMIT_APPLICATION.
 */
export function deriveUdyamStageIndex(opts: {
  forceTerminalComplete: boolean;
  persistedStepCode: string;
  nextActionCode: string;
  operationalRemaining: number;
  documentsMissing: boolean;
  documentsPending: boolean;
  currentController: string;
}): number {
  const {
    forceTerminalComplete,
    persistedStepCode,
    nextActionCode,
    operationalRemaining,
    documentsMissing,
    documentsPending,
    currentController,
  } = opts;

  if (forceTerminalComplete) return 7; // Stage 8 — terminal

  // Direct mapping from durable process step codes.
  const codeMap: Record<string, number> = {
    CLIENT_INFORMATION:       0,
    VERIFICATION_PREPARATION: 1,
    INTERNAL_REVIEW:          2,
    // APPLICATION_REVIEWED has no durable code
    SUBMIT_APPLICATION:       4,
    APPLICATION_SUBMISSION:   5,
    QUERY_RESOLUTION:         6,
    COMPLETION:               7,
  };
  if (persistedStepCode && codeMap[persistedStepCode] !== undefined) {
    return codeMap[persistedStepCode];
  }

  // Health-based next-action fallback.
  if (nextActionCode === 'RESOLVE_UDYAM_QUERY') return 6;
  if (nextActionCode === 'AWAIT_UDYAM_OUTCOME')  return 5;
  // Stage 5 (Submit Application) — durable code not yet present but action is ready.
  if (nextActionCode === 'SUBMIT_UDYAM_APPLICATION') return 4;
  // Stage 4 (Application Reviewed) — no action code exists; this is a transient
  // milestone.  Rely on the health/controller signals below after review.

  // Generic Work readiness derivation for stages 1–3.
  if (
    nextActionCode === 'REVIEW_WORK' ||
    currentController === 'REVIEWER'
  ) {
    return 2; // Stage 3 — Internal Review
  }

  if (
    operationalRemaining === 0 &&
    !documentsMissing &&
    !documentsPending
  ) {
    return 1; // Stage 2 — Verification & Preparation
  }

  return 0; // Stage 1 — Client Information
}

export function ProcessTracker({
  health,
  processState,
  forceTerminalComplete,
  loading,
  onOpenDocuments,
}: {
  health: WorkHealthSnapshot | null;
  processState: WorkProcessStateSnapshot | null;
  forceTerminalComplete: boolean;
  loading: boolean;
  onOpenDocuments: () => void;
}): React.JSX.Element | null {

  const nextActionCode = String(health?.next_action?.code ?? '');
  const operationalRemaining = Number(health?.operational?.mandatory_remaining ?? 0);
  const documentsMissing =
    Number(health?.documents?.mandatory_missing ?? 0) > 0 ||
    Number(health?.documents?.missing ?? 0) > 0;
  const documentsPending =
    Number(health?.documents?.pending_review ?? 0) > 0 ||
    Number(health?.documents?.pending_acceptance ?? 0) > 0;
  const persistedStepCode = String(processState?.current_step?.code ?? '');
  const currentController = String(health?.current_controller ?? '');

  const currentIndex = deriveUdyamStageIndex({
    forceTerminalComplete,
    persistedStepCode,
    nextActionCode,
    operationalRemaining,
    documentsMissing,
    documentsPending,
    currentController,
  });

  const currentStage = UDYAM_JOURNEY[currentIndex];

  const processNextActionLabel =
    forceTerminalComplete
      ? 'Work completed'
      : currentStage?.code === 'SUBMIT_APPLICATION'
        ? 'Record Udyam application submission'
        : currentStage?.code === 'APPLICATION_SUBMISSION'
          ? 'Record government outcome'
          : currentStage?.code === 'QUERY_RESOLUTION'
            ? 'Resolve query / OTP / technical issue'
            : currentStage?.code === 'COMPLETION'
              ? 'Registration completed'
              : currentStage?.code === 'APPLICATION_REVIEWED'
                ? 'Proceed to submit application'
                : health?.next_action?.label || 'Continue work';

  const actionIsDocuments =
    nextActionCode === 'REQUEST_MISSING_DOCUMENTS' || documentsMissing;

  const currentGuidance = UDYAM_STAGE_GUIDANCE[currentStage?.code ?? ''];

  return (
    <section
      className="cx-process-tracker cx-process-tracker-8stage"
      aria-label="Udyam process journey"
    >
      <div className="cx-process-heading">
        <h4>Process</h4>
        <p className="cx-process-heading-sub">
          Progress updates automatically from the work recorded in this case.
        </p>
      </div>

      {loading ? (
        <div className="cx-process-loading">Loading process&hellip;</div>
      ) : (
        <div className="cx-process-steps">
          {UDYAM_JOURNEY.map((stage, index) => {
            const active = index === currentIndex;
            const completed = index < currentIndex;
            const guidance = UDYAM_STAGE_GUIDANCE[stage.code];

            return (
              <div
                key={stage.code}
                className={
                  `cx-process-step cx-process-static ${
                    active ? 'current' : completed ? 'completed' : 'upcoming'
                  }${guidance ? ' cx-process-step-guided' : ''}`
                }
                aria-current={active ? 'step' : undefined}
                tabIndex={guidance ? 0 : undefined}
              >
                <span className="cx-process-number">
                  {completed ? '\u2713' : index + 1}
                </span>

                <span className="cx-process-step-copy">
                  <span className="cx-process-label">{stage.name}</span>
                  <span className="cx-process-state-label">
                    {active ? 'Current' : completed ? 'Completed' : 'Upcoming'}
                  </span>
                </span>

                {guidance ? (
                  <div className="cx-process-guidance-pop" role="tooltip">
                    <div className="cx-process-guidance-title">{stage.name}</div>
                    <dl>
                      <dt>What this stage means</dt>
                      <dd>{guidance.meaning}</dd>
                      <dt>What you need to do</dt>
                      <dd>{guidance.todo}</dd>
                      <dt>Required information</dt>
                      <dd>{guidance.required}</dd>
                      <dt>Next step</dt>
                      <dd>{guidance.next}</dd>
                    </dl>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      {!loading ? (
        <div className="cx-process-currentstage">
          <div className="cx-process-currentstage-head">
            <span className="cx-process-currentstage-kicker">Current stage</span>
            <strong className="cx-process-currentstage-name">
              {currentStage?.name ?? 'Starting'}
            </strong>
            {currentGuidance ? (
              <p className="cx-process-currentstage-meaning">
                {currentGuidance.meaning}
              </p>
            ) : null}
          </div>
          <div className="cx-process-currentstage-next">
            <span className="cx-process-currentstage-kicker">Next action</span>
            <strong>{processNextActionLabel}</strong>
            {actionIsDocuments && !forceTerminalComplete ? (
              <button type="button" className="cx-btn subtle" onClick={onOpenDocuments}>
                Open Documents
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}


export async function completeUdyamRegistrationAndRefresh(deps: {
  workItemId: string;
  certificate: File;
  remarks: string;
  upload: typeof uploadMany;
  onUploaded: () => void;
  onChanged: () => Promise<void>;
}): Promise<void> {
  const {
    workItemId,
    certificate,
    remarks,
    upload,
    onUploaded,
    onChanged,
  } = deps;

  await upload(
    'work-items',
    workItemId,
    'udyam-complete-registration',
    [certificate],
    remarks.trim() ? { remarks: remarks.trim() } : {},
  );

  // Preserve the production ordering: clear the local completion form after
  // the server accepts the action, then reconcile the open workspace from the
  // authoritative WorkItem before any further lifecycle action is presented.
  onUploaded();
  await onChanged();
}


type UdyamExternalActionsProps = {
  workItem: Row;
  processState: WorkProcessStateSnapshot | null;
  health: WorkHealthSnapshot | null;
  onChanged: () => Promise<void>;
  onError: (message: string) => void;
};

/*
 * Change 5: collapsible Udyam action panel wrapper.
 *
 * Presentation-only. It renders a header with the current stage title, a short
 * context-aware summary, and an accessible Collapse/Expand control. When
 * collapsed it shows only the summary; when expanded it shows the full action
 * body (its children). It holds NO business state, makes NO API calls, and does
 * not touch draft values - the draft field state lives in the parent component
 * and is untouched by collapsing, so expanding again shows the same drafts.
 */
type UdyamActionShellProps = {
  title: string;
  summary: string;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
};

export function UdyamActionShell({
  title,
  summary,
  collapsed,
  onToggle,
  children,
}: UdyamActionShellProps): React.JSX.Element {
  return (
    <section className="cx-process-guidance cx-udyam-action-shell">
      <div style={{ width: '100%' }}>
        <div className="cx-udyam-action-shell-header">
          <div className="cx-udyam-action-shell-heading">
            <strong>{title}</strong>
            {collapsed && summary ? (
              <span className="cx-udyam-action-shell-summary">
                {summary}
              </span>
            ) : null}
          </div>
          <button
            type="button"
            className="cx-btn subtle cx-udyam-action-shell-toggle"
            aria-expanded={!collapsed}
            aria-label={
              collapsed
                ? `Expand ${title} panel`
                : `Collapse ${title} panel`
            }
            onClick={onToggle}
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
        {!collapsed ? (
          <div className="cx-udyam-action-shell-body">{children}</div>
        ) : null}
      </div>
    </section>
  );
}

export function UdyamExternalActions({
  workItem,
  processState,
  health,
  onChanged,
  onError,
}: UdyamExternalActionsProps): React.JSX.Element | null {
  const persistedStepCode = String(
    processState?.current_step?.code ?? '',
  );

  const nextActionCode = String(
    health?.next_action?.code ?? '',
  );

  const stepCode =
    persistedStepCode ||
    (
      nextActionCode === 'SUBMIT_UDYAM_APPLICATION'
        ? 'SUBMIT_APPLICATION'
        : nextActionCode === 'AWAIT_UDYAM_OUTCOME'
          ? 'APPLICATION_SUBMISSION'
          : nextActionCode === 'RESOLVE_UDYAM_QUERY'
            ? 'QUERY_RESOLUTION'
            : ''
    );

  const operationalData =
    (
      workItem.operational_data as
        | Record<string, unknown>
        | undefined
    ) ?? {};

  const certificateAttachments = useList(
    'document-attachments',
    {
      work_item_id: String(workItem.id),
    },
  );

  const persistedCertificateAttachmentId = String(
    operationalData.udyam_certificate_attachment_id ?? '',
  );

  const persistedCertificateAttachment =
    persistedCertificateAttachmentId
      ? (
          certificateAttachments.rows.find(
            (attachment) =>
              String(attachment.id) ===
              persistedCertificateAttachmentId,
          ) ?? null
        )
      : null;

  const completionTimestamp = String(
    workItem.completed_at ?? '',
  );

  const [reference, setReference] = useState(
    String(
      operationalData.udyam_application_reference ?? '',
    ),
  );

  const [submissionDate, setSubmissionDate] = useState(
    String(
      operationalData.udyam_submission_date ?? '',
    ),
  );

  const [submissionTime, setSubmissionTime] = useState(
    String(
      operationalData.udyam_submission_time ?? '',
    ),
  );

  const canSubmitApplication =
    workItem.can_edit === true;

  const persistedQueryType = String(
    operationalData.udyam_query_type ?? '',
  );

  const persistedQueryRemarks = String(
    operationalData.udyam_query_remarks ?? '',
  );

  const persistedQueryResolutionRemarks = String(
    operationalData.udyam_query_resolution_remarks ?? '',
  );

  const [queryType, setQueryType] = useState('');
  const [remarks, setRemarks] = useState('');
  const [certificate, setCertificate] =
    useState<File | null>(null);

  const certificateInputRef =
    useRef<HTMLInputElement | null>(null);

  const [governmentOutcome, setGovernmentOutcome] =
    useState<'QUERY' | 'REGISTERED' | ''>('');

  const [busy, setBusy] = useState(false);

  // Changes 3 & 4: explicit selected-action confirmation for stage-changing
  // Udyam actions. This is UX-only presentation state layered on top of the
  // existing authoritative backend actions - it never changes which backend
  // action runs, only defers it until the analyst confirms. Selecting an action
  // sets this; Cancel clears it (draft field values are preserved because they
  // live in their own state). The actual backend call still goes through
  // runAction exactly once, from the confirm handler.
  const [udyamPendingAction, setUdyamPendingAction] = useState<
    'SUBMIT_APPLICATION' | 'REPORT_QUERY' | 'RESOLVE_QUERY' | ''
  >('');

  // Change 5: collapsible action panel (presentation state only). Defaults to
  // expanded so an action needing input is immediately visible; the analyst can
  // collapse it. Collapsing never calls the backend, never clears drafts, and
  // never clears a pending action - it only hides the body.
  const [panelCollapsed, setPanelCollapsed] = useState(false);

  const workCompleted =
    String(workItem.status ?? '') === 'COMPLETED';

  if (
    !workCompleted &&
    stepCode !== 'SUBMIT_APPLICATION' &&
    stepCode !== 'APPLICATION_SUBMISSION' &&
    stepCode !== 'QUERY_RESOLUTION'
  ) {
    return null;
  }

  const runAction = async (
    actionName: string,
    payload: Row,
  ): Promise<void> => {
    setBusy(true);
    onError('');

    try {
      await act(
        'work-items',
        String(workItem.id),
        actionName,
        payload,
      );

      setRemarks('');
      setQueryType('');
      // Changes 3/4: clear any selected-action confirmation state after the
      // backend action has succeeded so the confirmed action does not remain
      // visibly "selected"; authoritative reconciliation drives the next stage.
      setUdyamPendingAction('');
      setGovernmentOutcome('');
      await onChanged();
    } catch (error) {
      // Show the original business error first, and keep it visible.
      onError(
        error instanceof Error
          ? error.message
          : 'Udyam action failed.',
      );
      // Then re-read backend truth so a stale previous-stage action cannot
      // remain visible after the backend has already transitioned.  This
      // refresh is guarded: if it also fails, the original business error is
      // preserved and not replaced by a secondary refresh failure.
      try {
        await onChanged();
      } catch {
        // Intentionally swallow refresh failure; the original error stands.
      }
    } finally {
      setBusy(false);
    }
  };

  const uploadCertificate = async (): Promise<void> => {

    const selectedCertificate =
      certificateInputRef.current?.files?.[0] ??
      certificate;

    if (!selectedCertificate) {
      onError('Udyam certificate is required.');
      return;
    }

    setBusy(true);
    onError('');

    try {
      await completeUdyamRegistrationAndRefresh({
        workItemId: String(workItem.id),
        certificate: selectedCertificate,
        remarks,
        upload: uploadMany,
        onUploaded: () => {
          setCertificate(null);

          if (certificateInputRef.current) {
            certificateInputRef.current.value = '';
          }

          setRemarks('');
        },
        onChanged,
      });
    } catch (error) {
      onError(
        error instanceof Error
          ? error.message
          : 'Registration completion failed.',
      );
      try {
        await onChanged();
      } catch {
        // Preserve the original completion error if refresh also fails.
      }
    } finally {
      setBusy(false);
    }
  };

  if (workCompleted) {
    return (
      <section
        className="cx-process-guidance"
        style={{ marginBottom: 16 }}
      >
        <div style={{ width: '100%' }}>
          <strong>
            Registration Completion & Certificate
          </strong>

          <p>
            Udyam registration is complete. The application
            submission details and previous query history are
            retained below as a read-only record.
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'minmax(240px, 1fr) minmax(180px, 0.65fr) minmax(180px, 0.65fr)',
              gap: 12,
              marginTop: 12,
            }}
          >
            <div className="cx-field">
              <label>Application / Reference Number</label>
              <input
                type="text"
                value={reference}
                disabled
              />
            </div>

            <div className="cx-field">
              <label>Submission Date</label>
              <input
                type="date"
                value={submissionDate}
                disabled
              />
            </div>

            <div className="cx-field">
              <label>Submission Time</label>
              <input
                type="time"
                value={submissionTime}
                disabled
              />
            </div>
          </div>

          <div
            style={{
              marginTop: 16,
              paddingTop: 14,
              borderTop:
                '1px solid var(--cx-border, #d8dee8)',
            }}
          >
            <strong>Registration Certificate</strong>

            <div
              style={{
                marginTop: 10,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                flexWrap: 'wrap',
              }}
            >
              <div>
                {persistedCertificateAttachment ? (
                  <>
                    <div
                      style={{
                        fontWeight: 600,
                        marginBottom: 3,
                      }}
                    >
                      {String(
                        persistedCertificateAttachment
                          .original_name ||
                          'Udyam Registration Certificate',
                      )}
                    </div>

                    <div
                      style={{
                        fontSize: 12,
                        color: '#64748b',
                      }}
                    >
                      Certificate retained with this completed registration.
                    </div>
                  </>
                ) : persistedCertificateAttachmentId ? (
                  <div
                    style={{
                      fontSize: 13,
                      color: '#64748b',
                    }}
                  >
                    Registration certificate is recorded but is currently unavailable.
                  </div>
                ) : (
                  <div
                    style={{
                      fontSize: 13,
                      color: '#64748b',
                    }}
                  >
                    This earlier completed record does not yet have a durable certificate link.
                  </div>
                )}
              </div>

              {persistedCertificateAttachment &&
              persistedCertificateAttachment.download_url ? (
                <a
                  className="cx-btn"
                  href={String(
                    persistedCertificateAttachment.download_url,
                  )}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download Certificate
                </a>
              ) : null}
            </div>

            {completionTimestamp ? (
              <div
                style={{
                  marginTop: 12,
                  fontSize: 12,
                  color: '#64748b',
                }}
              >
                Registration completed:{' '}
                {new Date(
                  completionTimestamp,
                ).toLocaleString()}
              </div>
            ) : null}
          </div>

          {(
            persistedQueryType ||
            persistedQueryRemarks ||
            persistedQueryResolutionRemarks
          ) ? (
            <div
              style={{
                marginTop: 16,
                paddingTop: 14,
                borderTop:
                  '1px solid var(--cx-border, #d8dee8)',
              }}
            >
              <strong>Previous Application Query</strong>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'minmax(220px, 0.8fr) minmax(300px, 1.2fr)',
                  gap: 12,
                  marginTop: 12,
                }}
              >
                <div className="cx-field">
                  <label>Query / Issue Type</label>
                  <input
                    type="text"
                    value={persistedQueryType}
                    disabled
                  />
                </div>

                <div className="cx-field">
                  <label>Query Remarks</label>
                  <textarea
                    value={persistedQueryRemarks}
                    disabled
                  />
                </div>
              </div>

              <div
                className="cx-field"
                style={{ marginTop: 12 }}
              >
                <label>Response Provided</label>
                <textarea
                  value={persistedQueryResolutionRemarks}
                  disabled
                />
              </div>
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  if (stepCode === 'SUBMIT_APPLICATION') {
    return (
      <UdyamActionShell
        title="Submit Application"
        summary="Record submission reference, date and time"
        collapsed={panelCollapsed}
        onToggle={() => setPanelCollapsed((value) => !value)}
      >
        <div style={{ width: '100%' }}>
          <div style={{ marginBottom: 14 }}>
            <div
              style={{
                marginTop: 4,
                fontSize: 12,
                color: '#64748b',
              }}
            >
              Enter the government portal submission details
              before moving this work item to Application Submitted.
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'minmax(260px, 2fr) minmax(180px, 1fr) minmax(160px, 1fr)',
              gap: 12,
              alignItems: 'end',
            }}
          >
            <div
              className="cx-field"
              style={{ marginBottom: 0 }}
            >
              <label htmlFor="udyam-submission-reference">Application / Reference Number *</label>
              <input
                id="udyam-submission-reference"
                type="text"
                value={reference}
                disabled={
                  busy || !canSubmitApplication
                }
                onChange={(event) =>
                  setReference(event.target.value)
                }
              />
            </div>

            <div
              className="cx-field"
              style={{ marginBottom: 0 }}
            >
              <label htmlFor="udyam-submission-date">Submission Date *</label>
              <input
                id="udyam-submission-date"
                type="date"
                value={submissionDate}
                disabled={
                  busy || !canSubmitApplication
                }
                onChange={(event) =>
                  setSubmissionDate(event.target.value)
                }
              />
            </div>

            <div
              className="cx-field"
              style={{ marginBottom: 0 }}
            >
              <label htmlFor="udyam-submission-time">Submission Time *</label>
              <input
                id="udyam-submission-time"
                type="time"
                value={submissionTime}
                disabled={
                  busy || !canSubmitApplication
                }
                onChange={(event) =>
                  setSubmissionTime(event.target.value)
                }
              />
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              marginTop: 14,
              gap: 10,
            }}
          >
            {udyamPendingAction === 'SUBMIT_APPLICATION' ? (
              <>
                <span
                  className="cx-udyam-selected-label"
                  role="status"
                  style={{ alignSelf: 'center', marginRight: 'auto' }}
                >
                  Submit Application selected
                </span>
                <button
                  type="button"
                  className="cx-btn subtle"
                  disabled={busy}
                  onClick={() => setUdyamPendingAction('')}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="cx-btn cx-udyam-primary-action"
                  style={{
                    width: 'auto',
                    minWidth: 190,
                    paddingLeft: 18,
                    paddingRight: 18,
                  }}
                  disabled={
                    busy ||
                    !canSubmitApplication ||
                    !reference.trim() ||
                    !submissionDate ||
                    !submissionTime
                  }
                  onClick={() => {
                    void runAction(
                      'udyam-submit-application',
                      {
                        application_reference: reference.trim(),
                        submission_date: submissionDate,
                        submission_time: submissionTime,
                      },
                    );
                  }}
                >
                  {busy
                    ? 'Submitting...'
                    : 'Save & Submit Application'}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="cx-btn cx-udyam-primary-action"
                style={{
                  width: 'auto',
                  minWidth: 190,
                  paddingLeft: 18,
                  paddingRight: 18,
                }}
                disabled={
                  busy ||
                  !canSubmitApplication ||
                  !reference.trim() ||
                  !submissionDate ||
                  !submissionTime
                }
                aria-pressed={false}
                onClick={() => {
                  // Select only - does NOT call the backend yet.
                  setUdyamPendingAction('SUBMIT_APPLICATION');
                }}
              >
                Submit Udyam application
              </button>
            )}
          </div>
        </div>
      </UdyamActionShell>
    );
  }

  if (stepCode === 'QUERY_RESOLUTION') {
    return (
      <UdyamActionShell
        title="Query / OTP / Technical Resolution"
        summary={
          persistedQueryType
            ? `Resolving: ${persistedQueryType}`
            : 'Resolve the recorded government query'
        }
        collapsed={panelCollapsed}
        onToggle={() => setPanelCollapsed((value) => !value)}
      >
        <div style={{ width: '100%' }}>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'minmax(260px, 2fr) minmax(180px, 1fr) minmax(160px, 1fr)',
              gap: 12,
              marginTop: 12,
              marginBottom: 14,
            }}
          >
            <div className="cx-field" style={{ marginBottom: 0 }}>
              <label>Application / Reference Number</label>
              <input
                type="text"
                value={reference}
                disabled
              />
            </div>

            <div className="cx-field" style={{ marginBottom: 0 }}>
              <label>Submission Date</label>
              <input
                type="date"
                value={submissionDate}
                disabled
              />
            </div>

            <div className="cx-field" style={{ marginBottom: 0 }}>
              <label>Submission Time</label>
              <input
                type="time"
                value={submissionTime}
                disabled
              />
            </div>
          </div>

          {(persistedQueryType || persistedQueryRemarks) ? (
            <div
              style={{
                marginTop: 14,
                marginBottom: 14,
              }}
            >
              <strong>Government Query</strong>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'minmax(220px, 0.8fr) minmax(320px, 1.2fr)',
                  gap: 12,
                  marginTop: 10,
                }}
              >
                <div className="cx-field">
                  <label>Query / Issue Type</label>
                  <input
                    type="text"
                    value={persistedQueryType}
                    disabled
                  />
                </div>

                <div className="cx-field">
                  <label>Query Remarks</label>
                  <textarea
                    value={persistedQueryRemarks}
                    disabled
                  />
                </div>
              </div>
            </div>
          ) : null}

          <div className="cx-field">
            <label>Resolution remarks *</label>
            <textarea
              value={remarks}
              disabled={busy}
              onChange={(event) =>
                setRemarks(event.target.value)
              }
            />
          </div>

          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 10,
            }}
          >
            {udyamPendingAction === 'RESOLVE_QUERY' ? (
              <>
                <span
                  className="cx-udyam-selected-label"
                  role="status"
                  style={{ alignSelf: 'center', marginRight: 'auto' }}
                >
                  Resolve Query selected
                </span>
                <button
                  type="button"
                  className="cx-btn subtle"
                  disabled={busy}
                  onClick={() => setUdyamPendingAction('')}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="cx-btn cx-udyam-primary-action"
                  disabled={busy || !remarks.trim()}
                  onClick={() => {
                    void runAction(
                      'udyam-resolve-query',
                      {
                        remarks: remarks.trim(),
                      },
                    );
                  }}
                >
                  {busy ? 'Saving...' : 'Save & Resolve Query'}
                </button>
              </>
            ) : (
              <button
                type="button"
                className="cx-btn cx-udyam-primary-action"
                disabled={busy || !remarks.trim()}
                aria-pressed={false}
                onClick={() => {
                  // Select only - does NOT call the backend yet.
                  setUdyamPendingAction('RESOLVE_QUERY');
                }}
              >
                Respond to Application Query
              </button>
            )}
          </div>
        </div>
      </UdyamActionShell>
    );
  }

  return (
    <UdyamActionShell
      title="Application Submitted"
      summary={
        governmentOutcome === 'QUERY'
          ? 'Recording a government query'
          : governmentOutcome === 'REGISTERED'
            ? 'Recording registration success'
            : 'Awaiting government outcome'
      }
      collapsed={panelCollapsed}
      onToggle={() => setPanelCollapsed((value) => !value)}
    >
      <div style={{ width: '100%' }}>
        <div style={{ marginBottom: 16 }}>
          <p style={{ marginBottom: 0 }}>
            The application has been submitted to the government
            portal. Record the registration outcome when it becomes
            available.
          </p>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns:
              'minmax(260px, 2fr) minmax(180px, 1fr) minmax(160px, 1fr)',
            gap: 12,
            marginBottom: 16,
          }}
        >
          <div className="cx-field" style={{ marginBottom: 0 }}>
            <label>Application / Reference Number</label>
            <input
              type="text"
              value={reference}
              disabled
            />
          </div>

          <div className="cx-field" style={{ marginBottom: 0 }}>
            <label>Submission Date</label>
            <input
              type="date"
              value={submissionDate}
              disabled
            />
          </div>

          <div className="cx-field" style={{ marginBottom: 0 }}>
            <label>Submission Time</label>
            <input
              type="time"
              value={submissionTime}
              disabled
            />
          </div>
        </div>

        {persistedQueryType || persistedQueryRemarks || persistedQueryResolutionRemarks ? (
          <div
            className="cx-process-guidance"
            style={{ marginBottom: 16 }}
          >
            <div style={{ width: '100%' }}>
              <strong>Previous Application Query</strong>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns:
                    'minmax(220px, 0.8fr) minmax(300px, 1.2fr)',
                  gap: 12,
                  marginTop: 12,
                }}
              >
                <div className="cx-field">
                  <label>Query / Issue Type</label>
                  <input
                    type="text"
                    value={persistedQueryType}
                    disabled
                  />
                </div>

                <div className="cx-field">
                  <label>Query Remarks</label>
                  <textarea
                    value={persistedQueryRemarks}
                    disabled
                  />
                </div>
              </div>

              <div className="cx-field">
                <label>Response Provided</label>
                <textarea
                  value={persistedQueryResolutionRemarks}
                  disabled
                />
              </div>
            </div>
          </div>
        ) : null}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns:
              'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 12,
            marginBottom: 16,
          }}
        >
          <button
            type="button"
            className={
              governmentOutcome === 'QUERY'
                ? 'cx-btn cx-udyam-outcome-selected'
                : 'cx-btn subtle cx-udyam-outcome-option'
            }
            disabled={busy}
            onClick={() => {
              setGovernmentOutcome('QUERY');
              setCertificate(null);
              setUdyamPendingAction('');
            }}
            style={{
              textAlign: 'left',
              minHeight: 64,
            }}
          >
            Query / OTP / Technical Issue Received
          </button>

          <button
            type="button"
            className={
              governmentOutcome === 'REGISTERED'
                ? 'cx-btn cx-udyam-outcome-selected'
                : 'cx-btn subtle cx-udyam-outcome-option'
            }
            disabled={busy}
            onClick={() => {
              setGovernmentOutcome('REGISTERED');
              setQueryType('');
              setRemarks('');
              setUdyamPendingAction('');
            }}
            style={{
              textAlign: 'left',
              minHeight: 64,
            }}
          >
            Registration Successful / Certificate Received
          </button>
        </div>

        {governmentOutcome === 'QUERY' ? (
          <div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns:
                  'minmax(220px, 0.8fr) minmax(300px, 1.2fr)',
                gap: 12,
                alignItems: 'start',
              }}
            >
              <div className="cx-field">
                <label>Query / Issue Type *</label>

                <select
                  value={queryType}
                  disabled={busy}
                  onChange={(event) =>
                    setQueryType(event.target.value)
                  }
                >
                  <option value="">
                    Select query / issue
                  </option>

                  <option value="PORTAL_QUERY">
                    Portal query
                  </option>

                  <option value="OTP_REQUIRED">
                    OTP required
                  </option>

                  <option value="TECHNICAL_ISSUE">
                    Technical issue
                  </option>

                  <option value="ADDITIONAL_INFORMATION">
                    Additional information required
                  </option>

                  <option value="DOCUMENT_QUERY">
                    Document query
                  </option>

                  <option value="OTHER">
                    Other
                  </option>
                </select>
              </div>

              <div className="cx-field">
                <label>Remarks *</label>

                <textarea
                  value={remarks}
                  disabled={busy}
                  onChange={(event) =>
                    setRemarks(event.target.value)
                  }
                />
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: 10,
                gap: 10,
              }}
            >
              {udyamPendingAction === 'REPORT_QUERY' ? (
                <>
                  <span
                    className="cx-udyam-selected-label"
                    role="status"
                    style={{ alignSelf: 'center', marginRight: 'auto' }}
                  >
                    Query / OTP / Technical Issue selected
                  </span>
                  <button
                    type="button"
                    className="cx-btn subtle"
                    disabled={busy}
                    onClick={() => setUdyamPendingAction('')}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="cx-btn cx-udyam-primary-action"
                    disabled={
                      busy ||
                      !queryType ||
                      !remarks.trim()
                    }
                    onClick={() => {
                      void runAction(
                        'udyam-report-query',
                        {
                          query_type: queryType,
                          remarks: remarks.trim(),
                        },
                      );
                    }}
                  >
                    {busy
                      ? 'Saving...'
                      : 'Save & Move to Query Resolution'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="cx-btn cx-udyam-primary-action"
                  disabled={
                    busy ||
                    !queryType ||
                    !remarks.trim()
                  }
                  aria-pressed={false}
                  onClick={() => {
                    // Select only - does NOT call the backend yet.
                    setUdyamPendingAction('REPORT_QUERY');
                  }}
                >
                  Move to Query Resolution
                </button>
              )}
            </div>
          </div>
        ) : null}

        {governmentOutcome === 'REGISTERED' ? (
          <div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns:
                  'minmax(280px, 1fr) minmax(300px, 1fr)',
                gap: 12,
                alignItems: 'start',
              }}
            >
              <div className="cx-field">
                <label>Registration Certificate *</label>

                <input
                  ref={certificateInputRef}
                  type="file"
                  disabled={busy}
                  onChange={(event) => {
                    const selectedFile =
                      event.target.files?.[0] ?? null;

                    setCertificate(selectedFile);

                    if (selectedFile) {
                      onError('');
                    }
                  }}
                />
              </div>

              <div className="cx-field">
                <label>Remarks</label>

                <textarea
                  value={remarks}
                  disabled={busy}
                  onChange={(event) =>
                    setRemarks(event.target.value)
                  }
                />
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: 10,
              }}
            >
              <button
                type="button"
                className="cx-btn cx-udyam-primary-action"
                disabled={busy || !certificate}
                onClick={() => {
                  void uploadCertificate();
                }}
              >
                {busy
                  ? 'Completing...'
                  : 'Complete Registration'}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </UdyamActionShell>
  );}


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

/*
 * Mudra loan end-to-end runtime workspace (NEW).
 *
 * Renders the current Mudra system stage, the completed/current/upcoming
 * position, the business checkpoint inside the current stage, the required
 * information for the available action, and an explicit select -> confirm ->
 * backend -> reconcile action flow (mirroring the Udyam UX pattern, NOT its
 * business rules). All state is authoritative: the current stage is read from
 * the backend WorkProcessState via processState.current_step.code, and every
 * action calls a backend Mudra endpoint then reconciles through onChanged().
 */
export const MUDRA_STAGE_ORDER: string[] = [
  'APPLICATION',
  'CREDIT_ELIGIBILITY',
  'FILE_PREPARATION',
  'BANK_SUBMITTED',
  'BANK_VERIFICATION',
  'BANK_PENDING',
  'RO_REVIEW',
  'SANCTIONED',
  'DISBURSEMENT',
  'CLOSED',
];

export const MUDRA_STAGE_LABEL: Record<string, string> = {
  APPLICATION: 'Application & KYC',
  CREDIT_ELIGIBILITY: 'Credit & Eligibility',
  FILE_PREPARATION: 'File Preparation',
  BANK_SUBMITTED: 'Bank Submitted',
  BANK_VERIFICATION: 'Bank Verification',
  BANK_PENDING: 'Bank Pending',
  RO_REVIEW: 'RO Review',
  SANCTIONED: 'Sanctioned',
  DISBURSEMENT: 'Disbursement',
  CLOSED: 'Closed',
};

/*
 * Presentation-only analyst guidance for the 10 Mudra stages.
 *
 * This data does not derive workflow state, control action visibility,
 * select endpoints, or advance WorkProcessState.
 */
export type MudraStageGuidance = {
  meaning: string;
  previous: string;
  todo: string;
  required: string;
  next: string;
  actions: string[];
};

export const MUDRA_STAGE_GUIDANCE = {
  APPLICATION: {
    meaning:
      'Start and prepare the Mudra loan application by capturing the loan request, business purpose, application details and KYC-related information.',
    previous:
      'This is the starting stage of the Mudra workflow. The case has been created and is ready for application preparation.',
    todo:
      'Enter the application details, save your work as needed, and when the application is ready use Submit for Review for the initial internal review.',
    required:
      'Requested loan amount and loan purpose are required for application persistence. Also capture business activity, application reference and application date when available.',
    next:
      'The initial internal reviewer checks the prepared application. Reviewer approval moves the case to Credit & Eligibility; a return for rework sends it back for correction.',
    actions: [
      'Save — saves the current application details and keeps the workspace open; it does not advance the workflow.',
      'Save & Close — saves the same application details and closes the workspace; it does not advance the workflow.',
      'Submit for Review — sends Application & KYC to the initial internal reviewer. This is the one generic review gate in the Mudra workflow.',
    ],
  },

  CREDIT_ELIGIBILITY: {
    meaning:
      'Assess the applicant credit position and decide whether the application is eligible to continue.',
    previous:
      'Application & KYC was prepared and approved through the initial internal review.',
    todo:
      'Record the CIBIL assessment first, then make the eligibility decision.',
    required:
      'CIBIL score is required before eligibility can proceed. Capture CIBIL bureau, check date, result, report reference and remarks where applicable. A rejection reason is required when marking Not Eligible.',
    next:
      'Mark Eligible moves the case to File Preparation. Mark Not Eligible rejects the case and makes it terminal.',
    actions: [
      'Record CIBIL — saves the applicant credit assessment used for the eligibility decision.',
      'Mark Eligible — confirms eligibility and continues to File Preparation.',
      'Mark Not Eligible — rejects the case as not eligible; a rejection reason is required.',
    ],
  },

  FILE_PREPARATION: {
    meaning:
      'Prepare the complete loan file and project-report information required before sending the application to the bank.',
    previous:
      'The applicant passed Credit & Eligibility.',
    todo:
      'Confirm that the project report/file preparation is complete and record the preparation date.',
    required:
      'Project report prepared status and project report date.',
    next:
      'Completing File Preparation moves the case to Bank Submitted.',
    actions: [
      'Complete File Preparation — confirms the file is prepared and moves the case to Bank Submitted.',
    ],
  },

  BANK_SUBMITTED: {
    meaning:
      'Record the formal transfer of the prepared loan file to the bank and the bank acknowledgement.',
    previous:
      'File Preparation was completed and the application became ready for bank submission.',
    todo:
      'Capture the bank, branch, transfer details, reference and acknowledgement information.',
    required:
      'Bank name and bank acknowledgement date are required by the current action. Also capture branch, file transfer date and bank reference where applicable.',
    next:
      'Recording the bank submission moves the case to Bank Verification.',
    actions: [
      'Record Bank Submission — saves bank submission/acknowledgement details and moves the case to Bank Verification.',
    ],
  },

  BANK_VERIFICATION: {
    meaning:
      'Record the bank verification outcome after the bank has received the loan file.',
    previous:
      'The loan file was submitted to the bank and acknowledgement details were recorded.',
    todo:
      'Enter the verification details and choose whether the bank verification is Clear or Pending.',
    required:
      'Verification date and verification remarks should be recorded for the bank decision.',
    next:
      'Clear moves the case to RO Review. Pending moves the case to Bank Pending for additional information or follow-up.',
    actions: [
      'Mark Clear — records successful bank verification and moves the case to RO Review.',
      'Mark Pending — records an outstanding bank requirement and moves the case to Bank Pending.',
    ],
  },

  BANK_PENDING: {
    meaning:
      'Manage information, documents or clarification requested while the case is pending with the bank.',
    previous:
      'Bank Verification identified an outstanding requirement and marked the case Pending.',
    todo:
      'Raise the pending requirement when needed, assign or reassign responsibility, record the information/evidence received, and complete Re-QC after the requirement is resolved.',
    required:
      'Pending reason is required when raising a task. Capture requested information/document, responsible user and received evidence according to the active pending-task state.',
    next:
      'Complete Re-QC returns the case to Bank Verification so the verification decision can be performed again.',
    actions: [
      'Raise Pending Task — records a new outstanding bank requirement.',
      'Reassign Pending Task — changes responsibility for the active pending requirement.',
      'Record Received Information — records the information or evidence received against the active requirement.',
      'Complete Re-QC — completes the follow-up quality check and returns the case to Bank Verification.',
    ],
  },

  RO_REVIEW: {
    meaning:
      'Complete the dedicated Relationship Officer review after successful bank verification.',
    previous:
      'Bank Verification was marked Clear.',
    todo:
      'Record the RO details, review status, date and remarks, then complete the RO review.',
    required:
      'RO review status is required. Capture RO name, review date and remarks as applicable.',
    next:
      'Completing the dedicated RO Review moves the case to Sanctioned.',
    actions: [
      'Complete RO Review — completes the dedicated RO checkpoint and moves the case to Sanctioned. It is separate from the initial Submit for Review flow.',
    ],
  },

  SANCTIONED: {
    meaning:
      'Record the loan sanction and complete all sanction conditions before disbursement.',
    previous:
      'The dedicated RO Review was completed successfully.',
    todo:
      'Record the sanction first. After sanction is recorded, complete the applicable sanction conditions.',
    required:
      'Capture sanctioned amount, sanction date, sanction reference and remarks. Complete the sanction-condition status/date required by the existing stage controls.',
    next:
      'Once sanction conditions are complete, the case moves to Disbursement.',
    actions: [
      'Record Sanction — saves the sanction details; recording sanction alone does not complete the disbursement stage.',
      'Complete Sanction Conditions — confirms all sanction conditions are satisfied and moves the case to Disbursement.',
    ],
  },

  DISBURSEMENT: {
    meaning:
      'Complete the final loan-disbursement process after sanction conditions have been satisfied.',
    previous:
      'Sanction was recorded and all sanction conditions were completed.',
    todo:
      'First mark the case ready for disbursement, then record the actual disbursement details.',
    required:
      'Record the disbursement-ready date first, followed by the existing disbursement amount, date, reference and related details required by the stage.',
    next:
      'Actual disbursement closes the Mudra workflow.',
    actions: [
      'Mark Disbursement Ready — confirms the case is ready for actual disbursement.',
      'Record Disbursement — records final disbursement and closes the Mudra process.',
    ],
  },

  CLOSED: {
    meaning:
      'The Mudra loan workflow has been completed.',
    previous:
      'Actual loan disbursement was recorded successfully.',
    todo:
      'No further Mudra workflow action is required. Review the completed case or history when needed.',
    required:
      'No additional workflow fields are required.',
    next:
      'Process complete. There is no forward Mudra workflow action.',
    actions: [],
  },
} satisfies Record<string, MudraStageGuidance>;


type MudraExternalActionsProps = {
  workItem: Row;
  processState: WorkProcessStateSnapshot | null;
  onChanged: () => Promise<void> | void;
  onError: (message: string) => void;
  /*
   * Optional: close the workspace drawer. Only used by the APPLICATION-stage
   * "Save & Close" action, which must close the workspace ONLY after the
   * dedicated Mudra persistence call has actually succeeded. Every other
   * Mudra action is unaffected - they never receive or call this.
   */
  onCloseWorkspace?: () => void;
};

export function MudraProcessTracker({
  currentCode,
  rejected,
}: {
  currentCode: string;
  rejected: boolean;
}): React.JSX.Element {
  const currentIndex = MUDRA_STAGE_ORDER.indexOf(currentCode);
  return (
    <div className="cx-process-steps cx-mudra-tracker" aria-label="Mudra process tracker">
      {MUDRA_STAGE_ORDER.map((code, index) => {
        const isCurrent = !rejected && code === currentCode;
        const isComplete = !rejected && currentIndex >= 0 && index < currentIndex;
        const cls =
          'cx-process-step cx-process-static' +
          (isCurrent ? ' cx-process-step-current' : '') +
          (isComplete ? ' cx-process-step-complete' : '');
        return (
          <div
            key={code}
            className={`${cls} cx-process-step-guided`}
            data-testid={`mudra-stage-${code}`}
            tabIndex={0}
            aria-describedby={`mudra-guidance-${code}`}
            style={{ position: 'relative' }}
          >
            <span className="cx-process-step-copy">
              {MUDRA_STAGE_LABEL[code] ?? code}
            </span>
            {MUDRA_STAGE_GUIDANCE[code as keyof typeof MUDRA_STAGE_GUIDANCE] ? (
              <div
                id={`mudra-guidance-${code}`}
                className="cx-process-guidance-pop"
                role="tooltip"
              >
                <div className="cx-process-guidance-title">
                  {MUDRA_STAGE_LABEL[code] ?? code}
                </div>
                <dl>
                  <dt>What this stage means</dt>
                  <dd>
                    {MUDRA_STAGE_GUIDANCE[
                      code as keyof typeof MUDRA_STAGE_GUIDANCE
                    ].meaning}
                  </dd>
                  <dt>Previous</dt>
                  <dd>
                    {MUDRA_STAGE_GUIDANCE[
                      code as keyof typeof MUDRA_STAGE_GUIDANCE
                    ].previous}
                  </dd>
                  <dt>What to do</dt>
                  <dd>
                    {MUDRA_STAGE_GUIDANCE[
                      code as keyof typeof MUDRA_STAGE_GUIDANCE
                    ].todo}
                  </dd>
                  <dt>Required information</dt>
                  <dd>
                    {MUDRA_STAGE_GUIDANCE[
                      code as keyof typeof MUDRA_STAGE_GUIDANCE
                    ].required}
                  </dd>
                  <dt>Next</dt>
                  <dd>
                    {MUDRA_STAGE_GUIDANCE[
                      code as keyof typeof MUDRA_STAGE_GUIDANCE
                    ].next}
                  </dd>
                </dl>
              </div>
            ) : null}
          </div>
        );
      })}
      {rejected ? (
        <div
          className="cx-process-step cx-process-static cx-mudra-rejected"
          data-testid="mudra-stage-REJECTED"
        >
          <span className="cx-process-step-copy">Rejected</span>
        </div>
      ) : null}
    </div>
  );
}

export function MudraExternalActions({
  workItem,
  processState,
  onChanged,
  onError,
  onCloseWorkspace,
}: MudraExternalActionsProps): React.JSX.Element | null {
  const stageCode = String(processState?.current_step?.code ?? '');
  const data =
    (workItem.operational_data as Record<string, unknown> | undefined) ?? {};
  const outcome = String(data.mudra_outcome ?? '').toUpperCase();
  const rejected = outcome === 'REJECTED';
  const closed = outcome === 'CLOSED' || stageCode === 'CLOSED';

  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<string>('');
  const [collapsed, setCollapsed] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});

  const setField = (key: string, value: string): void =>
    setForm((prev) => ({ ...prev, [key]: value }));
  const val = (key: string): string => String(form[key] ?? '');

  /*
   * Value-precedence fallback used ONLY by the APPLICATION-stage fields (the
   * only Mudra fields the owner is expected to revisit and re-save across
   * multiple Save / Save & Close cycles before review, so a reopened case or
   * a post-save refresh must show the authoritative persisted value, not a
   * blank local draft). Precedence: a local edit (including one that clears
   * a field to '') wins; otherwise the authoritative persisted value from
   * workItem.operational_data is shown; otherwise ''. This is a pure
   * read-time fallback over the existing `form`/`data` state - not a
   * duplicate persisted form model.
   */
  const applicationVal = (key: string): string =>
    Object.prototype.hasOwnProperty.call(form, key)
      ? String(form[key] ?? '')
      : String(data[key] ?? '');

  const run = async (
    action: string,
    payload: Row,
    closeAfter: boolean = false,
  ): Promise<void> => {
    setBusy(true);
    onError('');
    try {
      await act('work-items', String(workItem.id), action, payload);
      setPending('');
      setForm({});
      await onChanged();
      if (closeAfter) {
        onCloseWorkspace?.();
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Mudra action failed.');
      try {
        await onChanged();
      } catch {
        /* keep original error */
      }
    } finally {
      setBusy(false);
    }
  };

  if (!stageCode && !rejected) {
    return null;
  }

  // Terminal presentations.
  if (rejected) {
    return (
      <section className="cx-process-guidance cx-mudra-terminal cx-mudra-rejected-panel">
        <div style={{ width: '100%' }}>
          <strong>Mudra case rejected</strong>
          <p style={{ marginBottom: 0 }}>
            This case was assessed NOT ELIGIBLE and is terminal.
            {data.rejection_reason
              ? ` Reason: ${String(data.rejection_reason)}.`
              : ''}
          </p>
        </div>
      </section>
    );
  }
  if (closed) {
    return (
      <section className="cx-process-guidance cx-mudra-terminal cx-mudra-closed-panel">
        <div style={{ width: '100%' }}>
          <strong>Mudra case closed</strong>
          <p style={{ marginBottom: 0 }}>
            Disbursement recorded and the Mudra process is complete.
            {data.disbursed_amount
              ? ` Disbursed: ${String(data.disbursed_amount)}.`
              : ''}
          </p>
          <div
            className="cx-mudra-subsection"
            data-testid="mudra-current-stage-guidance"
          >
            <strong>Stage guidance</strong>
            <p className="cx-process-help">
              <b>What this stage means:</b> {MUDRA_STAGE_GUIDANCE.CLOSED.meaning}
            </p>
            <p className="cx-process-help">
              <b>Previous:</b> {MUDRA_STAGE_GUIDANCE.CLOSED.previous}
            </p>
            <p className="cx-process-help">
              <b>What you need to do:</b> {MUDRA_STAGE_GUIDANCE.CLOSED.todo}
            </p>
            <p className="cx-process-help">
              <b>Required information:</b> {MUDRA_STAGE_GUIDANCE.CLOSED.required}
            </p>
            <p className="cx-process-help">
              <b>Next:</b> {MUDRA_STAGE_GUIDANCE.CLOSED.next}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const title = MUDRA_STAGE_LABEL[stageCode] ?? stageCode;
  const stageGuidance =
    MUDRA_STAGE_GUIDANCE[
      stageCode as keyof typeof MUDRA_STAGE_GUIDANCE
    ];

  const field = (
    key: string,
    label: string,
    type: string = 'text',
    getValue: (key: string) => string = val,
  ): React.JSX.Element => (
    <label className="cx-field cx-mudra-field">
      <span>{label}</span>
      <input
        type={type}
        value={getValue(key)}
        aria-label={label}
        onChange={(event) => setField(key, event.target.value)}
      />
    </label>
  );

  const confirmRow = (
    key: string,
    selectLabel: string,
    confirmLabel: string,
    action: string,
    payload: () => Row,
    disabled: boolean = false,
  ): React.JSX.Element =>
    pending === key ? (
      <div className="cx-mudra-confirm-row">
        <span className="cx-udyam-selected-label" role="status">
          {selectLabel} selected
        </span>
        <button
          type="button"
          className="cx-btn subtle"
          disabled={busy}
          onClick={() => setPending('')}
        >
          Cancel
        </button>
        <button
          type="button"
          className="cx-btn cx-udyam-primary-action"
          disabled={busy || disabled}
          onClick={() => {
            void run(action, payload());
          }}
        >
          {busy ? 'Saving...' : confirmLabel}
        </button>
      </div>
    ) : (
      <button
        type="button"
        className="cx-btn cx-udyam-primary-action"
        disabled={busy || disabled}
        aria-pressed={false}
        onClick={() => setPending(key)}
      >
        {selectLabel}
      </button>
    );

  let body: React.JSX.Element = <div />;

  if (stageCode === 'APPLICATION') {
    // While the case awaits or is under internal review, the backend no
    // longer accepts edits here (ownership.can_edit_work_item gate on
    // mudra-complete-application) - show a clear, non-editable status
    // instead of a form that would fail on submit.
    if (String(workItem.status ?? '') === 'READY_FOR_REVIEW') {
      body = (
        <div className="cx-mudra-stage-body">
          <p className="cx-mudra-hint">
            Application & KYC submitted for internal review. Credit &amp;
            Eligibility becomes available once the reviewer approves.
          </p>
        </div>
      );
    } else {
      const applicationFieldsPayload = (): Row => ({
        requested_loan_amount: applicationVal('requested_loan_amount'),
        loan_purpose: applicationVal('loan_purpose'),
        business_activity: applicationVal('business_activity'),
        application_reference: applicationVal('application_reference'),
        application_date: applicationVal('application_date'),
      });
      const applicationDisabled =
        !applicationVal('requested_loan_amount') ||
        !applicationVal('loan_purpose');
      body = (
        <div className="cx-mudra-stage-body">
          <p className="cx-mudra-hint">
            Business checkpoints: Lead, Application, Customer KYC, Checklist,
            Document Tagging. Record the application details using Save or
            Save &amp; Close, then use Submit for Review above to send the
            case for internal review. Credit &amp; Eligibility becomes
            available once the reviewer approves.
          </p>
          {field(
            'requested_loan_amount',
            'Requested loan amount',
            'text',
            applicationVal,
          )}
          {field('loan_purpose', 'Loan purpose', 'text', applicationVal)}
          {field(
            'business_activity',
            'Business activity',
            'text',
            applicationVal,
          )}
          {field(
            'application_reference',
            'Application reference',
            'text',
            applicationVal,
          )}
          {field(
            'application_date',
            'Application date',
            'date',
            applicationVal,
          )}
          {/*
            UX-parity correction: Application/KYC persistence is presented as
            the same Save / Save & Close pair the generic workspace uses
            elsewhere - not a third, differently-named action - even though
            both buttons call the dedicated mudra-complete-application
            endpoint internally (the generic Work update path cannot persist
            operational_data; see _deny_operational_data_writes). Neither
            button advances the process position - that remains owned
            exclusively by reviewer approval. Submit for Review is a
            separate action (in reviewButtons, above) and is never invoked
            here.
          */}
          <div className="cx-mudra-decision-row">
            <button
              type="button"
              className="cx-btn cx-udyam-primary-action"
              disabled={busy || applicationDisabled}
              onClick={() => {
                void run(
                  'mudra-complete-application',
                  applicationFieldsPayload(),
                  false,
                );
              }}
            >
              {busy ? 'Saving...' : 'Save'}
            </button>
            <button
              type="button"
              className="cx-btn"
              disabled={busy || applicationDisabled}
              onClick={() => {
                void run(
                  'mudra-complete-application',
                  applicationFieldsPayload(),
                  true,
                );
              }}
            >
              {busy ? 'Saving...' : 'Save & Close'}
            </button>
          </div>
        </div>
      );
    }
  } else if (stageCode === 'CREDIT_ELIGIBILITY') {
    const cibilRecorded = Boolean(String(data.cibil_score ?? ''));
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoints: CIBIL Check, then Eligibility Check. Record CIBIL
          first, then decide eligibility. Not Eligible rejects the case.
        </p>
        <div className="cx-mudra-subsection">
          <strong>CIBIL check</strong>
          {cibilRecorded ? (
            <p className="cx-mudra-recorded">
              CIBIL recorded: score {String(data.cibil_score)}
              {data.cibil_result ? ` (${String(data.cibil_result)})` : ''}.
            </p>
          ) : null}
          {field('cibil_score', 'CIBIL score')}
          {field('cibil_bureau', 'CIBIL bureau')}
          {field('cibil_check_date', 'CIBIL check date', 'date')}
          {field('cibil_result', 'CIBIL result')}
          {field('cibil_report_reference', 'CIBIL report reference')}
          {confirmRow(
            'CIBIL',
            'Record CIBIL',
            'Save CIBIL',
            'mudra-record-cibil',
            () => ({
              cibil_score: val('cibil_score'),
              cibil_bureau: val('cibil_bureau'),
              cibil_check_date: val('cibil_check_date'),
              cibil_result: val('cibil_result'),
              cibil_report_reference: val('cibil_report_reference'),
              cibil_remarks: val('cibil_remarks'),
            }),
            !val('cibil_score'),
          )}
        </div>
        <div className="cx-mudra-subsection">
          <strong>Eligibility decision</strong>
          {field('eligibility_date', 'Eligibility date', 'date')}
          <label className="cx-field cx-mudra-field">
            <span>Rejection reason (required if Not Eligible)</span>
            <input
              type="text"
              value={val('rejection_reason')}
              aria-label="Rejection reason"
              onChange={(event) => setField('rejection_reason', event.target.value)}
            />
          </label>
          <div className="cx-mudra-decision-row">
            {confirmRow(
              'ELIGIBLE',
              'Mark Eligible',
              'Save & Continue to File Preparation',
              'mudra-decide-eligibility',
              () => ({
                eligibility_result: 'ELIGIBLE',
                eligibility_date: val('eligibility_date'),
              }),
              !cibilRecorded,
            )}
            {confirmRow(
              'NOT_ELIGIBLE',
              'Mark Not Eligible (reject)',
              'Save & Reject Case',
              'mudra-decide-eligibility',
              () => ({
                eligibility_result: 'NOT_ELIGIBLE',
                eligibility_date: val('eligibility_date'),
                rejection_reason: val('rejection_reason'),
              }),
              !val('rejection_reason'),
            )}
          </div>
        </div>
      </div>
    );
  } else if (stageCode === 'FILE_PREPARATION') {
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoint: Project Report. Confirm the project report is
          prepared, then advance to Bank Submitted.
        </p>
        {field('project_report_prepared', 'Project report prepared (YES/NO)')}
        {field('project_report_date', 'Project report date', 'date')}
        {confirmRow(
          'FILEPREP',
          'Complete File Preparation',
          'Save & Move to Bank Submitted',
          'mudra-complete-file-preparation',
          () => ({
            project_report_prepared: val('project_report_prepared'),
            project_report_date: val('project_report_date'),
          }),
          !val('project_report_prepared'),
        )}
      </div>
    );
  } else if (stageCode === 'BANK_SUBMITTED') {
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoints: Bank Transfer, then Bank Received. Record the
          file transfer and the bank acknowledgement, then advance to Bank
          Verification.
        </p>
        {field('bank_name', 'Bank name')}
        {field('bank_branch', 'Bank branch')}
        {field('bank_file_transfer_date', 'File transfer date', 'date')}
        {field('bank_reference', 'Bank reference')}
        {field('bank_acknowledgement_date', 'Bank acknowledgement date', 'date')}
        {confirmRow(
          'BANKSUB',
          'Record Bank Submission',
          'Save & Move to Bank Verification',
          'mudra-record-bank-submission',
          () => ({
            bank_name: val('bank_name'),
            bank_branch: val('bank_branch'),
            bank_file_transfer_date: val('bank_file_transfer_date'),
            bank_reference: val('bank_reference'),
            bank_acknowledgement_date: val('bank_acknowledgement_date'),
          }),
          !val('bank_name') || !val('bank_acknowledgement_date'),
        )}
      </div>
    );
  } else if (stageCode === 'BANK_VERIFICATION') {
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoint: Bank Verification. Record the verification
          outcome. CLEAR proceeds to RO Review; PENDING moves to Bank Pending.
        </p>
        {field('bank_verification_date', 'Verification date', 'date')}
        {field('bank_verification_remarks', 'Verification remarks')}
        <div className="cx-mudra-decision-row">
          {confirmRow(
            'VERIFY_CLEAR',
            'Mark Clear',
            'Save & Move to RO Review',
            'mudra-record-bank-verification',
            () => ({
              bank_verification_status: 'CLEAR',
              bank_verification_date: val('bank_verification_date'),
              bank_verification_remarks: val('bank_verification_remarks'),
            }),
          )}
          {confirmRow(
            'VERIFY_PENDING',
            'Mark Pending',
            'Save & Move to Bank Pending',
            'mudra-record-bank-verification',
            () => ({
              bank_verification_status: 'PENDING',
              bank_verification_date: val('bank_verification_date'),
              bank_verification_remarks: val('bank_verification_remarks'),
            }),
          )}
        </div>
      </div>
    );
  } else if (stageCode === 'BANK_PENDING') {
    const task =
      (data.mudra_pending_task as Record<string, unknown> | undefined) ?? {};
    const taskStatus = String(task.status ?? '');
    const hasActive = taskStatus === 'OPEN' || taskStatus === 'RECEIVED';
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Bank Pending loop: raise the pending requirement, assign/reassign,
          record received information, then complete Re-QC to return to Bank
          Verification (the verification decision is then made again).
        </p>
        {hasActive ? (
          <div className="cx-mudra-subsection cx-mudra-pending-active">
            <strong>Active pending task</strong>
            <p className="cx-mudra-recorded">
              Status: {taskStatus}. Reason: {String(task.reason ?? '')}.
              {task.requested_info
                ? ` Requested: ${String(task.requested_info)}.`
                : ''}
              {task.assignee_user_id
                ? ` Assignee: ${String(task.assignee_user_id)}.`
                : ''}
              {task.evidence ? ` Evidence: ${String(task.evidence)}.` : ''}
            </p>
            {/* One active pending-operation form at a time. */}
            {taskStatus === 'OPEN' ? (
              <>
                {field('pending_assignee_user_id', 'Reassign to (user id)')}
                {confirmRow(
                  'REASSIGN',
                  'Reassign Pending Task',
                  'Save Reassignment',
                  'mudra-reassign-pending-task',
                  () => ({
                    pending_assignee_user_id: val('pending_assignee_user_id'),
                  }),
                  !val('pending_assignee_user_id'),
                )}
                {field('pending_evidence', 'Information / evidence received')}
                {confirmRow(
                  'EVIDENCE',
                  'Record Received Information',
                  'Save Received Information',
                  'mudra-record-pending-evidence',
                  () => ({ pending_evidence: val('pending_evidence') }),
                  !val('pending_evidence'),
                )}
              </>
            ) : (
              confirmRow(
                'REQC',
                'Complete Re-QC',
                'Save & Return to Bank Verification',
                'mudra-complete-reqc',
                () => ({}),
              )
            )}
          </div>
        ) : (
          <div className="cx-mudra-subsection">
            <strong>Raise pending requirement</strong>
            {field('pending_reason', 'Pending reason')}
            {field('pending_requested_info', 'Requested information / document')}
            {field('pending_assignee_user_id', 'Assign to (user id)')}
            {confirmRow(
              'RAISE',
              'Raise Pending Task',
              'Save Pending Task',
              'mudra-raise-pending-task',
              () => ({
                pending_reason: val('pending_reason'),
                pending_requested_info: val('pending_requested_info'),
                pending_assignee_user_id: val('pending_assignee_user_id'),
              }),
              !val('pending_reason'),
            )}
          </div>
        )}
      </div>
    );
  } else if (stageCode === 'RO_REVIEW') {
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoint: RO Review. Record the RO review outcome and
          advance to Sanctioned.
        </p>
        {field('ro_name', 'RO name')}
        {field('ro_review_status', 'RO review status')}
        {field('ro_review_date', 'RO review date', 'date')}
        {field('ro_review_remarks', 'RO review remarks')}
        {confirmRow(
          'RO',
          'Complete RO Review',
          'Save & Move to Sanctioned',
          'mudra-complete-ro-review',
          () => ({
            ro_name: val('ro_name'),
            ro_review_status: val('ro_review_status'),
            ro_review_date: val('ro_review_date'),
            ro_review_remarks: val('ro_review_remarks'),
          }),
          !val('ro_review_status'),
        )}
      </div>
    );
  } else if (stageCode === 'SANCTIONED') {
    const sanctionRecorded = Boolean(String(data.sanctioned_amount ?? ''));
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoints: Sanction, then Sanction Conditions. Record the
          sanction first; disbursement is blocked until conditions are complete.
        </p>
        <div className="cx-mudra-subsection">
          <strong>Sanction</strong>
          {sanctionRecorded ? (
            <p className="cx-mudra-recorded">
              Sanction recorded: {String(data.sanctioned_amount)}.
            </p>
          ) : null}
          {field('sanctioned_amount', 'Sanctioned amount')}
          {field('sanction_date', 'Sanction date', 'date')}
          {field('sanction_reference', 'Sanction reference')}
          {field('sanction_remarks', 'Sanction remarks')}
          {confirmRow(
            'SANCTION',
            'Record Sanction',
            'Save Sanction',
            'mudra-record-sanction',
            () => ({
              sanctioned_amount: val('sanctioned_amount'),
              sanction_date: val('sanction_date'),
              sanction_reference: val('sanction_reference'),
              sanction_remarks: val('sanction_remarks'),
            }),
            !val('sanctioned_amount'),
          )}
        </div>
        <div className="cx-mudra-subsection">
          <strong>Sanction conditions</strong>
          {field(
            'sanction_conditions_completed_date',
            'Conditions completed date',
            'date',
          )}
          {confirmRow(
            'CONDITIONS',
            'Complete Sanction Conditions',
            'Save & Move to Disbursement',
            'mudra-complete-sanction-conditions',
            () => ({
              sanction_conditions_status: 'COMPLETE',
              sanction_conditions_completed_date: val(
                'sanction_conditions_completed_date',
              ),
            }),
            !sanctionRecorded,
          )}
        </div>
      </div>
    );
  } else if (stageCode === 'DISBURSEMENT') {
    const ready = String(data.mudra_disbursement_ready ?? '') === 'YES';
    body = (
      <div className="cx-mudra-stage-body">
        <p className="cx-mudra-hint">
          Business checkpoints: Disbursement Ready, then Disbursement. Mark ready
          first; actual disbursement closes the case.
        </p>
        <div className="cx-mudra-subsection">
          <strong>Disbursement ready</strong>
          {ready ? (
            <p className="cx-mudra-recorded">
              Marked ready on {String(data.disbursement_ready_date ?? '')}.
            </p>
          ) : null}
          {field('disbursement_ready_date', 'Disbursement ready date', 'date')}
          {confirmRow(
            'READY',
            'Mark Disbursement Ready',
            'Save Ready',
            'mudra-mark-disbursement-ready',
            () => ({ disbursement_ready_date: val('disbursement_ready_date') }),
            !val('disbursement_ready_date'),
          )}
        </div>
        <div className="cx-mudra-subsection">
          <strong>Actual disbursement</strong>
          {field('disbursed_amount', 'Disbursed amount')}
          {field('disbursement_date', 'Disbursement date', 'date')}
          {field('disbursement_reference', 'Disbursement reference')}
          {confirmRow(
            'DISBURSE',
            'Record Disbursement',
            'Save & Close Case',
            'mudra-record-disbursement',
            () => ({
              disbursed_amount: val('disbursed_amount'),
              disbursement_date: val('disbursement_date'),
              disbursement_reference: val('disbursement_reference'),
            }),
            !ready || !val('disbursed_amount') || !val('disbursement_date'),
          )}
        </div>
      </div>
    );
  }

  return (
    <section className="cx-process-guidance cx-mudra-action-shell">
      <div style={{ width: '100%' }}>
        <div className="cx-udyam-action-shell-header">
          <div className="cx-udyam-action-shell-heading">
            <strong>{`Mudra: ${title}`}</strong>
            {collapsed ? (
              <span className="cx-udyam-action-shell-summary">
                Current stage: {title}
              </span>
            ) : null}
          </div>
          <button
            type="button"
            className="cx-btn subtle cx-udyam-action-shell-toggle"
            aria-expanded={!collapsed}
            aria-label={collapsed ? 'Expand Mudra panel' : 'Collapse Mudra panel'}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        </div>
        {!collapsed ? (
          <div className="cx-udyam-action-shell-body">
            {stageGuidance ? (
              <div
                className="cx-mudra-subsection"
                data-testid="mudra-current-stage-guidance"
              >
                <strong>Stage guidance</strong>
                <p className="cx-process-help">
                  <b>What this stage means:</b> {stageGuidance.meaning}
                </p>
                <p className="cx-process-help">
                  <b>Previous:</b> {stageGuidance.previous}
                </p>
                <p className="cx-process-help">
                  <b>What you need to do:</b> {stageGuidance.todo}
                </p>
                <p className="cx-process-help">
                  <b>Required information:</b> {stageGuidance.required}
                </p>
                <p className="cx-process-help">
                  <b>Next:</b> {stageGuidance.next}
                </p>

                {stageGuidance.actions.length > 0 ? (
                  <div>
                    <strong>Stage actions</strong>
                    <ul className="cx-process-help">
                      {stageGuidance.actions.map((actionHelp) => (
                        <li key={actionHelp}>{actionHelp}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {body}
          </div>
        ) : null}
      </div>
    </section>
  );
}


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
      label: 'Uploaded • pending review',
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
              Loading fields for the selected service…
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
                  )} · ${String(
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
          No eligible document contact exists for this client. Add or enable one under Client · Contacts.
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
                      ? '✓'
                      : visualState.key === 'REJECTED'
                        ? '!'
                        : visualState.key ===
                            'PENDING_REVIEW'
                          ? '…'
                          : '›'}
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
                <p style={{ whiteSpace: 'pre-wrap' }}>{entry}</p>
              ) : null}

              {detail ? (
                <small>{detail}</small>
              ) : null}

              {fromStatus && toStatus ? (
                <small>
                  {label(fromStatus)}
                  {' → '}
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
  | {
      kind: 'APPROVE';
      label: 'Approve & complete' | 'Approve & continue';
    }
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

  // The server serializer owns Udyam process-owned evidence: for the Udyam
  // service it preserves the reserved lifecycle keys from the database and
  // ignores any incoming values for them.  The frontend therefore no longer
  // needs to strip udyam_* keys before a generic save.

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
  closeAfterSave: boolean = true,
  onSaved: (() => void) | null = null,
): Promise<void> {
  try {
    const reviewerOnlyAction =
      editing.can_review === true &&
      editing.can_edit !== true &&
      (
        pendingAction?.kind === 'APPROVE' ||
        pendingAction?.kind === 'RETURN_FOR_REWORK'
      );

    if (reviewerOnlyAction && pendingAction) {
      const workItemId = String(editing.id ?? '');

      if (!workItemId) {
        throw new Error(
          'A saved work item is required for reviewer action.',
        );
      }

      await executePendingWorkAction(
        workItemId,
        pendingAction,
      );

      setError('');
      // Reviewer workflow actions always conclude the edit and return to the
      // list, matching existing behaviour.
      closeDrawer();
      reload();
      return;
    }

    const saved = await save(
      'work-items',
      cleanWorkItemPayload(editing),
    );

    const workItemId = String(
      saved.id ?? editing.id ?? '',
    );

    if (pendingAction) {
      if (!workItemId) {
        throw new Error(
          'Save the work item before applying a workflow action.',
        );
      }

      await executePendingWorkAction(
        workItemId,
        pendingAction,
      );
    }

    setError('');

    // A workflow action (pendingAction) always concludes by returning to the
    // list, preserving the existing save-gated behaviour.  A plain record save
    // honours the caller intent: Save keeps the drawer open; Save & Close
    // closes only after successful persistence.
    if (pendingAction || closeAfterSave) {
      closeDrawer();
      reload();
    } else {
      reload();
      if (onSaved) {
        onSaved();
      }
    }
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

/*
 * Centralized, pure top-workflow-action eligibility.
 *
 * workPrimaryAction(status) is generic and status-only - it has no knowledge
 * of a service's own durable business process. For most services that is
 * correct: IN_PROGRESS genuinely means "ready to submit for review". For a
 * service with its own coordinated business lifecycle (WorkProcessState),
 * SUBMIT_FOR_REVIEW is only valid while that lifecycle is still at its
 * pre-review position - once it has advanced, the service's own business
 * process owns the primary action and generic review must not reappear.
 *
 * This reuses the exact conditions already established for Udyam and Mudra
 * (previously duplicated inline in reviewButtons) as the one place that
 * decides top-action eligibility, so production render code and tests can
 * share the identical logic - not a new workflow engine, only a
 * reconciliation of the existing generic status-only helper against
 * existing per-service process state.
 */
export function deriveWorkspacePrimaryAction(params: {
  serviceCode: string;
  status: unknown;
  processStepCode: string;
  nextActionCode?: string;
}): WorkPrimaryAction {
  const generic = workPrimaryAction(params.status);

  if (generic !== 'SUBMIT_FOR_REVIEW') {
    // RESUME_WORK and null are unaffected by process-stage reconciliation.
    return generic;
  }

  const serviceCode = params.serviceCode;
  const processStepCode = params.processStepCode;
  const nextActionCode = String(params.nextActionCode ?? '');

  if (serviceCode === 'UDYAM_REGISTRATION') {
    const udyamPostReviewAction =
      nextActionCode === 'SUBMIT_UDYAM_APPLICATION' ||
      nextActionCode === 'AWAIT_UDYAM_OUTCOME' ||
      nextActionCode === 'RESOLVE_UDYAM_QUERY' ||
      nextActionCode === 'COMPLETE_UDYAM_REGISTRATION';

    const udyamPostReviewProcessStep =
      processStepCode === 'SUBMIT_APPLICATION' ||
      processStepCode === 'APPLICATION_SUBMISSION' ||
      processStepCode === 'QUERY_RESOLUTION' ||
      processStepCode === 'COMPLETION';

    if (udyamPostReviewAction || udyamPostReviewProcessStep) {
      return null;
    }
    return generic;
  }

  if (serviceCode === 'MUDRA_LOAN') {
    if (Boolean(processStepCode) && processStepCode !== 'APPLICATION') {
      return null;
    }
    return generic;
  }

  // Any other service (or no service): generic behaviour, unchanged.
  return generic;
}

/*
 * Testability-only extraction of the exact stale-pendingAction reconciliation
 * decision that refreshOpenWorkWorkspace already performs in its `finally`
 * block. This function owns no new logic and changes no runtime behavior -
 * it is the same expression, unchanged, given a name and exported so it can
 * be tested directly against the real production decision rather than a
 * re-simulation of it. refreshOpenWorkWorkspace calls this function instead
 * of inlining the expression; the side effect (setPendingAction) stays where
 * it always was, at the call site, not inside this pure function.
 *
 * Returns the pendingAction unchanged when there is nothing to reconcile
 * (wrong kind, or no fresh row available - e.g. the authoritative refresh
 * itself failed and this must not clear a selection based on data it never
 * obtained), or null when the fresh authoritative state proves the selected
 * SUBMIT_FOR_REVIEW action is no longer valid.
 */
export function reconcileStalePendingAction(params: {
  pendingAction: PendingWorkAction | null;
  freshRow: Row | null;
  freshProcessState: WorkProcessStateSnapshot | null;
  freshHealthSnapshot: WorkHealthSnapshot | null;
  freshServiceCode: string;
}): PendingWorkAction | null {
  const {
    pendingAction,
    freshRow,
    freshProcessState,
    freshHealthSnapshot,
    freshServiceCode,
  } = params;

  if (pendingAction?.kind !== 'SUBMIT_FOR_REVIEW' || !freshRow) {
    return pendingAction;
  }

  const reconciledAction = deriveWorkspacePrimaryAction({
    serviceCode: freshServiceCode,
    status: freshRow.status,
    processStepCode: String(
      freshProcessState?.current_step?.code ?? '',
    ),
    nextActionCode: String(
      freshHealthSnapshot?.next_action?.code ?? '',
    ),
  });

  return reconciledAction !== 'SUBMIT_FOR_REVIEW' ? null : pendingAction;
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


/*
 * reconcileOpenWorkspace  (Requirement 1 / P0)
 *
 * After a workflow mutation that can change Work status or process position
 * (especially completion), the open workspace must reconcile from authoritative
 * server state.  The RELEASE-CRITICAL step is that the open `editing` WorkItem
 * is replaced by the freshly fetched authoritative WorkItem, because the
 * terminal projection is anchored to `editing.status === 'COMPLETED'`.
 *
 * The previous implementation fetched WorkItem + Health + Process in a single
 * Promise.all.  If the combined request rejected (or a projection failed) the
 * whole batch was caught and `editing` stayed stale (e.g. IN_PROGRESS) while
 * Health had already advanced elsewhere, so the tracker fell back to Stage 2
 * and re-exposed Submit for Review on an already-completed record.
 *
 * This helper fixes the reconciliation boundary:
 *   1. The authoritative WorkItem is fetched FIRST and independently.  On
 *      success `editing` is replaced immediately (reconciled).  On failure it
 *      surfaces an explicit error via onWorkItemError and does NOT fabricate a
 *      completed record or silently leave a contradictory editable state.
 *   2. Health and Process are then fetched as NON-FATAL projections.  A failure
 *      there records a projection error but never blocks or reverts the
 *      authoritative WorkItem reconciliation from step 1.
 *
 * It is a pure orchestration function (all IO and state writes are injected),
 * so the real completion-reconciliation sequence can be tested directly.
 */
export async function reconcileOpenWorkspace(deps: {
  workItemId: string;
  fetchObject: (path: string) => Promise<Row>;
  setEditing: (row: Row) => void;
  setWorkHealth: (snapshot: WorkHealthSnapshot | null) => void;
  setWorkProcessState: (
    snapshot: WorkProcessStateSnapshot | null,
  ) => void;
  onWorkItemError: (message: string) => void;
  onProjectionError: (message: string) => void;
  clearError: () => void;
}): Promise<boolean> {
  const {
    workItemId,
    fetchObject,
    setEditing,
    setWorkHealth,
    setWorkProcessState,
    onWorkItemError,
    onProjectionError,
    clearError,
  } = deps;

  // Step 1 - authoritative WorkItem refetch (release-critical reconciliation).
  try {
    const freshWorkItem = await fetchObject(
      `work-items/${workItemId}`,
    );
    setEditing({ ...freshWorkItem });
    clearError();
  } catch (error) {
    /*
     * The authoritative refresh failed.  Do NOT silently return the user to a
     * contradictory editable state and do NOT fabricate a completed record.
     * Surface the failure through the existing error channel so the analyst can
     * retry (reopen) the record.  The stale editing snapshot is left untouched
     * rather than being wrongly presented as reconciled.
     */
    onWorkItemError(
      String(
        error instanceof Error
          ? `Could not refresh this work item after the last action. ` +
            `Please reopen it to see its current state. (${error.message})`
          : error,
      ),
    );
    return false;
  }

  // Step 2 - dependent projections are non-fatal.
  try {
    const [freshHealth, freshProcessState] = await Promise.all([
      fetchObject(`work-items/${workItemId}/health`),
      fetchObject(`work-items/${workItemId}/process-step`),
    ]);

    setWorkHealth(
      isWorkHealthSnapshot(freshHealth) ? freshHealth : null,
    );
    setWorkProcessState(
      isWorkProcessStateSnapshot(freshProcessState)
        ? freshProcessState
        : null,
    );
  } catch (error) {
    /*
     * A projection hiccup must never revert the authoritative WorkItem that was
     * already reconciled in step 1.  Record the projection error only.  The
     * terminal invariant still holds because it is anchored to editing.status.
     */
    onProjectionError(
      String(error instanceof Error ? error.message : error),
    );
  }

  return true;
}


/*
 * UdyamWorkflowConfirm
 *
 * The confirmation surface for a selected generic Udyam lifecycle action.  It
 * renders inside the TOP workflow zone so the analyst completes the workflow in
 * one place (V1.3 fix).  It reuses the caller's canonical submit() path and the
 * existing pendingAction state; it introduces no new persistence and no second
 * pending-action state.
 *
 * Exported for rendered workspace tests.
 */
export function UdyamWorkflowConfirm({
  pendingAction,
  canEdit,
  onCommentChange,
  onConfirm,
  onCancel,
}: {
  pendingAction: PendingWorkAction | null;
  canEdit: boolean;
  onCommentChange: (comment: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}): React.JSX.Element | null {
  if (!pendingAction) return null;

  const isReturn = pendingAction.kind === 'RETURN_FOR_REWORK';
  const returnComment = isReturn ? (pendingAction as { comment: string }).comment : '';
  const confirmDisabled = isReturn && !returnComment.trim();

  return (
    <div
      className="cx-workflow-confirm"
      role="group"
      aria-label="Confirm workflow action"
    >
      {isReturn ? (
        <div className="cx-field cx-workflow-confirm-field">
          <label htmlFor="udyam-reviewer-return-justification">
            Reviewer return justification *
          </label>
          <textarea
            id="udyam-reviewer-return-justification"
            value={returnComment}
            onChange={(event) => onCommentChange(event.target.value)}
          />
        </div>
      ) : null}

      <div className="cx-workflow-confirm-actions">
        <button
          type="button"
          className={isReturn ? 'cx-btn danger' : 'cx-btn'}
          disabled={confirmDisabled}
          onClick={onConfirm}
        >
          {canEdit ? `Save & ${pendingAction.label}` : `Confirm ${pendingAction.label}`}
        </button>
        <button type="button" className="cx-btn subtle" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}


/*
 * Change 2: scalable searchable Client selector with inline "Add New Client".
 *
 * Reuses the existing Client contracts:
 *  - reads the already-loaded client rows (no second Client model / no second
 *    list endpoint) and filters them by name as the analyst types, rendering
 *    only the matching subset (capped) instead of hundreds of <option>s;
 *  - creates a client through the existing `save('clients', ...)` API, which
 *    goes through the authoritative ClientSerializer + ClientAccessPermission.
 *
 * It never mutates the parent Work draft except through `onChange(client_id)`,
 * so partially-entered Work Item data is preserved across search, open/close of
 * the add-client form, and successful/failed client creation. On successful
 * creation it calls `onClientCreated` so the parent can reload the client list
 * and select the new client.
 */
type SearchableClientSelectProps = {
  clients: Row[];
  value: string;
  onChange: (clientId: string) => void;
  onClientCreated: (client: Row) => void;
  disabled?: boolean;
};

function clientDisplayName(row: Row | undefined | null): string {
  if (!row) return '';
  return String(
    row.trade_name ||
    row.display_name ||
    row.legal_name ||
    row.business_name ||
    row.client_name ||
    row.name ||
    '',
  ).trim();
}

const CLIENT_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'INDIVIDUAL', label: 'Individual' },
  { value: 'PROPRIETORSHIP', label: 'Proprietorship' },
  { value: 'PARTNERSHIP', label: 'Partnership' },
  { value: 'LLP', label: 'LLP' },
  { value: 'PRIVATE_LIMITED', label: 'Private Limited Company' },
  { value: 'PUBLIC_LIMITED', label: 'Public Limited Company' },
  { value: 'TRUST', label: 'Trust' },
  { value: 'OTHER', label: 'Other' },
];

const CLIENT_RESULT_LIMIT = 20;

export function SearchableClientSelect({
  clients,
  value,
  onChange,
  onClientCreated,
  disabled = false,
}: SearchableClientSelectProps): React.JSX.Element {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newLegalName, setNewLegalName] = useState('');
  const [newClientType, setNewClientType] = useState('INDIVIDUAL');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  // Clients created via "+ Add New Client" during this session. The parent's
  // reload() of the shared client list is asynchronous, so until it resolves a
  // just-created client would not yet be in `clients`. Merging it here makes the
  // new client immediately searchable and selectable (and keeps the selected
  // label resolvable) without waiting on the network round-trip. Once reload
  // resolves, the same client also arrives in `clients`; de-duplication by id
  // keeps it appearing once.
  const [locallyCreated, setLocallyCreated] = useState<Row[]>([]);

  const mergedClients = (() => {
    if (locallyCreated.length === 0) return clients;
    const existingIds = new Set(clients.map((row) => String(row.id ?? '')));
    const extras = locallyCreated.filter(
      (row) => !existingIds.has(String(row.id ?? '')),
    );
    return extras.length ? [...clients, ...extras] : clients;
  })();

  const selectedRow =
    mergedClients.find((row) => String(row.id ?? '') === String(value ?? '')) ??
    null;

  const normalizedQuery = query.trim().toLowerCase();

  const matches = (
    normalizedQuery
      ? mergedClients.filter((row) =>
          clientDisplayName(row).toLowerCase().includes(normalizedQuery) ||
          String(row.legal_name ?? '').toLowerCase().includes(normalizedQuery) ||
          String(row.pan ?? '').toLowerCase().includes(normalizedQuery),
        )
      : mergedClients
  ).slice(0, CLIENT_RESULT_LIMIT);

  const selectExisting = (clientId: string): void => {
    onChange(clientId);
    setOpen(false);
    setQuery('');
  };

  const clearSelection = (): void => {
    onChange('');
    setQuery('');
    setOpen(true);
  };

  const submitNewClient = async (): Promise<void> => {
    const legalName = newLegalName.trim();
    if (!legalName) {
      setCreateError('Client legal name is required.');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      // Uses the existing Client API + serializer. lifecycle_status defaults to
      // PROSPECT server-side, so PAN is not required for this minimal create.
      const created = await save('clients', {
        legal_name: legalName,
        client_type: newClientType,
      });
      const createdId = String(created.id ?? '');
      // Make the new client available in THIS selector immediately (before the
      // parent's async reload resolves), then notify the parent so it can reload
      // the shared list and select the client. The Work draft is untouched.
      if (createdId) {
        setLocallyCreated((prev) => [
          ...prev.filter((row) => String(row.id ?? '') !== createdId),
          created,
        ]);
      }
      onClientCreated(created);
      setAdding(false);
      setNewLegalName('');
      setNewClientType('INDIVIDUAL');
      setOpen(false);
      setQuery('');
    } catch (error) {
      setCreateError(
        error instanceof Error ? error.message : 'Failed to create client.',
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="cx-client-select">
      {selectedRow && !open ? (
        <div className="cx-client-select-selected">
          <span className="cx-client-select-name">
            {clientDisplayName(selectedRow)}
          </span>
          {!disabled ? (
            <button
              type="button"
              className="cx-btn subtle"
              onClick={clearSelection}
            >
              Change
            </button>
          ) : null}
        </div>
      ) : (
        <>
          <input
            type="text"
            className="cx-client-select-input"
            placeholder="Search clients by name..."
            value={query}
            disabled={disabled}
            aria-label="Search clients"
            onFocus={() => setOpen(true)}
            onChange={(event) => {
              setQuery(event.target.value);
              setOpen(true);
            }}
          />
          {open && !disabled ? (
            <div className="cx-client-select-menu" role="listbox">
              {matches.length > 0 ? (
                matches.map((row) => (
                  <button
                    type="button"
                    key={String(row.id)}
                    className="cx-client-select-option"
                    role="option"
                    aria-selected={String(row.id ?? '') === String(value ?? '')}
                    onClick={() => selectExisting(String(row.id))}
                  >
                    {clientDisplayName(row)}
                  </button>
                ))
              ) : (
                <div className="cx-client-select-empty">
                  No matching clients.
                </div>
              )}

              {!adding ? (
                <button
                  type="button"
                  className="cx-client-select-add"
                  onClick={() => {
                    setAdding(true);
                    setCreateError('');
                    if (normalizedQuery) setNewLegalName(query.trim());
                  }}
                >
                  + Add New Client
                </button>
              ) : (
                <div className="cx-client-select-newform">
                  <div className="cx-field">
                    <label>Legal name *</label>
                    <input
                      type="text"
                      value={newLegalName}
                      onChange={(event) => setNewLegalName(event.target.value)}
                      aria-label="New client legal name"
                    />
                  </div>
                  <div className="cx-field">
                    <label>Client type</label>
                    <select
                      value={newClientType}
                      onChange={(event) => setNewClientType(event.target.value)}
                      aria-label="New client type"
                    >
                      {CLIENT_TYPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  {createError ? (
                    <div className="cx-client-select-error" role="alert">
                      {createError}
                    </div>
                  ) : null}
                  <div className="cx-client-select-newactions">
                    <button
                      type="button"
                      className="cx-btn subtle"
                      disabled={creating}
                      onClick={() => {
                        setAdding(false);
                        setCreateError('');
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="cx-btn"
                      disabled={creating || !newLegalName.trim()}
                      onClick={() => {
                        void submitNewClient();
                      }}
                    >
                      {creating ? 'Creating...' : 'Create & Select Client'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

export function WorkArea({
  initialVerticalId,
  initialWorkItemId,
  onInitialWorkOpened,
  initialQuickAction,
  onInitialQuickActionHandled,
}: {
  initialVerticalId?: string | undefined;
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
  const [listVerticalId, setListVerticalId] = useState(
    initialVerticalId ?? '',
  );

  useEffect(() => {
    setListVerticalId(initialVerticalId ?? '');
  }, [initialVerticalId]);

  const params = useMemo(
    () => ({
      ...(statusFilter
        ? { status: statusFilter }
        : {}),
      ...(listVerticalId
        ? { vertical_id: listVerticalId }
        : {}),
    }),
    [statusFilter, listVerticalId],
  );

  const work = useList('work-items', params);
  const [editing, setEditing] = useState<Row | null>(null);

  /*
   * Correction 2 (V1.4.1): frontend-only reconciliation safety state.
   *
   * If a workflow mutation succeeds on the server but the authoritative
   * WorkItem refetch subsequently fails, the workspace must NOT continue
   * presenting stale lifecycle controls (the server state is now unknown).
   * This flag activates a "refresh required" mode that:
   *   - suppresses all lifecycle controls (workflow zone and footer)
   *   - suppresses Save / Save & Close (server state is unknown)
   *   - shows an explicit "Refresh Work" recovery action
   *
   * This is NOT a business workflow state.  It is never persisted, never
   * sent to the backend, and does not change Work status semantics.
   * It clears automatically when a subsequent reconciliation succeeds.
   */
  const [workspaceNeedsRefresh, setWorkspaceNeedsRefresh] =
    useState(false);

  /*
   * Requirement 4: while a Work record is open, the workspace renders as a
   * fixed full-viewport overlay (.cx-workspace-backdrop) with its own scroll.
   * Lock the underlying shell body scroll so the analyst sees exactly one
   * scrollbar (the overlay's) instead of the overlay plus the shell scrolling
   * behind it.  The class is removed on close/unmount.
   */
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.body;
    if (editing) {
      root.classList.add('cx-workspace-open');
    } else {
      root.classList.remove('cx-workspace-open');
    }
    return () => {
      root.classList.remove('cx-workspace-open');
    };
  }, [editing]);

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

  const [
    workProcessState,
    setWorkProcessState,
  ] = useState<WorkProcessStateSnapshot | null>(
    null,
  );

  const [
    workProcessStateLoading,
    setWorkProcessStateLoading,
  ] = useState(false);

  const [selectedVerticalId, setSelectedVerticalId] =
    useState('');
  const [selectedDomainId, setSelectedDomainId] =
    useState('');

  const selectedServiceId = String(
    editing?.service_id ?? '',
  );

  const selectedServiceCode = String(
    services.rows.find(
      (service) =>
        String(service.id ?? '') === selectedServiceId,
    )?.code ?? '',
  );

  const workDisplayStatus = (() => {
    const rawStatus = String(
      editing?.status ?? '',
    );

    const effectiveStatus = String(
      editing?.effective_status ?? '',
    ).trim();

    if (effectiveStatus) {
      return effectiveStatus;
    }

    if (
      selectedServiceCode !==
      'UDYAM_REGISTRATION'
    ) {
      return rawStatus;
    }

    if (rawStatus === 'COMPLETED') {
      return 'Completed';
    }

    if (rawStatus === 'REWORK_REQUIRED') {
      return 'Returned';
    }

    const processCode = String(
      workProcessState?.current_step?.code ?? '',
    );

    const nextActionCode = String(
      workHealth?.next_action?.code ?? '',
    );

    if (
      processCode === 'SUBMIT_APPLICATION' ||
      nextActionCode === 'SUBMIT_UDYAM_APPLICATION'
    ) {
      return 'Application reviewed';
    }

    if (
      processCode === 'APPLICATION_SUBMISSION' ||
      nextActionCode === 'AWAIT_UDYAM_OUTCOME'
    ) {
      return 'Application submitted';
    }

    if (
      processCode === 'QUERY_RESOLUTION' ||
      nextActionCode === 'RESOLVE_UDYAM_QUERY'
    ) {
      return 'Query / OTP / Technical Issue';
    }

    return rawStatus;
  })();

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
        const selectedClient = clients.rows.find(
          (row) =>
            String(row.id ?? '') ===
            String(current.client_id ?? ''),
        );

        const clientName = String(
          selectedClient?.trade_name ??
          selectedClient?.display_name ??
          selectedClient?.legal_name ??
          selectedClient?.business_name ??
          selectedClient?.client_name ??
          selectedClient?.name ??
          '',
        ).trim();

        return {
          ...current,
          service_id: value,
          operational_data: clientName
            ? {
                enterprise_name: clientName,
              }
            : {},
        };
      }

      if (name === 'client_id') {
        const selectedClient = clients.rows.find(
          (row) =>
            String(row.id ?? '') ===
            String(value ?? ''),
        );

        const operationalData =
          current.operational_data &&
          typeof current.operational_data === 'object' &&
          !Array.isArray(current.operational_data)
            ? current.operational_data as Row
            : {};

        const existingEnterpriseName = String(
          operationalData.enterprise_name ?? '',
        ).trim();

        const clientName = String(
          selectedClient?.trade_name ??
          selectedClient?.display_name ??
          selectedClient?.legal_name ??
          selectedClient?.business_name ??
          selectedClient?.client_name ??
          selectedClient?.name ??
          '',
        ).trim();

        return {
          ...current,
          client_id: value,
          operational_data: {
            ...operationalData,
            ...(
              !existingEnterpriseName && clientName
                ? {
                    enterprise_name: clientName,
                  }
                : {}
            ),
          },
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
  const [tab, setTab] = useState<'details' | 'documents' | 'qa' | 'history'>('details');
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

  const loadWorkProcessState = (): void => {
    const workItemId = String(
      editing?.id ?? '',
    );

    if (!workItemId) {
      setWorkProcessState(null);
      setWorkProcessStateLoading(false);
      return;
    }

    setWorkProcessStateLoading(true);

    void getObject(
      `work-items/${workItemId}/process-step`,
    )
      .then((snapshot) => {
        setWorkProcessState(
          isWorkProcessStateSnapshot(snapshot)
            ? snapshot
            : null,
        );
      })
      .catch(() => {
        setWorkProcessState(null);
      })
      .finally(() => {
        setWorkProcessStateLoading(false);
      });
  };

  useEffect(() => {
    loadWorkHealth();
    loadWorkProcessState();
  }, [
    editing?.id,
    tab,
  ]);

  const refreshOpenWorkWorkspace =
    async (): Promise<void> => {
      const workItemId = String(
        editing?.id ?? '',
      );

      if (!workItemId) {
        work.reload();
        return;
      }

      /*
       * Reconcile the open workspace from authoritative server state.
       *
       * The authoritative WorkItem is refreshed FIRST and independently so a
       * completed record replaces the stale open `editing` snapshot even if a
       * dependent projection (Health/Process) is slow or fails.  See
       * reconcileOpenWorkspace for the full rationale (Requirement 1 / P0).
       */
      setWorkHealthLoading(true);
      setWorkProcessStateLoading(true);

      /*
       * Fresh authoritative values captured from reconcileOpenWorkspace's
       * callbacks, read after the call resolves (see the stale-pendingAction
       * reconciliation below). Captured as properties of one object rather
       * than separate `let` variables: TypeScript's control-flow narrowing
       * does not treat an assignment made inside a callback (passed as an
       * argument to an awaited function) as reaching a later point in this
       * function's own synchronous flow, so a bare `let x: Row | null = null`
       * narrows to exactly `null` (and then to `never` under `&& x`) at the
       * read site below, even though the callback did run. Reading through
       * an object property does not hit that limitation - verified with a
       * full program-level TypeScript check (0 diagnostics) before applying
       * this, so no cast, non-null assertion, or compiler-suppression
       * directive is used or needed.
       */
      const captured: {
        row: Row | null;
        processState: WorkProcessStateSnapshot | null;
        health: WorkHealthSnapshot | null;
      } = { row: null, processState: null, health: null };

      try {
        await reconcileOpenWorkspace({
          workItemId,
          fetchObject: (path) => getObject(path),
          setEditing: (row) => {
            captured.row = row;
            setEditing({ ...row });
          },
          setWorkHealth: (snapshot) => {
            captured.health = snapshot;
            setWorkHealth(snapshot);
          },
          setWorkProcessState: (snapshot) => {
            captured.processState = snapshot;
            setWorkProcessState(snapshot);
          },
          onWorkItemError: (message) => {
            // Surface a failed authoritative refresh and activate the
            // refresh-required safety state.  While that flag is set the
            // workspace suppresses all lifecycle controls and Save/Save&Close.
            setErr(message);
            setWorkHealthError(message);
            setWorkspaceNeedsRefresh(true);
          },
          onProjectionError: (message) => {
            // Non-fatal: the authoritative WorkItem already reconciled.
            setWorkHealthError(message);
          },
          clearError: () => {
            // Clear only the refresh/reconciliation presentation state after
            // the authoritative WorkItem has been fetched successfully.
            setErr('');
            setWorkHealthError('');
            setWorkspaceNeedsRefresh(false);
          },
        });
      } finally {
        setWorkHealthLoading(false);
        setWorkProcessStateLoading(false);

        /*
         * Stale pendingAction reconciliation (defense in depth): a selected-
         * but-unconfirmed SUBMIT_FOR_REVIEW must not survive an authoritative
         * refresh once the service's own business process has moved past its
         * pre-review position. UdyamWorkflowConfirm renders purely from
         * pendingAction with no awareness of process state, so this is the
         * one place a stale selection is safely cleared. The decision itself
         * lives in reconcileStalePendingAction (exported, directly testable);
         * this call site only supplies the fresh data and applies whatever
         * that function decides.
         */
        const freshServiceCode = String(
          services.rows.find(
            (service) =>
              String(service.id ?? '') ===
              String(captured.row?.service_id ?? ''),
          )?.code ?? '',
        );
        setPendingAction(
          reconcileStalePendingAction({
            pendingAction,
            freshRow: captured.row,
            freshProcessState: captured.processState,
            freshHealthSnapshot: captured.health,
            freshServiceCode,
          }),
        );

        // Preserve the existing Work grid refresh.
        work.reload();
      }
    };


  const udyamProcessStepCode = String(
    workProcessState?.current_step?.code ?? '',
  );

  /*
   * Requirement 1: anchor terminal signal to the authoritative Work Item status
   * rather than the separately-loaded process snapshot.  editing.status is
   * always present on the fetched record; the process snapshot can be
   * null/slow during loading and must never cause a completed record to appear
   * editable or to regress the tracker to Stage 2.
   */
  const udyamCompletedTerminal =
    Boolean(editing?.id) &&
    selectedServiceCode === 'UDYAM_REGISTRATION' &&
    String(editing?.status ?? '') === 'COMPLETED';

  /*
   * Udyam post-review stages use dedicated event actions.
   * Generic Work Save must not compete with them.  A completed Udyam record
   * is terminal and must likewise not present generic Save or Save & Close.
   */
  const udyamOwnsPrimaryAction =
    Boolean(editing?.id) &&
    (
      udyamCompletedTerminal ||
      udyamProcessStepCode === 'SUBMIT_APPLICATION' ||
      udyamProcessStepCode === 'APPLICATION_SUBMISSION' ||
      udyamProcessStepCode === 'QUERY_RESOLUTION' ||
      udyamProcessStepCode === 'COMPLETION'
    );

  /*
   * Requirement 8: when generic Work fields are locked but a stage-owned Udyam
   * workflow action is still available (an active, non-completed external
   * stage), the read-only banner must not imply that nothing can be done.
   * Permissions are unchanged; only the lock-banner wording is clarified.
   */
  const udyamHasProcessOwnedAction =
    selectedServiceCode === 'UDYAM_REGISTRATION' &&
    !udyamCompletedTerminal &&
    (
      udyamProcessStepCode === 'SUBMIT_APPLICATION' ||
      udyamProcessStepCode === 'APPLICATION_SUBMISSION' ||
      udyamProcessStepCode === 'QUERY_RESOLUTION'
    );

  const mudraProcessStepCode = String(
    workProcessState?.current_step?.code ?? '',
  );

  const mudraOutcome = String(
    (
      (editing?.operational_data as Record<string, unknown> | undefined) ?? {}
    ).mudra_outcome ?? '',
  ).toUpperCase();

  const mudraCompletedTerminal =
    Boolean(editing?.id) &&
    selectedServiceCode === 'MUDRA_LOAN' &&
    String(editing?.status ?? '') === 'COMPLETED';

  /*
   * UX-parity correction: MudraExternalActions owns Application & KYC
   * persistence (mudra-complete-application) from the moment a Mudra case
   * exists - APPLICATION is not different from any later Mudra stage in
   * this respect. The generic footer Save / Save & Close must not compete
   * with it there either, matching Udyam's exact same rule and every other
   * Mudra stage (CREDIT_ELIGIBILITY onward) already correctly suppresses
   * the footer once its own stage action owns the data.
   */
  const mudraOwnsPrimaryAction =
    Boolean(editing?.id) &&
    selectedServiceCode === 'MUDRA_LOAN' &&
    (
      mudraCompletedTerminal ||
      mudraOutcome === 'REJECTED' ||
      mudraOutcome === 'CLOSED' ||
      Boolean(mudraProcessStepCode)
    );

  const mudraHasProcessOwnedAction =
    selectedServiceCode === 'MUDRA_LOAN' &&
    !mudraCompletedTerminal &&
    mudraOutcome !== 'REJECTED' &&
    mudraOutcome !== 'CLOSED' &&
    Boolean(mudraProcessStepCode) &&
    mudraProcessStepCode !== 'APPLICATION';

  const closeWorkDrawer = (): void => {
    setWorkHealth(null);
    setWorkHealthError('');
    setWorkProcessState(null);
    setWorkspaceNeedsRefresh(false);
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
    // Save & Close (or workflow action): persist then close on success.
    void persistWorkItem(editing, closeWorkDrawer, setErr, work.reload, pendingAction, true);
  };

  const submitStayOpen = (): void => {
    if (!editing) return;
    // Save: persist and KEEP the drawer open so the analyst can continue editing.
    void persistWorkItem(
      editing,
      closeWorkDrawer,
      setErr,
      work.reload,
      pendingAction,
      false,
      () => { void refreshOpenWorkWorkspace(); },
    );
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
    const action = deriveWorkspacePrimaryAction({
      serviceCode: selectedServiceCode,
      status: row.status,
      processStepCode: String(
        workProcessState?.current_step?.code ?? '',
      ),
      nextActionCode: String(workHealth?.next_action?.code ?? ''),
    });
    // C4: reflect backend permission flags, never status alone.
    const canSubmit = row.can_submit_for_review === true;
    const canReview = row.can_review === true;
    if (action === 'SUBMIT_FOR_REVIEW' && canSubmit) {
      return actionButton({
        kind: 'SUBMIT_FOR_REVIEW',
        label: 'Submit for review',
      });
    }
    if (action === 'RESUME_WORK' && row.can_edit === true) {
      return actionButton({ kind: 'RESUME_WORK', label: 'Resume Work' });
    }
    const s = String(row.status);
    if (s === 'READY_FOR_REVIEW' && canReview) {
      return (
        <div style={{ display: 'flex', gap: 6 }}>
          {actionButton({
            kind: 'APPROVE',
            label:
              (selectedServiceCode === 'UDYAM_REGISTRATION' &&
                workProcessState?.current_step?.code ===
                  'INTERNAL_REVIEW') ||
              (selectedServiceCode === 'MUDRA_LOAN' &&
                workProcessState?.current_step?.code ===
                  'APPLICATION')
                ? 'Approve & continue'
                : 'Approve & complete',
          })}
          <button
            type="button"
            className={`cx-btn danger${pendingAction?.kind === 'RETURN_FOR_REWORK' ? ' pending' : ''}`}
            aria-pressed={pendingAction?.kind === 'RETURN_FOR_REWORK'}
            onClick={() => {
              if (pendingAction?.kind === 'RETURN_FOR_REWORK') {
                setPendingAction(null);
                return;
              }
              selectPendingAction({
                kind: 'RETURN_FOR_REWORK',
                label: 'Return for rework',
                comment: '',
              });
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
    { name: 'reference_by' },
    { name: 'due_date', kind: 'date' },
    { name: 'priority', kind: 'select', options: WORK_PRIORITY },
    { name: 'description', kind: 'textarea' },
  ];

  return (
    <>
      <div className="cx-toolbar">
        <select
          value={listVerticalId}
          onChange={(e) =>
            setListVerticalId(e.target.value)
          }
          aria-label="Filter Work by vertical"
        >
          <option value="">All verticals</option>
          {verticals.rows
            .filter(
              (vertical) =>
                String(vertical.status ?? 'ACTIVE')
                === 'ACTIVE',
            )
            .map((vertical) => (
              <option
                key={String(vertical.id)}
                value={String(vertical.id)}
              >
                {String(vertical.name)}
              </option>
            ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value)
          }
          aria-label="Filter Work by status"
        >
          <option value="">All statuses</option>
          {WORK_STATUS.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
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
            setPendingAction(null);
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
            { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.effective_status || r.status)} tone={statusTone(String(r.status))} /> },
          ]}
          rows={work.rows}
        />
      )}
      {editing && (
        <div className="cx-workspace-backdrop" onClick={closeWorkDrawer}>
          <div className="cx-workspace-page" onClick={(e) => e.stopPropagation()}>
            <div className="cx-workspace-commandbar" data-testid="work-commandbar">
              <div className="cx-workspace-commandbar-title">
                {editing.id ? (
                  /*
                    Phase 1 GREEN (Change A + B): identity and current
                    responsibility are rendered read-only from values already
                    present on the serialized WorkItem (client_name,
                    service_name, status/effective_status, current_controller,
                    current_controller_name).  No state is written, no handler,
                    callback, API, or workflow derivation is touched, and no
                    component is mounted/unmounted.  workDisplayStatus and
                    statusTone are existing read-only helpers.
                  */
                  <div className="cx-work-identity" data-testid="work-identity">
                    <div className="cx-work-identity-line">
                      <Chip
                        value={workDisplayStatus}
                        tone={statusTone(String(editing.status))}
                      />
                      <h3 className="cx-work-identity-title">
                        {String(editing.title)}
                      </h3>
                    </div>
                    {(editing.client_name || editing.service_name) ? (
                      <div className="cx-work-identity-meta">
                        {editing.client_name ? (
                          <span className="cx-work-identity-client">
                            {String(editing.client_name)}
                          </span>
                        ) : null}
                        {editing.client_name && editing.service_name ? (
                          <span className="cx-work-identity-sep"> · </span>
                        ) : null}
                        {editing.service_name ? (
                          <span className="cx-work-identity-service">
                            {String(editing.service_name)}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="cx-work-identity-responsibility">
                      <span className="cx-work-identity-kicker">
                        Current responsibility:
                      </span>{' '}
                      <span className="cx-work-identity-owner">
                        {
                          /*
                            Read-only projection of the EXISTING controller
                            fields.  Current responsibility is deliberately
                            derived from current_controller (not owner_name):
                            the durable Owner and the Current Responsibility are
                            not necessarily the same principal.
                          */
                          String(editing.status) === 'COMPLETED'
                            ? 'Completed - no active controller'
                            : String(editing.status) === 'CANCELLED'
                              ? 'Cancelled - no active controller'
                              : String(editing.current_controller) === 'REVIEWER'
                                ? (editing.current_controller_name
                                    ? `Reviewer - ${String(editing.current_controller_name)}`
                                    : 'Reviewer')
                                : String(editing.current_controller) === 'OWNER'
                                  ? (editing.current_controller_name
                                      ? `Owner - ${String(editing.current_controller_name)}`
                                      : 'Owner')
                                  : String(editing.current_controller) === 'CLIENT'
                                    ? 'Waiting on client'
                                    : (editing.current_controller_name
                                        ? String(editing.current_controller_name)
                                        : 'Unassigned')
                        }
                      </span>
                    </div>
                  </div>
                ) : (
                  <h3>New Work Item</h3>
                )}
              </div>

              <div
                className="cx-workspace-commandbar-action"
                aria-label="Current workflow action"
              >
                {/* TOP WORKFLOW ACTION ZONE - complete workflow interaction in one place */}
            {editing.id && !workspaceNeedsRefresh ? (
              <div className="cx-workflow-zone" data-testid="udyam-workflow-zone">
                {selectedServiceCode === 'UDYAM_REGISTRATION'
                  ? (
                    udyamCompletedTerminal
                      ? (
                        // Terminal completed: show only a close action
                        <div className="cx-workflow-zone-inner">
                          <span className="cx-workflow-zone-label">Work completed</span>
                          <button type="button" className="cx-btn subtle" onClick={closeWorkDrawer}>
                            Close
                          </button>
                        </div>
                      )
                      : (
                        <div className="cx-workflow-zone-inner">
                          {/* Udyam generic-review actions (Submit for Review / Approve / Return / Start / Resume) */}
                          {reviewButtons(editing)}
                          {/* Udyam external business actions (Submit Application / Report Query / Resolve / Complete) */}
                          <UdyamExternalActions
                            workItem={editing}
                            processState={workProcessState}
                            health={workHealth}
                            onError={setErr}
                            onChanged={refreshOpenWorkWorkspace}
                          />

                          {/*
                            V1.3: a selected generic lifecycle action is COMPLETED
                            here in the top zone - not at the footer.  The reviewer
                            justification (Return for Rework) and the confirm control
                            render together in this same zone.  Execution reuses the
                            canonical submit() -> persistWorkItem(pendingAction) path.
                          */}
                          <UdyamWorkflowConfirm
                            pendingAction={pendingAction}
                            canEdit={editing.can_edit === true}
                            onCommentChange={(comment) =>
                              setPendingAction(
                                pendingAction &&
                                  pendingAction.kind === 'RETURN_FOR_REWORK'
                                  ? { ...pendingAction, comment }
                                  : pendingAction,
                              )
                            }
                            onConfirm={submit}
                            onCancel={() => setPendingAction(null)}
                          />
                        </div>
                      )
                  )
                  : selectedServiceCode === 'MUDRA_LOAN'
                  ? (
                    <div className="cx-workflow-zone-inner">
                      {reviewButtons(editing)}
                      <MudraExternalActions
                        workItem={editing}
                        processState={workProcessState}
                        onError={setErr}
                        onChanged={refreshOpenWorkWorkspace}
                        onCloseWorkspace={closeWorkDrawer}
                      />

                      {/*
                        UX-parity correction: complete a selected Mudra
                        reviewer action (Approve & Continue / Return for
                        Rework) in this same top zone, exactly like Udyam -
                        not in the generic footer. Reuses UdyamWorkflowConfirm
                        unmodified: the same component, the same canonical
                        submit() -> persistWorkItem(pendingAction) path, no
                        new persistence and no second pending-action state.
                      */}
                      <UdyamWorkflowConfirm
                        pendingAction={pendingAction}
                        canEdit={editing.can_edit === true}
                        onCommentChange={(comment) =>
                          setPendingAction(
                            pendingAction &&
                              pendingAction.kind === 'RETURN_FOR_REWORK'
                              ? { ...pendingAction, comment }
                              : pendingAction,
                          )
                        }
                        onConfirm={submit}
                        onCancel={() => setPendingAction(null)}
                      />
                    </div>
                  )
                  : (
                    /* Non-Udyam: primary generic workflow actions (footer confirm preserved) */
                    <div className="cx-workflow-zone-inner">
                      {reviewButtons(editing)}
                    </div>
                  )
                }
              </div>
            ) : null}
              </div>
            </div>

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

            {/* 8-STAGE PROCESS TRACKER — always visible above tabs */}
            {editing.id && selectedServiceCode === 'UDYAM_REGISTRATION' ? (
              <ProcessTracker
                health={workHealth}
                processState={workProcessState}
                forceTerminalComplete={udyamCompletedTerminal}
                loading={
                  workHealthLoading ||
                  workProcessStateLoading
                }
                onOpenDocuments={() => setTab('documents')}
              />
            ) : null}

            {editing.id && selectedServiceCode === 'MUDRA_LOAN' ? (
              <MudraProcessTracker
                currentCode={String(
                  workProcessState?.current_step?.code ?? '',
                )}
                rejected={
                  String(
                    (
                      (editing.operational_data as
                        | Record<string, unknown>
                        | undefined) ?? {}
                    ).mudra_outcome ?? '',
                  ).toUpperCase() === 'REJECTED'
                }
              />
            ) : null}

            {editing.id ? (
              <div className="cx-toolbar" style={{ marginBottom: 12 }}>
                {(['details', 'documents', 'history'] as const).map((t) => (
                  <button
                    key={t}
                    className={`cx-btn ${t === tab ? '' : 'subtle'}`}
                    onClick={() => setTab(t)}
                  >
                    {t === 'history' ? 'History' : label(t)}
                  </button>
                ))}
              </div>
            ) : null}
            <ErrorBar error={err} />
            {/*
              Correction 2 (V1.4.1): refresh-required safety banner.
              While workspaceNeedsRefresh is true the workspace has just
              performed a workflow mutation whose authoritative result could
              not be confirmed.  The analyst must refresh before acting again.
              This is frontend-only reconciliation safety - not a business
              workflow state.
            */}
            {workspaceNeedsRefresh ? (
              <div
                className="cx-warning"
                role="alert"
                data-testid="workspace-refresh-required"
                style={{ marginBottom: 12 }}
              >
                <strong>Refresh required.</strong>{' '}
                The workflow action completed, but the latest Work state could
                not be confirmed. Refresh before performing another action.
                <div style={{ marginTop: 8 }}>
                  <button
                    type="button"
                    className="cx-btn"
                    onClick={() => { void refreshOpenWorkWorkspace(); }}
                  >
                    Refresh Work
                  </button>
                </div>
              </div>
            ) : null}
            {tab === 'details' && (
              <>
                {editing.id ? (
                  <div style={{ marginBottom: 12 }}>
                    <Chip
                      value={workDisplayStatus}
                      tone={statusTone(String(editing.status))}
                    />
                    {editing.current_controller_name ? (
                      <span className="cx-controller"> Controller: {String(editing.current_controller_name)}</span>
                    ) : null}
                  </div>
                ) : null}
                {editing.id && editing.is_locked === true ? (
                  <div className="cx-lock-banner" role="status">
                    {lockMessage(editing.status, editing.current_controller_name, udyamHasProcessOwnedAction || mudraHasProcessOwnedAction)}
                  </div>
                ) : null}
                {pendingAction &&
                  selectedServiceCode !== 'UDYAM_REGISTRATION' &&
                  selectedServiceCode !== 'MUDRA_LOAN' ? (
                  <div className="cx-warning" role="status" style={{ marginBottom: 12 }}>
                    Pending workflow action: <strong>{pendingAction.label}</strong>. {
                      editing.can_review === true &&
                      editing.can_edit !== true
                        ? 'Confirm the reviewer action below.'
                        : 'This will run only when you save.'
                    }
                  </div>
                ) : null}

                {pendingAction?.kind === 'RETURN_FOR_REWORK' &&
                  selectedServiceCode !== 'UDYAM_REGISTRATION' &&
                  selectedServiceCode !== 'MUDRA_LOAN' ? (
                  <div className="cx-field" style={{ marginBottom: 12 }}>
                    <label htmlFor="reviewer-return-justification">
                      Reviewer return justification *
                    </label>
                    <textarea
                      id="reviewer-return-justification"
                      value={pendingAction.comment}
                      onChange={(event) =>
                        setPendingAction({
                          ...pendingAction,
                          comment: event.target.value,
                        })
                      }
                    />
                  </div>
                ) : null}

                {
                  String(editing.review_comment ?? '').trim()
                    ? (
                      <div className="cx-field" style={{ marginBottom: 12 }}>
                        <label htmlFor="reviewer-return-justification-readonly">
                          Reviewer return justification
                        </label>
                        <textarea
                          id="reviewer-return-justification-readonly"
                          readOnly
                          value={String(editing.review_comment)}
                        />
                      </div>
                    )
                    : null
                }
                {fields.map((f) => (
                  <div key={f.name}>
                    <div className="cx-field">
                      <label>{label(f.name.replace(/_id$/, '').replace(/_user$/, ''))}</label>
                      {f.name === 'client_id' ? (
                        <SearchableClientSelect
                          clients={clients.rows}
                          value={String(editing[f.name] ?? '')}
                          disabled={Boolean(editing.id)}
                          onChange={(clientId) =>
                            updateWorkField('client_id', clientId)
                          }
                          onClientCreated={(client) => {
                            // Reload the shared client list so the new client is
                            // available everywhere, and select it immediately by
                            // id. The Work draft in `editing` is preserved (only
                            // client_id changes). The selector also keeps the new
                            // client locally so it shows before reload resolves.
                            clients.reload();
                            updateWorkField('client_id', String(client.id ?? ''));
                          }}
                        />
                      ) : f.kind === 'textarea' ? (
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

                    {f.name === 'owner_user_id' ? (
                      <div className="cx-owner-recommendation">
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
                      </div>
                    ) : null}
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
                  disabled={Boolean(editing.id)}
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
                    disabled={Boolean(editing.id)}
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
                  {/*
                    Correction 2: while workspaceNeedsRefresh is active, all
                    lifecycle controls and Save/Save&Close are suppressed - the
                    server state is unknown after the failed authoritative refresh.
                    The analyst must use the "Refresh Work" recovery action above.
                  */}
                  {!workspaceNeedsRefresh && !udyamOwnsPrimaryAction && !mudraOwnsPrimaryAction && (
                    (
                      !editing.id ||
                    editing.can_edit === true ||
                    (
                      editing.can_review === true &&
                      (
                        pendingAction?.kind === 'APPROVE' ||
                        pendingAction?.kind === 'RETURN_FOR_REWORK'
                      )
                    )
                  ) ? (
                    /*
                      V1.3: For Udyam, a selected lifecycle action is confirmed in
                      the TOP workflow zone, so the footer never renders the
                      lifecycle confirm button.  Non-Udyam keeps the existing
                      footer save-gated confirm behaviour unchanged.
                      UX-parity correction: Mudra now completes its own
                      selected reviewer action in the same top zone (via
                      UdyamWorkflowConfirm), so it is exempted here too.
                    */
                    (
                      pendingAction &&
                      selectedServiceCode !== 'UDYAM_REGISTRATION' &&
                      selectedServiceCode !== 'MUDRA_LOAN'
                    ) ? (
                      <button
                        type="button"
                        className="cx-btn"
                        disabled={
                          pendingAction?.kind === 'RETURN_FOR_REWORK' &&
                          !pendingAction.comment.trim()
                        }
                        onClick={submit}
                      >
                        {
                          editing.can_edit !== true
                            ? `Confirm ${pendingAction.label}`
                            : `Save & ${pendingAction.label}`
                        }
                      </button>
                    ) : !pendingAction ? (
                      <>
                        <button type="button" className="cx-btn subtle" onClick={submitStayOpen}>
                          Save
                        </button>
                        <button type="button" className="cx-btn" onClick={submit}>
                          Save &amp; Close
                        </button>
                      </>
                    ) : null
                  ) : null
                  )}
                </div>
              </>
            )}
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
