import type * as React from 'react';
import { useEffect, useState } from 'react';
import { list } from './api';
import type { Row } from './types';
import { DataTable, ErrorBar, Loading } from './ui';

const ACTIONS = [
  'CREATE', 'UPDATE', 'DELETE', 'OWNER_ASSIGNED', 'REVIEWER_ASSIGNED', 'STATUS_CHANGE',
  'COMMENT_CREATED', 'DOCUMENT_REQUEST_CREATED', 'DOCUMENT_UPLOAD',
  'ATTACHMENT_ACCEPTED', 'ATTACHMENT_REJECTED',
] as const;

export function AuditViewer(): React.JSX.Element {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = (): void => {
    setLoading(true);
    list('audit-events', {
      action: action || undefined,
      entity_type: entityType || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    })
      .then((r) => {
        setRows(r);
        setError('');
      })
      .catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  return (
    <>
      <div className="cx-toolbar">
        <select value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="">All actions</option>
          {ACTIONS.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
        </select>
        <input placeholder="Entity type" value={entityType} onChange={(e) => setEntityType(e.target.value)} />
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        <button className="cx-btn subtle" onClick={load}>Apply</button>
      </div>
      <ErrorBar error={error} />
      {loading ? (
        <Loading />
      ) : (
        <DataTable
          empty="No audit events."
          columns={[
            { key: 'created_at', header: 'When', render: (r) => String(r.created_at ?? '').slice(0, 19).replace('T', ' ') },
            { key: 'action_label', header: 'Action', render: (r) => String(r.action_label ?? r.action) },
            { key: 'entity_type', header: 'Entity' },
            { key: 'summary', header: 'Summary' },
          ]}
          rows={rows}
        />
      )}
    </>
  );
}
