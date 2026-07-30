import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { list, save } from './api';
import { label } from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';

type Level = 'verticals' | 'domains' | 'services';

function useList(resource: string): { rows: Row[]; error: string; loading: boolean; reload: () => void } {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const reload = (): void => {
    setLoading(true);
    list(resource)
      .then((r) => {
        setRows(r);
        setError('');
      })
      .catch((e: unknown) => setError(String(e instanceof Error ? e.message : e)))
      .finally(() => setLoading(false));
  };
  useEffect(reload, [resource]);
  return { rows, error, loading, reload };
}

export function CatalogueArea(): React.JSX.Element {
  const [level, setLevel] = useState<Level>('verticals');
  const verticals = useList('verticals');
  const domains = useList('domains');
  const services = useList('services');
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');

  const activeVerticals = useMemo(() => verticals.rows.filter((v) => v.status === 'ACTIVE'), [verticals.rows]);
  const activeDomains = useMemo(() => domains.rows.filter((d) => d.status === 'ACTIVE'), [domains.rows]);
  const vName = (id: unknown): string => String(verticals.rows.find((v) => v.id === id)?.name ?? '""');
  const dName = (id: unknown): string => String(domains.rows.find((d) => d.id === id)?.name ?? '""');

  const current = level === 'verticals' ? verticals : level === 'domains' ? domains : services;

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save(level, clean)
      .then(() => {
        setEditing(null);
        setSaveError('');
        current.reload();
      })
      .catch((e: unknown) => setSaveError(String(e instanceof Error ? e.message : e)));
  };

  const blank = (): Row => {
    if (level === 'verticals') return { name: '', code: '', status: 'ACTIVE' };
    if (level === 'domains') return { name: '', code: '', vertical_id: '', status: 'ACTIVE' };
    return { name: '', code: '', domain_id: '', status: 'ACTIVE' };
  };

  const columns =
    level === 'verticals'
      ? [
          { key: 'name', header: 'Vertical' },
          { key: 'code', header: 'Code' },
          { key: 'status', header: 'Status', render: (r: Row) => <Chip value={String(r.status)} tone={r.status === 'ACTIVE' ? 'ok' : 'danger'} /> },
        ]
      : level === 'domains'
        ? [
            { key: 'name', header: 'Domain' },
            { key: 'vertical_id', header: 'Vertical', render: (r: Row) => vName(r.vertical_id) },
            { key: 'status', header: 'Status', render: (r: Row) => <Chip value={String(r.status)} tone={r.status === 'ACTIVE' ? 'ok' : 'danger'} /> },
          ]
        : [
            { key: 'name', header: 'Service' },
            { key: 'domain_id', header: 'Domain', render: (r: Row) => dName(r.domain_id) },
            { key: 'status', header: 'Status', render: (r: Row) => <Chip value={String(r.status)} tone={r.status === 'ACTIVE' ? 'ok' : 'danger'} /> },
          ];

  return (
    <>
      <div className="cx-toolbar">
        {(['verticals', 'domains', 'services'] as Level[]).map((l) => (
          <button key={l} className={`cx-btn ${l === level ? '' : 'subtle'}`} onClick={() => { setLevel(l); setEditing(null); }}>
            {label(l)}
          </button>
        ))}
        <div className="cx-spacer" />
        <button className="cx-btn" onClick={() => { setEditing(blank()); setSaveError(''); }}>
          Add {label(level).replace(/s$/, '')}
        </button>
      </div>
      <ErrorBar error={current.error} />
      {current.loading ? (
        <Loading />
      ) : (
        <DataTable columns={columns} rows={current.rows} onRow={(r) => { setEditing({ ...r }); setSaveError(''); }} empty={`No ${level} yet.`} />
      )}
      {editing && (
        <Drawer
          title={`${editing.id ? 'Edit' : 'New'} ${label(level).replace(/s$/, '')}`}
          value={editing}
          onChange={setEditing}
          onClose={() => setEditing(null)}
          onSave={submit}
          extra={<ErrorBar error={saveError} />}
          fields={[
            { name: 'name' },
            { name: 'code' },
            ...(level === 'domains'
              ? [{ name: 'vertical_id', kind: 'select' as const, options: activeVerticals.map((v) => String(v.id)), labels: (id: string) => vName(id) }]
              : []),
            ...(level === 'services'
              ? [
                  { name: 'domain_id', kind: 'select' as const, options: activeDomains.map((d) => String(d.id)), labels: (id: string) => dName(id) },
                  { name: 'default_due_days' },
                ]
              : []),
            { name: 'description', kind: 'textarea' },
            { name: 'status', kind: 'select', options: ['ACTIVE', 'INACTIVE'] },
          ]}
        />
      )}
    </>
  );
}
