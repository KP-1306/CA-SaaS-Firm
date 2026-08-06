import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';

import { act, getObject, list, save } from './api';
import type { Row } from './types';
import { Chip, ErrorBar, Loading } from './ui';

export type QaValue = 'PENDING' | 'YES' | 'NO' | 'NOT_APPLICABLE';

export function qaTone(value: unknown): string {
  const text = String(value ?? '');
  if (text === 'YES' || text === 'APPROVED' || text === 'RESOLVED') return 'ok';
  if (text === 'NO' || text === 'CHANGES_REQUESTED' || text === 'OPEN') return 'danger';
  if (text === 'PENDING' || text === 'READY_FOR_REVIEW' || text === 'IN_REVIEW') return 'warn';
  return 'muted';
}

export function buildQaResponses(
  rows: Row[],
  role: 'preparer' | 'reviewer',
): Row[] {
  return rows.map((row) => ({
    id: row.id,
    value:
      role === 'preparer'
        ? row.preparer_response ?? 'PENDING'
        : row.reviewer_response ?? 'PENDING',
    comment:
      role === 'preparer'
        ? row.preparer_comment ?? ''
        : row.reviewer_comment ?? '',
    evidence_attachment_id:
      role === 'preparer'
        ? row.preparer_evidence_attachment_id ?? null
        : row.reviewer_evidence_attachment_id ?? null,
  }));
}

function useQa(workItemId: string): {
  readiness: Row | null;
  history: Row[];
  loading: boolean;
  error: string;
  reload: () => void;
} {
  const [readiness, setReadiness] = useState<Row | null>(null);
  const [history, setHistory] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = (): void => {
    setLoading(true);
    Promise.all([
      getObject(`work-items/${workItemId}/qa-readiness`),
      getObject(`work-items/${workItemId}/qa-review-history`),
    ])
      .then(([ready, reviewHistory]) => {
        setReadiness(ready);
        setHistory(Array.isArray(reviewHistory) ? reviewHistory : []);
        setError('');
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      })
      .finally(() => setLoading(false));
  };

  useEffect(reload, [workItemId]);

  return { readiness, history, loading, error, reload };
}

function QaChecklist({
  workItemId,
  cycle,
  role,
  onSaved,
}: {
  workItemId: string;
  cycle: Row;
  role: 'preparer' | 'reviewer';
  onSaved: () => void;
}): React.JSX.Element {
  const initial = Array.isArray(cycle.responses) ? cycle.responses as Row[] : [];
  const [rows, setRows] = useState<Row[]>(initial.map((row) => ({ ...row })));
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setRows(initial.map((row) => ({ ...row })));
  }, [cycle.id, cycle.updated_at, JSON.stringify(initial)]);

  const responseField = role === 'preparer' ? 'preparer_response' : 'reviewer_response';
  const commentField = role === 'preparer' ? 'preparer_comment' : 'reviewer_comment';

  const update = (index: number, patch: Row): void => {
    setRows((current) =>
      current.map((row, rowIndex) =>
        rowIndex === index ? { ...row, ...patch } : row,
      ),
    );
  };

  const submit = (): void => {
    setSaving(true);
    setError('');
    act(
      'work-items',
      workItemId,
      role === 'preparer'
        ? 'save-preparer-checklist'
        : 'save-reviewer-checklist',
      { responses: buildQaResponses(rows, role) },
    )
      .then(() => onSaved())
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      )
      .finally(() => setSaving(false));
  };

  return (
    <section className="cx-qa-panel">
      <div className="cx-qa-panel-head">
        <div>
          <span className="cx-panel-kicker">
            {role === 'preparer' ? 'Preparation control' : 'Independent review'}
          </span>
          <h4>{role === 'preparer' ? 'Preparer checklist' : 'Reviewer checklist'}</h4>
        </div>
        <Chip value={String(cycle.status ?? 'PREPARATION')} tone={qaTone(cycle.status)} />
      </div>

      <ErrorBar error={error} />

      <div className="cx-qa-checklist">
        {rows.map((row, index) => (
          <article className="cx-qa-check" key={String(row.id)}>
            <div className="cx-qa-check-title">
              <strong>{String(row.code || '')}</strong>
              <span>{String(row.title || 'Checklist item')}</span>
              {row.mandatory === true ? <Chip value="MANDATORY" tone="warn" /> : null}
            </div>

            <div className="cx-qa-check-controls">
              <select
                value={String(row[responseField] ?? 'PENDING')}
                onChange={(event) =>
                  update(index, { [responseField]: event.target.value })
                }
              >
                <option value="PENDING">Pending</option>
                <option value="YES">Pass / Yes</option>
                <option value="NO">Fail / No</option>
                <option value="NOT_APPLICABLE">Not applicable</option>
              </select>

              <input
                type="text"
                placeholder="Comment"
                value={String(row[commentField] ?? '')}
                onChange={(event) =>
                  update(index, { [commentField]: event.target.value })
                }
              />
            </div>
          </article>
        ))}
      </div>

      <div className="cx-qa-actions">
        <button className="cx-btn" type="button" disabled={saving} onClick={submit}>
          {saving ? 'Saving...' : 'Save checklist'}
        </button>
      </div>
    </section>
  );
}

function QaIssues({
  workItemId,
  cycle,
  canReview,
  canEdit,
  onChanged,
}: {
  workItemId: string;
  cycle: Row;
  canReview: boolean;
  canEdit: boolean;
  onChanged: () => void;
}): React.JSX.Element {
  const issues = Array.isArray(cycle.issues) ? cycle.issues as Row[] : [];
  const [form, setForm] = useState<Row>({
    title: '',
    description: '',
    severity: 'MEDIUM',
    category: 'QUALITY',
  });
  const [resolution, setResolution] = useState<Record<string, string>>({});
  const [error, setError] = useState('');

  const raise = (): void => {
    setError('');
    act('work-items', workItemId, 'raise-qa-issue', form)
      .then(() => {
        setForm({
          title: '',
          description: '',
          severity: 'MEDIUM',
          category: 'QUALITY',
        });
        onChanged();
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  const resolve = (issue: Row): void => {
    setError('');
    act('work-items', workItemId, 'resolve-qa-issue', {
      issue_id: issue.id,
      comment: resolution[String(issue.id)] ?? '',
    })
      .then(() => onChanged())
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  return (
    <section className="cx-qa-panel">
      <div className="cx-qa-panel-head">
        <div>
          <span className="cx-panel-kicker">Correction control</span>
          <h4>QA issues</h4>
        </div>
        <span className="cx-panel-count">{issues.length}</span>
      </div>

      <ErrorBar error={error} />

      {issues.length === 0 ? (
        <div className="cx-empty">No QA issues have been raised.</div>
      ) : (
        <div className="cx-qa-issues">
          {issues.map((issue) => (
            <article className="cx-qa-issue" key={String(issue.id)}>
              <div>
                <div className="cx-qa-check-title">
                  <strong>{String(issue.title)}</strong>
                  <Chip value={String(issue.severity)} tone={qaTone(issue.severity)} />
                  <Chip value={String(issue.status)} tone={qaTone(issue.status)} />
                </div>
                <p>{String(issue.description || '')}</p>
                {issue.resolution_comment ? (
                  <small>Resolution: {String(issue.resolution_comment)}</small>
                ) : null}
              </div>

              {canEdit && (issue.status === 'OPEN' || issue.status === 'REOPENED') ? (
                <div className="cx-qa-resolve">
                  <input
                    type="text"
                    placeholder="Resolution comment"
                    value={resolution[String(issue.id)] ?? ''}
                    onChange={(event) =>
                      setResolution({
                        ...resolution,
                        [String(issue.id)]: event.target.value,
                      })
                    }
                  />
                  <button
                    type="button"
                    className="cx-btn subtle"
                    onClick={() => resolve(issue)}
                  >
                    Resolve
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      )}

      {canReview ? (
        <div className="cx-qa-issue-form">
          <input
            placeholder="Issue title"
            value={String(form.title)}
            onChange={(event) => setForm({ ...form, title: event.target.value })}
          />
          <textarea
            placeholder="Describe the required correction"
            value={String(form.description)}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
          />
          <select
            value={String(form.severity)}
            onChange={(event) => setForm({ ...form, severity: event.target.value })}
          >
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
            <option value="CRITICAL">Critical</option>
          </select>
          <button className="cx-btn" type="button" onClick={raise}>
            Raise issue
          </button>
        </div>
      ) : null}
    </section>
  );
}

export function QAWorkspace({
  workItem,
  onWorkChanged,
}: {
  workItem: Row;
  onWorkChanged?: () => void;
}): React.JSX.Element {
  const workItemId = String(workItem.id);
  const qa = useQa(workItemId);
  const [actionError, setActionError] = useState('');

  const prepare = (): void => {
    setActionError('');
    act('work-items', workItemId, 'prepare-qa')
      .then(() => qa.reload())
      .catch((value: unknown) =>
        setActionError(String(value instanceof Error ? value.message : value)),
      );
  };

  if (qa.loading) return <Loading />;

  const readiness = qa.readiness ?? {};
  const cycle = readiness.cycle as Row | null | undefined;
  const enabled = readiness.enabled === true;
  const blockers = Array.isArray(readiness.blockers) ? readiness.blockers as Row[] : [];

  return (
    <div className="cx-qa-workspace">
      <ErrorBar error={qa.error || actionError} />

      <section className="cx-qa-summary">
        <div>
          <span>QA status</span>
          <strong>{enabled ? String(cycle?.status ?? 'NOT PREPARED') : 'NOT CONFIGURED'}</strong>
        </div>
        <div>
          <span>Submission</span>
          <strong>{readiness.ready_for_submission === true ? 'READY' : 'BLOCKED'}</strong>
        </div>
        <div>
          <span>Approval</span>
          <strong>{readiness.ready_for_approval === true ? 'READY' : 'BLOCKED'}</strong>
        </div>
        <div>
          <span>Review cycles</span>
          <strong>{qa.history.length}</strong>
        </div>
      </section>

      {!enabled ? (
        <div className="cx-warning">
          No active QA checklist is configured for this service. The existing
          review workflow remains available.
        </div>
      ) : null}

      {enabled && !cycle && workItem.can_edit === true ? (
        <button className="cx-btn" type="button" onClick={prepare}>
          Prepare QA checklist
        </button>
      ) : null}

      {blockers.length > 0 ? (
        <section className="cx-qa-blockers">
          <strong>Current blockers</strong>
          <ul>
            {blockers.map((blocker, index) => (
              <li key={`${String(blocker.code)}-${index}`}>
                {String(blocker.detail || blocker.code)}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {cycle && workItem.can_edit === true ? (
        <QaChecklist
          workItemId={workItemId}
          cycle={cycle}
          role="preparer"
          onSaved={() => {
            qa.reload();
            onWorkChanged?.();
          }}
        />
      ) : null}

      {cycle && workItem.can_review === true ? (
        <QaChecklist
          workItemId={workItemId}
          cycle={cycle}
          role="reviewer"
          onSaved={() => {
            qa.reload();
            onWorkChanged?.();
          }}
        />
      ) : null}

      {cycle ? (
        <QaIssues
          workItemId={workItemId}
          cycle={cycle}
          canReview={workItem.can_review === true}
          canEdit={workItem.can_edit === true}
          onChanged={() => {
            qa.reload();
            onWorkChanged?.();
          }}
        />
      ) : null}

      <section className="cx-qa-panel">
        <div className="cx-qa-panel-head">
          <div>
            <span className="cx-panel-kicker">Immutable evidence</span>
            <h4>Review history</h4>
          </div>
        </div>

        {qa.history.length === 0 ? (
          <div className="cx-empty">No QA review cycle has been created.</div>
        ) : (
          <div className="cx-qa-history">
            {qa.history.map((entry) => (
              <article key={String(entry.id)}>
                <strong>Cycle {String(entry.cycle_number)}</strong>
                <Chip value={String(entry.status)} tone={qaTone(entry.status)} />
                <span>Checklist V{String(entry.checklist_version ?? 1)}</span>
                <span>
                  Submitted: {String(entry.submitted_at ?? '-').slice(0, 16).replace('T', ' ')}
                </span>
                <span>
                  Approved: {String(entry.approved_at ?? '-').slice(0, 16).replace('T', ' ')}
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export function QAOperationalQueue({
  workRows,
  onOpen,
}: {
  workRows: Row[];
  onOpen: (row: Row) => void;
}): React.JSX.Element {
  const queue = useMemo(
    () =>
      workRows.filter((row) =>
        ['READY_FOR_REVIEW', 'REWORK_REQUIRED'].includes(String(row.status)),
      ),
    [workRows],
  );

  if (queue.length === 0) return <></>;

  return (
    <section className="cx-qa-queue">
      <div className="cx-qa-panel-head">
        <div>
          <span className="cx-panel-kicker">QA action queue</span>
          <h3>Review and rework</h3>
        </div>
        <span className="cx-panel-count">{queue.length}</span>
      </div>
      <div className="cx-qa-queue-grid">
        {queue.slice(0, 8).map((row) => (
          <button type="button" key={String(row.id)} onClick={() => onOpen(row)}>
            <strong>{String(row.title || 'Work item')}</strong>
            <span>{String(row.client_name || '')}</span>
            <Chip value={String(row.status)} tone={qaTone(row.status)} />
          </button>
        ))}
      </div>
    </section>
  );
}

export function QACataloguePanel({
  services,
}: {
  services: Row[];
}): React.JSX.Element {
  const [sets, setSets] = useState<Row[]>([]);
  const [items, setItems] = useState<Row[]>([]);
  const [editingSet, setEditingSet] = useState<Row>({
    service_id: '',
    name: '',
    version_number: 1,
    status: 'DRAFT',
    prevent_self_review: true,
    require_preparer_confirmation: true,
    require_reviewer_confirmation: true,
  });
  const [editingItem, setEditingItem] = useState<Row>({
    checklist_set_id: '',
    service_id: '',
    code: '',
    title: '',
    display_order: 10,
    mandatory: true,
    preparer_required: true,
    reviewer_required: true,
    evidence_required: false,
    allow_not_applicable: false,
    is_active: true,
  });
  const [error, setError] = useState('');

  const reload = (): void => {
    Promise.all([
      list('service-qa-checklist-sets'),
      list('service-qa-checklist-items'),
    ])
      .then(([setRows, itemRows]) => {
        setSets(setRows);
        setItems(itemRows);
        setError('');
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  useEffect(reload, []);

  const saveSet = (): void => {
    save('service-qa-checklist-sets', editingSet)
      .then(() => {
        setEditingSet({
          service_id: '',
          name: '',
          version_number: 1,
          status: 'DRAFT',
          prevent_self_review: true,
          require_preparer_confirmation: true,
          require_reviewer_confirmation: true,
        });
        reload();
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  const saveItem = (): void => {
    const selectedSet = sets.find(
      (row) => String(row.id) === String(editingItem.checklist_set_id),
    );
    save('service-qa-checklist-items', {
      ...editingItem,
      service_id: selectedSet?.service_id ?? editingItem.service_id,
    })
      .then(() => {
        setEditingItem({
          checklist_set_id: '',
          service_id: '',
          code: '',
          title: '',
          display_order: 10,
          mandatory: true,
          preparer_required: true,
          reviewer_required: true,
          evidence_required: false,
          allow_not_applicable: false,
          is_active: true,
        });
        reload();
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  return (
    <section className="cx-qa-catalogue">
      <div className="cx-qa-panel-head">
        <div>
          <span className="cx-panel-kicker">Quality configuration</span>
          <h3>Service QA checklists</h3>
        </div>
        <span className="cx-panel-count">{sets.length}</span>
      </div>

      <ErrorBar error={error} />

      <div className="cx-qa-config-grid">
        <div className="cx-qa-panel">
          <h4>Checklist version</h4>
          <select
            value={String(editingSet.service_id ?? '')}
            onChange={(event) =>
              setEditingSet({ ...editingSet, service_id: event.target.value })
            }
          >
            <option value="">Select service</option>
            {services.map((service) => (
              <option key={String(service.id)} value={String(service.id)}>
                {String(service.name)}
              </option>
            ))}
          </select>
          <input
            placeholder="Checklist name"
            value={String(editingSet.name ?? '')}
            onChange={(event) =>
              setEditingSet({ ...editingSet, name: event.target.value })
            }
          />
          <input
            type="number"
            min="1"
            value={Number(editingSet.version_number ?? 1)}
            onChange={(event) =>
              setEditingSet({
                ...editingSet,
                version_number: Number(event.target.value),
              })
            }
          />
          <select
            value={String(editingSet.status ?? 'DRAFT')}
            onChange={(event) =>
              setEditingSet({ ...editingSet, status: event.target.value })
            }
          >
            <option value="DRAFT">Draft</option>
            <option value="ACTIVE">Active</option>
            <option value="RETIRED">Retired</option>
          </select>
          <button className="cx-btn" type="button" onClick={saveSet}>
            Save checklist version
          </button>
        </div>

        <div className="cx-qa-panel">
          <h4>Checklist item</h4>
          <select
            value={String(editingItem.checklist_set_id ?? '')}
            onChange={(event) =>
              setEditingItem({
                ...editingItem,
                checklist_set_id: event.target.value,
              })
            }
          >
            <option value="">Select checklist</option>
            {sets.map((setRow) => (
              <option key={String(setRow.id)} value={String(setRow.id)}>
                {String(setRow.name)} · V{String(setRow.version_number)}
              </option>
            ))}
          </select>
          <input
            placeholder="Code"
            value={String(editingItem.code ?? '')}
            onChange={(event) =>
              setEditingItem({ ...editingItem, code: event.target.value })
            }
          />
          <input
            placeholder="Control / review step"
            value={String(editingItem.title ?? '')}
            onChange={(event) =>
              setEditingItem({ ...editingItem, title: event.target.value })
            }
          />
          <label>
            <input
              type="checkbox"
              checked={editingItem.mandatory === true}
              onChange={(event) =>
                setEditingItem({ ...editingItem, mandatory: event.target.checked })
              }
            />
            Mandatory
          </label>
          <label>
            <input
              type="checkbox"
              checked={editingItem.evidence_required === true}
              onChange={(event) =>
                setEditingItem({
                  ...editingItem,
                  evidence_required: event.target.checked,
                })
              }
            />
            Evidence required
          </label>
          <button className="cx-btn" type="button" onClick={saveItem}>
            Save checklist item
          </button>
        </div>
      </div>

      <div className="cx-qa-config-list">
        {sets.map((setRow) => (
          <article key={String(setRow.id)}>
            <strong>{String(setRow.name)}</strong>
            <span>Version {String(setRow.version_number)}</span>
            <Chip value={String(setRow.status)} tone={qaTone(setRow.status)} />
            <small>
              {items.filter(
                (item) =>
                  String(item.checklist_set_id) === String(setRow.id),
              ).length} controls
            </small>
          </article>
        ))}
      </div>
    </section>
  );
}
