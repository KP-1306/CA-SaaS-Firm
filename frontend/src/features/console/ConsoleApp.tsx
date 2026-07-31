import type * as React from 'react';
import { useEffect, useState } from 'react';
import { list, save } from './api';
import { CatalogueArea } from './catalogue';
import { WorkArea } from './work';
import { useBrand } from './branding';
import { EmployeeDashboard, ExecutiveDashboard } from './dashboards';
import { ExpertisePanel } from './expertise';
import { AuditViewer } from './audit';
import { CLIENT_TYPES, ENGAGEMENT_STATUS, WORK_STATUS, isOverdue, label } from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';
import type { Column, Field } from './ui';
import './console.css';

type Area = 'dashboard' | 'my-dashboard' | 'firm-overview' | 'clients' | 'work' | 'team' | 'services' | 'reports' | 'audit' | 'settings';

const NAV: { key: Area; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'my-dashboard', label: 'My Dashboard' },
  { key: 'firm-overview', label: 'Firm Overview' },
  { key: 'clients', label: 'Clients' },
  { key: 'work', label: 'Work' },
  { key: 'team', label: 'Team' },
  { key: 'services', label: 'Services' },
  { key: 'reports', label: 'Reports' },
  { key: 'audit', label: 'Audit' },
  { key: 'settings', label: 'Settings' },
];

function useRows(resource: string, params: Record<string, string> = {}): {
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

function statusTone(status: string): string {
  if (status === 'COMPLETED' || status === 'ACTIVE' || status === 'RECEIVED') return 'ok';
  if (status === 'CANCELLED' || status === 'INACTIVE' || status === 'REWORK_REQUIRED') return 'danger';
  if (status === 'WAITING_FOR_CLIENT' || status === 'READY_FOR_REVIEW' || status === 'REQUESTED') return 'warn';
  return 'muted';
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

// ---------------- Dashboard ----------------
function Dashboard(): React.JSX.Element {
  const clients = useRows('clients');
  const employees = useRows('employees');
  const services = useRows('services');
  const work = useRows('work-items');
  const docs = useRows('document-requests');
  if (clients.loading || work.loading) return <Loading />;
  const open = work.rows.filter((w) => w.status !== 'COMPLETED' && w.status !== 'CANCELLED');
  const overdue = open.filter((w) => isOverdue(w.due_date, w.status));
  const waiting = work.rows.filter((w) => w.status === 'WAITING_FOR_CLIENT').length;
  const ready = work.rows.filter((w) => w.status === 'READY_FOR_REVIEW').length;
  const rework = work.rows.filter((w) => w.status === 'REWORK_REQUIRED').length;
  const completedToday = work.rows.filter((w) => String(w.completed_at ?? '').slice(0, 10) === todayStr()).length;
  const pendingDocs = docs.rows.filter((d) => d.status === 'REQUESTED' || d.status === 'PARTIALLY_RECEIVED').length;
  const byStatus = WORK_STATUS.map((s) => ({ s, n: work.rows.filter((w) => w.status === s).length })).filter((x) => x.n > 0);
  const recent = [...work.rows].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))).slice(0, 8);
  const card = (n: number | string, l: string, danger = false): React.JSX.Element => (
    <div className="cx-card"><div className="n" style={danger && Number(n) > 0 ? { color: '#b42318' } : undefined}>{n}</div><div className="l">{l}</div></div>
  );
  return (
    <>
      <ErrorBar error={clients.error || work.error} />
      <div className="cx-cards">
        {card(clients.rows.filter((c) => c.engagement_status === 'ACTIVE').length, 'Active clients')}
        {card(employees.rows.length, 'Employees')}
        {card(services.rows.length, 'Services')}
        {card(open.length, 'Open work')}
        {card(overdue.length, 'Overdue', true)}
        {card(waiting, 'Waiting for client')}
        {card(ready, 'Ready for review')}
        {card(rework, 'Rework required', true)}
        {card(completedToday, 'Completed today')}
        {card(pendingDocs, 'Pending documents')}
      </div>
      <div className="cx-panel">
        <h3>Work by status</h3>
        <div style={{ padding: '12px 16px' }}>
          {byStatus.length === 0 ? (
            <span style={{ color: '#64748b' }}>No work items yet.</span>
          ) : (
            byStatus.map((x) => (
              <span key={x.s} style={{ marginRight: 10, display: 'inline-block', marginBottom: 6 }}>
                <Chip value={x.s} tone={statusTone(x.s)} /> {x.n}
              </span>
            ))
          )}
        </div>
      </div>
      <div className="cx-panel">
        <h3>Recent work activity</h3>
        <DataTable
          empty="No work yet."
          columns={[
            { key: 'title', header: 'Title' },
            { key: 'client_name', header: 'Client', render: (r) => String(r.client_name || '""') },
            { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} tone={statusTone(String(r.status))} /> },
            { key: 'updated_at', header: 'Updated', render: (r) => String(r.updated_at ?? '').slice(0, 10) },
          ]}
          rows={recent}
        />
      </div>
    </>
  );
}

export function buildResourcePayload(editing: Row): Row {
  const serverDisplayFields = new Set([
    'client_name',
    'service_name',
    'owner_name',
    'reviewer_name',
  ]);
  const clean: Row = {};
  for (const [key, value] of Object.entries(editing)) {
    if (value !== '' && !serverDisplayFields.has(key) && key !== 'is_overdue' && key !== 'attachment_count') {
      clean[key] = value;
    }
  }
  return clean;
}

// ---------------- Generic resource manager ----------------
function ResourceManager({
  resource,
  title,
  columns,
  fields,
  blank,
  filters,
  drawerExtra,
}: {
  resource: string;
  title: string;
  columns: Column[];
  fields: Field[];
  blank: Row;
  filters?: { name: string; options: readonly string[] }[];
  drawerExtra?: (editing: Row) => React.ReactNode;
}): React.JSX.Element {
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [filterVals, setFilterVals] = useState<Record<string, string>>({});
  const params: Record<string, string> = { search: applied, ...filterVals };
  const { rows, error, loading, reload } = useRows(resource, params);
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');

  const submit = (): void => {
    if (!editing) return;
    const clean = buildResourcePayload(editing);
    save(resource, clean)
      .then(() => {
        setEditing(null);
        setSaveError('');
        reload();
      })
      .catch((e: unknown) => setSaveError(String(e instanceof Error ? e.message : e)));
  };

  return (
    <>
      <ErrorBar error={error} />
      <div className="cx-toolbar">
        <input
          type="search"
          placeholder={`Search ${title.toLowerCase()}`}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setApplied(search)}
        />
        <button className="cx-btn subtle" onClick={() => setApplied(search)}>Search</button>
        {filters?.map((f) => (
          <select key={f.name} value={filterVals[f.name] ?? ''} onChange={(e) => setFilterVals({ ...filterVals, [f.name]: e.target.value })}>
            <option value="">All {label(f.name)}</option>
            {f.options.map((o) => <option key={o} value={o}>{label(o)}</option>)}
          </select>
        ))}
        <div className="cx-spacer" />
        <button className="cx-btn" onClick={() => { setEditing({ ...blank }); setSaveError(''); }}>Add {title}</button>
      </div>
      {loading ? <Loading /> : <DataTable columns={columns} rows={rows} onRow={(r) => { setEditing({ ...r }); setSaveError(''); }} empty={`No ${title.toLowerCase()} yet.`} />}
      {editing && (
        <Drawer
          title={`${editing.id ? 'Edit' : 'New'} ${title}`}
          fields={fields}
          value={editing}
          onChange={setEditing}
          onClose={() => setEditing(null)}
          onSave={submit}
          extra={(
            <>
              <ErrorBar error={saveError} />
              {drawerExtra?.(editing)}
            </>
          )}
        />
      )}
    </>
  );
}


// ---------------- Client contacts ----------------
const CONTACT_CHANNELS = ['WHATSAPP', 'EMAIL', 'PHONE', 'PORTAL', 'MANUAL'] as const;

function blankClientContact(primary: boolean): Row {
  return {
    name: '',
    designation: '',
    email: '',
    mobile: '',
    whatsapp_number: '',
    preferred_channel: 'WHATSAPP',
    can_receive_document_requests: true,
    is_primary: primary,
    is_active: true,
  };
}

export function ClientContactsPanel({ clientId }: { clientId: string }): React.JSX.Element {
  const contacts = useRows('client-contacts', { client_id: clientId });
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');

  const submit = (): void => {
    if (!editing) return;
    save('client-contacts', { ...editing, client_id: clientId })
      .then(() => {
        setEditing(null);
        setSaveError('');
        contacts.reload();
      })
      .catch((e: unknown) => setSaveError(String(e instanceof Error ? e.message : e)));
  };

  return (
    <section aria-label="Client contacts">
      <div className="cx-subhead">
        <h4>Contacts</h4>
        <button
          className="cx-btn subtle"
          type="button"
          onClick={() => {
            setEditing(blankClientContact(!contacts.rows.some((c) => c.is_primary)));
            setSaveError('');
          }}
        >
          Add contact
        </button>
      </div>

      <ErrorBar error={contacts.error} />

      {contacts.loading ? (
        <Loading />
      ) : contacts.rows.length === 0 ? (
        <div className="cx-empty">No contacts have been added for this client.</div>
      ) : (
        <table className="cx-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Contact</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {contacts.rows.map((contact) => (
              <tr
                key={String(contact.id)}
                onClick={() => {
                  setEditing({ ...contact });
                  setSaveError('');
                }}
                style={{ cursor: 'pointer' }}
              >
                <td>
                  <strong>{String(contact.name || 'Unnamed contact')}</strong>
                  <div className="cx-muted">{String(contact.designation || '')}</div>
                </td>
                <td>
                  <div>{String(contact.email || '')}</div>
                  <div className="cx-muted">
                    {String(contact.mobile || contact.whatsapp_number || '')}
                  </div>
                </td>
                <td>
                  {contact.is_primary ? <Chip value="PRIMARY" tone="ok" /> : null}
                  {' '}
                  {contact.can_receive_document_requests !== false
                    ? <Chip value="DOCUMENTS" tone="muted" />
                    : null}
                  {' '}
                  {!contact.is_active ? <Chip value="INACTIVE" tone="danger" /> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Drawer
          title={`${editing.id ? 'Edit' : 'New'} Client Contact`}
          value={editing}
          onChange={setEditing}
          onClose={() => setEditing(null)}
          onSave={submit}
          extra={<ErrorBar error={saveError} />}
          fields={[
            { name: 'name' },
            { name: 'designation' },
            { name: 'email' },
            { name: 'mobile' },
            { name: 'whatsapp_number' },
            { name: 'preferred_channel', kind: 'select', options: CONTACT_CHANNELS },
            { name: 'can_receive_document_requests', kind: 'checkbox' },
            { name: 'is_primary', kind: 'checkbox' },
            { name: 'is_active', kind: 'checkbox' },
          ]}
        />
      )}
    </section>
  );
}

// ---------------- Reports ----------------
function Reports(): React.JSX.Element {
  const work = useRows('work-items');
  const docs = useRows('document-requests');
  const employees = useRows('employees');
  if (work.loading) return <Loading />;
  const overdue = work.rows.filter((w) => isOverdue(w.due_date, w.status));
  const waiting = work.rows.filter((w) => w.status === 'WAITING_FOR_CLIENT');
  const ready = work.rows.filter((w) => w.status === 'READY_FOR_REVIEW');
  const rework = work.rows.filter((w) => w.status === 'REWORK_REQUIRED');
  const completed = work.rows.filter((w) => w.status === 'COMPLETED');
  const pendingDocs = docs.rows.filter((d) => d.status === 'REQUESTED' || d.status === 'PARTIALLY_RECEIVED');
  const workload = employees.rows.map((e) => ({
    name: String(e.name),
    open: work.rows.filter((w) => w.owner_user_id === e.id && w.status !== 'COMPLETED' && w.status !== 'CANCELLED').length,
  })).filter((x) => x.open > 0);

  const csv = (name: string, rows: Row[], cols: { key: string; header: string }[]): void => {
    const head = cols.map((c) => c.header).join(',');
    const body = rows.map((r) => cols.map((c) => JSON.stringify(String(r[c.key] ?? ''))).join(',')).join('\n');
    const blob = new Blob([`${head}\n${body}`], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${name}.csv`;
    a.click();
  };

  const workCols = [
    { key: 'title', header: 'Title' },
    { key: 'client_name', header: 'Client' },
    { key: 'service_name', header: 'Service' },
    { key: 'owner_name', header: 'Owner' },
    { key: 'due_date', header: 'Due' },
    { key: 'status', header: 'Status' },
  ];

  const section = (heading: string, rows: Row[], cols: { key: string; header: string }[], file: string): React.JSX.Element => (
    <div className="cx-panel">
      <h3>{heading} ({rows.length})</h3>
      <div style={{ padding: 12 }}>
        <button className="cx-btn ghost" onClick={() => csv(file, rows, cols)} disabled={rows.length === 0}>Export CSV</button>
      </div>
      <DataTable
        empty="Nothing to show."
        columns={cols.map((c) => (c.key === 'status' ? { key: c.key, header: c.header, render: (r: Row) => <Chip value={String(r[c.key])} tone={statusTone(String(r[c.key]))} /> } : { key: c.key, header: c.header }))}
        rows={rows}
      />
    </div>
  );

  return (
    <>
      <ErrorBar error={work.error} />
      {section('Overdue work', overdue, workCols, 'overdue-work')}
      {section('Waiting for client documents', waiting, workCols, 'waiting-for-client')}
      {section('Ready for review', ready, workCols, 'ready-for-review')}
      {section('Rework required', rework, workCols, 'rework-required')}
      {section('Recently completed', completed.slice(0, 30), workCols, 'completed-work')}
      {section('Pending documents', pendingDocs, [{ key: 'name', header: 'Document' }, { key: 'client_name', header: 'Client' }, { key: 'due_date', header: 'Due' }, { key: 'status', header: 'Status' }], 'pending-documents')}
      <div className="cx-panel">
        <h3>Employee workload ({workload.length})</h3>
        <div style={{ padding: 12 }}>
          <button className="cx-btn ghost" onClick={() => csv('employee-workload', workload as unknown as Row[], [{ key: 'name', header: 'Employee' }, { key: 'open', header: 'Open work' }])} disabled={workload.length === 0}>Export CSV</button>
        </div>
        {workload.length === 0 ? <div className="cx-empty">No open work assigned.</div> : (
          <table className="cx-table"><thead><tr><th>Employee</th><th>Open work</th></tr></thead>
            <tbody>{workload.map((w) => <tr key={w.name}><td>{w.name}</td><td>{w.open}</td></tr>)}</tbody></table>
        )}
      </div>
    </>
  );
}

// ---------------- Root ----------------
export function ConsoleApp(): React.JSX.Element {
  const [area, setArea] = useState<Area>('dashboard');
  const brand = useBrand();
  const view = ((): React.JSX.Element => {
    switch (area) {
      case 'dashboard':
        return <Dashboard />;
      case 'my-dashboard':
        return <EmployeeDashboard onDrill={(f) => { setArea('work'); void f; }} />;
      case 'firm-overview':
        return <ExecutiveDashboard onDrill={(f) => { setArea('work'); void f; }} />;
      case 'audit':
        return <AuditViewer />;
      case 'clients':
        return (
          <ResourceManager
            resource="clients"
            title="Client"
            filters={[{ name: 'client_type', options: CLIENT_TYPES }, { name: 'engagement_status', options: ENGAGEMENT_STATUS }]}
            columns={[
              { key: 'legal_name', header: 'Client', render: (r) => String(r.trade_name || r.legal_name) },
              { key: 'client_type', header: 'Type', render: (r) => label(String(r.client_type)) },
              { key: 'pan', header: 'PAN' },
              { key: 'engagement_status', header: 'Status', render: (r) => <Chip value={String(r.engagement_status)} tone={statusTone(String(r.engagement_status))} /> },
            ]}
            blank={{ legal_name: '', trade_name: '', client_type: 'PRIVATE_LIMITED', engagement_status: 'ACTIVE' }}
            fields={[
              { name: 'legal_name' },
              { name: 'trade_name' },
              { name: 'client_type', kind: 'select', options: CLIENT_TYPES },
              { name: 'industry' },
              { name: 'pan' },
              { name: 'cin_or_llpin' },
              { name: 'registered_address', kind: 'textarea' },
              { name: 'engagement_status', kind: 'select', options: ENGAGEMENT_STATUS },
              { name: 'notes', kind: 'textarea' },
            ]}
            drawerExtra={(client) => (
              client.id
                ? <ClientContactsPanel key={String(client.id)} clientId={String(client.id)} />
                : <div className="cx-warning">Save the client before adding contacts.</div>
            )}
          />
        );
      case 'work':
        return <WorkArea />;
      case 'team':
        return (
          <ResourceManager
            resource="employees"
            title="Employee"
            columns={[
              { key: 'name', header: 'Name' },
              { key: 'email', header: 'Email' },
              { key: 'role', header: 'Role', render: (r) => label(String(r.role)) },
              { key: 'is_active', header: 'Active', render: (r) => <Chip value={r.is_active ? 'ACTIVE' : 'INACTIVE'} tone={r.is_active ? 'ok' : 'danger'} /> },
            ]}
            blank={{ name: '', email: '', role: 'STAFF', is_active: true }}
            fields={[
              { name: 'name' },
              { name: 'email' },
              { name: 'mobile' },
              { name: 'employee_code' },
              { name: 'role', kind: 'select', options: ['ADMIN', 'PARTNER', 'MANAGER', 'STAFF', 'READ_ONLY'] },
              { name: 'is_active', kind: 'checkbox' },
            ]}
            drawerExtra={(employee) => (
              employee.id
                ? <ExpertisePanel key={String(employee.id)} employeeId={String(employee.id)} />
                : <div className="cx-warning">Save the employee before adding expertise.</div>
            )}
          />
        );
      case 'services':
        return <CatalogueArea />;
      case 'reports':
        return <Reports />;
      case 'settings':
        return (
          <ResourceManager
            resource="firm"
            title="Firm Profile"
            columns={[
              { key: 'name', header: 'Firm' },
              { key: 'pan', header: 'PAN' },
              { key: 'gstin', header: 'GSTIN' },
              { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} tone={statusTone(String(r.status))} /> },
            ]}
            blank={{ name: '', legal_name: '', status: 'ACTIVE' }}
            fields={[
              { name: 'name' },
              { name: 'legal_name' },
              { name: 'pan' },
              { name: 'gstin' },
              { name: 'email' },
              { name: 'mobile' },
              { name: 'address', kind: 'textarea' },
              { name: 'status', kind: 'select', options: ['ACTIVE', 'INACTIVE'] },
            ]}
          />
        );
    }
  })();

  return (
    <div className="cx-app">
      <aside className="cx-side">
        <div className="cx-brand">{brand.firm_name}<small>Internal console</small></div>
        <nav className="cx-nav">
          {NAV.filter((n) => (n.key === 'firm-overview' || n.key === 'audit') ? brand.capabilities?.is_executive === true : true).map((n) => (
            <button key={n.key} className={n.key === area ? 'active' : ''} onClick={() => setArea(n.key)}>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="cx-side-foot">One firm - operational build</div>
      </aside>
      <div className="cx-main">
        <header className="cx-top">
          <h2>{NAV.find((n) => n.key === area)?.label}</h2>
          <span className="cx-user">Signed in - internal plane</span>
        </header>
        <div className="cx-body">{view}</div>
      </div>
    </div>
  );
}
