import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { act, list, save, uploadMany } from './api';
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

type AttachmentListProps = {
  rows: Row[];
  pendingDecision?: PendingDocumentDecision | null;
  onSelectReview?: (attachment: Row, status: 'ACCEPTED' | 'REJECTED') => void;
};

function AttachmentList({
  rows,
  pendingDecision = null,
  onSelectReview,
}: AttachmentListProps): React.JSX.Element {
  if (rows.length === 0) {
    return <p style={{ color: '#64748b', fontSize: 13 }}>No files uploaded.</p>;
  }
  return (
    <ul className="cx-file-list">
      {rows.map((attachment) => {
        const attachmentId = String(attachment.id);
        const reviewStatus = String(attachment.review_status || 'PENDING_REVIEW');
        const isPending = reviewStatus === 'PENDING_REVIEW';
        const selected =
          pendingDecision?.kind === 'ATTACHMENT_REVIEW' &&
          pendingDecision.attachmentId === attachmentId;
        return (
          <li className="cx-file-row" key={attachmentId}>
            <div className="cx-file-main">
              <div className="cx-document-file-title">
                <a href={String(attachment.download_url)}>
                  {String(attachment.original_name)}
                </a>
                <span className="cx-version-badge">
                  {String(attachment.version_label || `V${attachment.version_number || 1}`)}
                </span>
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
              <Chip value={reviewStatus} tone={statusTone(reviewStatus)} />
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
      return 'Rejected — upload a corrected document';
    case 'RECEIVED':
      return 'Received — waiting for acceptance';
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
        message: 'Expired — obtain a valid replacement',
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
        message: 'Rejected — corrected document required',
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
        message: 'Uploaded — review and accept or reject',
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
  const [pendingDecision, setPendingDecision] = useState<PendingDocumentDecision | null>(null);

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

  const uploadRequestFiles = (row: Row, files: FileList | null): void => {
    if (!files?.length) return;
    uploadMany('document-requests', String(row.id), 'upload', Array.from(files), { source: 'CLIENT' })
      .then(() => { docs.reload(); loadAttachments(String(row.id)); })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const uploadInternal = (files: FileList | null): void => {
    if (!files?.length) return;
    uploadMany('work-items', workItemId, 'upload_internal', Array.from(files))
      .then(() => internalFiles.reload())
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  return (
    <div>
      <ErrorBar error={docs.error || contacts.error || internalFiles.error || err} />
      <div className="cx-subhead"><h4>Internal work documents</h4>{canUploadInternal ? (<label className="cx-btn subtle" style={{ cursor: 'pointer' }}>Upload files<input type="file" multiple style={{ display: 'none' }} onChange={(e) => uploadInternal(e.target.files)} /></label>) : (<span className="cx-readonly-note">Upload locked at this stage</span>)}</div>
      <AttachmentList rows={internalFiles.rows.filter((a) => !a.document_request_id)} />
      <section
        className={`cx-readiness-card ${readinessTone}`}
        aria-label="Document readiness"
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
              Document readiness
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
            <span>Mandatory complete</span>
          </div>

          <div>
            <strong>
              {readiness.satisfiedDocuments}/
              {readiness.totalDocuments}
            </strong>
            <span>Overall complete</span>
          </div>

          <div>
            <strong>{readiness.mandatoryMissing}</strong>
            <span>Blocking review</span>
          </div>
        </div>

        {!readiness.ready && readiness.blockers.length > 0 ? (
          <div className="cx-readiness-blockers">
            <div className="cx-readiness-blockers-title">
              <strong>Required before review</strong>
              <span>
                Resolve these items to unlock submission.
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

      <section className="cx-document-action-queue">
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
          <h4>Client document requests</h4>
          <span className="cx-muted">
            Structured evidence required to complete this work
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
          No eligible document contact exists for this client. Add or enable one under Client → Contacts.
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
            <label className="cx-btn subtle" style={{ cursor: 'pointer' }}>Upload files<input type="file" multiple style={{ display: 'none' }} onChange={(e) => uploadRequestFiles(d, e.target.files)} /></label>
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

function HistoryPanel({ workItemId }: { workItemId: string }): React.JSX.Element {
  const notes = useList('work-notes', { work_item_id: workItemId });
  if (notes.loading) return <Loading />;
  if (notes.rows.length === 0) return <p style={{ color: '#64748b', fontSize: 13 }}>No history yet.</p>;
  return (
    <table className="cx-table">
      <thead><tr><th>When</th><th>Change</th><th>Note</th></tr></thead>
      <tbody>
        {notes.rows.map((n) => (
          <tr key={String(n.id)}>
            <td>{String(n.created_at ?? '').slice(0, 16).replace('T', ' ')}</td>
            <td>{n.from_status ? `${label(String(n.from_status))} -> ${label(String(n.to_status))}` : '-'}</td>
            <td>{String(n.entry)}</td>
          </tr>
        ))}
      </tbody>
    </table>
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

export function WorkArea(): React.JSX.Element {
  const clients = useList('clients');
  const services = useList('services');
  const employees = useList('employees');
  const [statusFilter, setStatusFilter] = useState('');
  const params = useMemo(() => (statusFilter ? { status: statusFilter } : {}), [statusFilter]);
  const work = useList('work-items', params);
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');
  const [tab, setTab] = useState<'details' | 'documents' | 'history'>('details');
  const [pendingAction, setPendingAction] = useState<PendingWorkAction | null>(null);

  const closeWorkDrawer = (): void => {
    setPendingAction(null);
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
    { name: 'service_id', kind: 'select', options: services.rows.filter((s) => s.status === 'ACTIVE').map((s) => String(s.id)), labels: (v) => String(services.rows.find((s) => s.id === v)?.name ?? v) },
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
        <button className="cx-btn" onClick={() => { setEditing({ title: '', priority: 'NORMAL', status: 'NOT_STARTED' }); setPendingAction(null); setTab('details'); setErr(''); }}>Add Work Item</button>
      </div>
      <ErrorBar error={work.error} />
      {work.loading ? (
        <Loading />
      ) : (
        <DataTable
          empty="No work items yet. Create one to start tracking client work."
          onRow={(r) => { setEditing({ ...r }); setPendingAction(null); setTab('details'); setErr(''); }}
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
        <div className="cx-drawer-backdrop" onClick={closeWorkDrawer}>
          <div className="cx-drawer" onClick={(e) => e.stopPropagation()}>
            <h3>{editing.id ? String(editing.title) : 'New Work Item'}</h3>
            {editing.id ? (
              <div className="cx-toolbar" style={{ marginBottom: 12 }}>
                {(['details', 'documents', 'history'] as const).map((t) => (
                  <button key={t} className={`cx-btn ${t === tab ? '' : 'subtle'}`} onClick={() => setTab(t)}>{label(t)}</button>
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
                      <textarea value={String(editing[f.name] ?? '')} onChange={(e) => setEditing({ ...editing, [f.name]: e.target.value })} />
                    ) : f.kind === 'select' ? (
                      <select value={String(editing[f.name] ?? '')} onChange={(e) => setEditing({ ...editing, [f.name]: e.target.value })}>
                        <option value="">""</option>
                        {(f.options ?? []).map((o) => <option key={o} value={o}>{f.labels ? f.labels(o) : label(o)}</option>)}
                      </select>
                    ) : (
                      <input type={f.kind === 'date' ? 'date' : 'text'} value={String(editing[f.name] ?? '')} onChange={(e) => setEditing({ ...editing, [f.name]: e.target.value })} />
                    )}
                  </div>
                ))}
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
            {tab === 'history' && editing.id ? <HistoryPanel workItemId={String(editing.id)} /> : null}
          </div>
        </div>
      )}
    </>
  );
}
