import type * as React from 'react';
import { useEffect, useState } from 'react';
import { act, list, save } from './api';
import { label } from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';
import type { Column, Field } from './ui';

// Servicing area (V1): client service subscriptions, task templates and
// recurring work profiles. Mirrors the existing area components and reuses the
// shared UI kit exactly. UUID references are chosen via `kind: 'select'` whose
// options are existing row ids with a `labels` name lookup — never raw-UUID text
// inputs (matching the no-raw-uuid contract).

type Level = 'client-service-subscriptions' | 'task-templates' | 'recurring-work-profiles';

const FREQUENCY = ['NONE', 'MONTHLY', 'QUARTERLY', 'HALF_YEARLY', 'YEARLY'] as const;
const SUBSCRIPTION_STATUS = ['ACTIVE', 'PAUSED', 'ENDED'] as const;

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

export function ServicingArea(): React.JSX.Element {
  const [level, setLevel] = useState<Level>('client-service-subscriptions');
  const subscriptions = useList('client-service-subscriptions');
  const templates = useList('task-templates');
  const profiles = useList('recurring-work-profiles');
  const clients = useList('clients');
  const services = useList('services');
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');
  const [notice, setNotice] = useState('');

  const clientName = (id: unknown): string =>
    String(clients.rows.find((c) => c.id === id)?.trade_name || clients.rows.find((c) => c.id === id)?.legal_name || '-');
  const serviceName = (id: unknown): string => String(services.rows.find((s) => s.id === id)?.name ?? '-');

  const current = level === 'client-service-subscriptions' ? subscriptions : level === 'task-templates' ? templates : profiles;

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
    if (level === 'client-service-subscriptions') return { client_id: '', service_id: '', frequency: 'NONE', status: 'ACTIVE' };
    if (level === 'task-templates') return { service_id: '', name: '', default_priority: 'NORMAL' };
    return { subscription_id: '', client_id: '', service_id: '', frequency: 'MONTHLY' };
  };

  const generate = (profile: Row): void => {
    act('recurring-work-profiles', String(profile.id), 'generate', {})
      .then((r) => {
        const created = (r as Row).created === true;
        setNotice(
          created
            ? `Generated work for period ${String((r as Row).period_key)}.`
            : `Already generated for period ${String((r as Row).period_key)}.`,
        );
        profiles.reload();
      })
      .catch((e: unknown) => setSaveError(String(e instanceof Error ? e.message : e)));
  };

  const clientIds = (): string[] => clients.rows.map((c) => String(c.id));
  const serviceIds = (): string[] => services.rows.filter((s) => s.status === 'ACTIVE').map((s) => String(s.id));

  const fields = (): Field[] => {
    if (level === 'client-service-subscriptions') {
      return [
        { name: 'client_id', kind: 'select', options: clientIds(), labels: (v) => clientName(v) },
        { name: 'service_id', kind: 'select', options: serviceIds(), labels: (v) => serviceName(v) },
        { name: 'frequency', kind: 'select', options: [...FREQUENCY] },
        { name: 'status', kind: 'select', options: [...SUBSCRIPTION_STATUS] },
        { name: 'start_date', kind: 'date' },
        { name: 'end_date', kind: 'date' },
        { name: 'notes', kind: 'textarea' },
      ];
    }
    if (level === 'task-templates') {
      return [
        { name: 'service_id', kind: 'select', options: serviceIds(), labels: (v) => serviceName(v) },
        { name: 'name', kind: 'text' },
        { name: 'description', kind: 'textarea' },
        { name: 'default_title', kind: 'text' },
        { name: 'default_due_days', kind: 'text' },
      ];
    }
    return [
      {
        name: 'subscription_id',
        kind: 'select',
        options: subscriptions.rows.map((s) => String(s.id)),
        labels: (v) => {
          const s = subscriptions.rows.find((x) => x.id === v);
          return s ? `${clientName(s.client_id)} · ${serviceName(s.service_id)}` : String(v);
        },
      },
      { name: 'client_id', kind: 'select', options: clientIds(), labels: (v) => clientName(v) },
      { name: 'service_id', kind: 'select', options: serviceIds(), labels: (v) => serviceName(v) },
      { name: 'frequency', kind: 'select', options: [...FREQUENCY] },
      { name: 'anchor_date', kind: 'date' },
    ];
  };

  const columns = (): Column[] => {
    if (level === 'client-service-subscriptions') {
      return [
        { key: 'client_id', header: 'Client', render: (r) => clientName(r.client_id) },
        { key: 'service_id', header: 'Service', render: (r) => serviceName(r.service_id) },
        { key: 'frequency', header: 'Frequency', render: (r) => label(String(r.frequency)) },
        { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} /> },
      ];
    }
    if (level === 'task-templates') {
      return [
        { key: 'name', header: 'Name' },
        { key: 'service_id', header: 'Service', render: (r) => serviceName(r.service_id) },
        { key: 'default_due_days', header: 'Due days' },
      ];
    }
    return [
      { key: 'client_id', header: 'Client', render: (r) => clientName(r.client_id) },
      { key: 'service_id', header: 'Service', render: (r) => serviceName(r.service_id) },
      { key: 'frequency', header: 'Frequency', render: (r) => label(String(r.frequency)) },
      {
        key: 'actions',
        header: '',
        render: (r) => (
          <button type="button" className="cx-btn" onClick={() => generate(r)}>
            Generate now
          </button>
        ),
      },
    ];
  };

  if (current.loading) return <Loading />;

  const LEVELS: { key: Level; label: string }[] = [
    { key: 'client-service-subscriptions', label: 'Subscriptions' },
    { key: 'task-templates', label: 'Task Templates' },
    { key: 'recurring-work-profiles', label: 'Recurring Work' },
  ];

  return (
    <div className="cx-area">
      <div className="cx-subnav">
        {LEVELS.map((l) => (
          <button
            key={l.key}
            type="button"
            className={l.key === level ? 'cx-btn' : 'cx-btn subtle'}
            onClick={() => {
              setLevel(l.key);
              setNotice('');
            }}
          >
            {l.label}
          </button>
        ))}
        <button type="button" className="cx-btn" onClick={() => setEditing(blank())}>
          New
        </button>
      </div>
      <ErrorBar error={current.error || saveError} />
      {notice ? <div className="cx-notice">{notice}</div> : null}
      <DataTable columns={columns()} rows={current.rows} onRow={(r) => setEditing(r)} empty="Nothing here yet." />
      {editing ? (
        <Drawer
          title="Servicing"
          fields={fields()}
          value={editing}
          onChange={setEditing}
          onSave={submit}
          onClose={() => setEditing(null)}
          extra={<ErrorBar error={saveError} />}
        />
      ) : null}
    </div>
  );
}
