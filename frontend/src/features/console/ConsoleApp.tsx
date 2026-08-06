import type * as React from 'react';
import { useEffect, useState } from 'react';
import { list, save } from './api';
import { CatalogueArea } from './catalogue';
import { WorkArea } from './work';
import { ServicingArea } from './servicing';
import { EmployeeOpsArea } from './employee_ops';
import { useBrand } from './branding';
import { EmployeeDashboard, ExecutiveDashboard } from './dashboards';
import { ExpertisePanel } from './expertise';
import { AuditViewer } from './audit';
import { GlobalSearch } from './GlobalSearch';
import {
  ConsultantAdministration,
  IdentityGate,
  UserMenu,
  isProviderAdmin,
  useIdentity,
} from './identity';
import { CLIENT_TYPES, CLIENT_LIFECYCLE_STATUS, ENGAGEMENT_STATUS, WORK_STATUS, isOverdue, label } from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';
import type { Column, Field } from './ui';
import './console.css';

type Area = 'dashboard' | 'my-dashboard' | 'firm-overview' | 'clients' | 'work' | 'servicing' | 'employee-ops' | 'team' | 'services' | 'reports' | 'audit' | 'identity' | 'settings';

const NAV: { key: Area; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'my-dashboard', label: 'My Dashboard' },
  { key: 'firm-overview', label: 'Firm Overview' },
  { key: 'clients', label: 'Clients' },
  { key: 'work', label: 'Work' },
  { key: 'servicing', label: 'Servicing' },
  { key: 'employee-ops', label: 'Employee Ops' },
  { key: 'team', label: 'Team' },
  { key: 'services', label: 'Services' },
  { key: 'reports', label: 'Reports' },
  { key: 'audit', label: 'Audit' },
  { key: 'identity', label: 'Identity & Access' },
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

  const loading =
    clients.loading
    || employees.loading
    || services.loading
    || work.loading
    || docs.loading;

  if (loading) return <Loading />;

  const now = new Date();
  const today = todayStr();

  const isOpen = (row: Row): boolean => (
    row.status !== 'COMPLETED'
    && row.status !== 'CANCELLED'
  );

  const daysFromToday = (value: unknown): number | null => {
    if (!value) return null;

    const parsed = new Date(String(value));

    if (Number.isNaN(parsed.getTime())) return null;

    const todayStart = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    );

    const dateStart = new Date(
      parsed.getFullYear(),
      parsed.getMonth(),
      parsed.getDate(),
    );

    return Math.round(
      (dateStart.getTime() - todayStart.getTime())
      / (1000 * 60 * 60 * 24),
    );
  };

  const ageInDays = (value: unknown): number => {
    if (!value) return 0;

    const parsed = new Date(String(value));

    if (Number.isNaN(parsed.getTime())) return 0;

    return Math.max(
      0,
      Math.floor(
        (now.getTime() - parsed.getTime())
        / (1000 * 60 * 60 * 24),
      ),
    );
  };

  const activeClients = clients.rows.filter(
    (client) => client.engagement_status === 'ACTIVE',
  );

  const openWork = work.rows.filter(isOpen);

  const overdueWork = openWork.filter(
    (row) => isOverdue(row.due_date, row.status),
  );

  const dueToday = openWork.filter(
    (row) => String(row.due_date ?? '').slice(0, 10) === today,
  );

  const dueSoon = openWork.filter((row) => {
    const days = daysFromToday(row.due_date);
    return days !== null && days > 0 && days <= 7;
  });

  const waitingForClient = openWork.filter(
    (row) => row.status === 'WAITING_FOR_CLIENT',
  );

  const readyForReview = openWork.filter(
    (row) => row.status === 'READY_FOR_REVIEW',
  );

  const reworkRequired = openWork.filter(
    (row) => row.status === 'REWORK_REQUIRED',
  );

  const highPriorityOverdue = overdueWork.filter((row) => (
    row.priority === 'HIGH'
    || row.priority === 'URGENT'
    || row.priority === 'CRITICAL'
  ));

  const completedToday = work.rows.filter(
    (row) => String(row.completed_at ?? '').slice(0, 10) === today,
  );

  const pendingDocuments = docs.rows.filter((row) => (
    row.status === 'REQUESTED'
    || row.status === 'PARTIALLY_RECEIVED'
  ));

  const documentAgeBuckets = [
    {
      label: '0–3 days',
      count: pendingDocuments.filter(
        (row) => ageInDays(row.created_at || row.requested_at) <= 3,
      ).length,
      tone: 'good',
    },
    {
      label: '4–7 days',
      count: pendingDocuments.filter((row) => {
        const age = ageInDays(row.created_at || row.requested_at);
        return age >= 4 && age <= 7;
      }).length,
      tone: 'watch',
    },
    {
      label: '8–15 days',
      count: pendingDocuments.filter((row) => {
        const age = ageInDays(row.created_at || row.requested_at);
        return age >= 8 && age <= 15;
      }).length,
      tone: 'risk',
    },
    {
      label: '15+ days',
      count: pendingDocuments.filter(
        (row) => ageInDays(row.created_at || row.requested_at) > 15,
      ).length,
      tone: 'critical',
    },
  ];

  const statusDistribution = WORK_STATUS
    .map((status) => ({
      status,
      count: work.rows.filter((row) => row.status === status).length,
    }))
    .filter((item) => item.count > 0);

  const maxStatusCount = Math.max(
    1,
    ...statusDistribution.map((item) => item.count),
  );

  const employeeWorkload = employees.rows
    .filter((employee) => employee.is_active !== false)
    .map((employee) => {
      const assigned = openWork.filter(
        (row) => String(row.owner_user_id) === String(employee.id),
      );

      const overdue = assigned.filter(
        (row) => isOverdue(row.due_date, row.status),
      );

      const review = openWork.filter(
        (row) => (
          String(row.reviewer_user_id) === String(employee.id)
          && row.status === 'READY_FOR_REVIEW'
        ),
      );

      const score =
        assigned.length
        + (overdue.length * 2)
        + review.length;

      const pressure =
        score >= 8
          ? 'OVERLOADED'
          : score >= 5
            ? 'BUSY'
            : score >= 2
              ? 'BALANCED'
              : 'AVAILABLE';

      return {
        id: String(employee.id),
        name: String(employee.name || employee.email || 'Unnamed employee'),
        assigned: assigned.length,
        overdue: overdue.length,
        review: review.length,
        score,
        pressure,
      };
    })
    .sort((a, b) => b.score - a.score);

  const maxEmployeeScore = Math.max(
    1,
    ...employeeWorkload.map((employee) => employee.score),
  );

  const clientRisk = activeClients
    .map((client) => {
      const clientId = String(client.id);

      const clientWork = openWork.filter(
        (row) => String(row.client_id) === clientId,
      );

      const overdue = clientWork.filter(
        (row) => isOverdue(row.due_date, row.status),
      );

      const waiting = clientWork.filter(
        (row) => row.status === 'WAITING_FOR_CLIENT',
      );

      const nextDue = clientWork
        .filter((row) => row.due_date)
        .sort(
          (a, b) => String(a.due_date).localeCompare(String(b.due_date)),
        )[0];

      const riskScore =
        (overdue.length * 3)
        + (waiting.length * 2)
        + clientWork.length;

      return {
        id: clientId,
        name: String(
          client.trade_name
          || client.legal_name
          || 'Unnamed client',
        ),
        open: clientWork.length,
        overdue: overdue.length,
        waiting: waiting.length,
        nextDue: String(nextDue?.due_date ?? ''),
        riskScore,
        risk:
          riskScore >= 10
            ? 'HIGH'
            : riskScore >= 5
              ? 'MEDIUM'
              : 'LOW',
      };
    })
    .filter((client) => client.open > 0)
    .sort((a, b) => b.riskScore - a.riskScore)
    .slice(0, 6);

  const recentActivity = [...work.rows]
    .sort(
      (a, b) => String(b.updated_at).localeCompare(String(a.updated_at)),
    )
    .slice(0, 7);

  const attentionItems: {
    title: string;
    detail: string;
    tone: 'critical' | 'risk' | 'watch' | 'info';
  }[] = [];

  if (highPriorityOverdue.length > 0) {
    attentionItems.push({
      title: `${highPriorityOverdue.length} high-priority overdue item${
        highPriorityOverdue.length === 1 ? '' : 's'
      }`,
      detail: 'Immediate partner or manager intervention is recommended.',
      tone: 'critical',
    });
  }

  if (overdueWork.length > 0) {
    attentionItems.push({
      title: `${overdueWork.length} overdue work item${
        overdueWork.length === 1 ? '' : 's'
      }`,
      detail: 'Review ownership, blockers and revised completion plans.',
      tone: 'risk',
    });
  }

  if (readyForReview.length > 0) {
    attentionItems.push({
      title: `${readyForReview.length} item${
        readyForReview.length === 1 ? '' : 's'
      } awaiting review`,
      detail: 'Reviewer action can unblock completion and client delivery.',
      tone: 'watch',
    });
  }

  const agedDocuments = pendingDocuments.filter(
    (row) => ageInDays(row.created_at || row.requested_at) > 7,
  );

  if (agedDocuments.length > 0) {
    attentionItems.push({
      title: `${agedDocuments.length} document request${
        agedDocuments.length === 1 ? '' : 's'
      } pending beyond 7 days`,
      detail: 'Client follow-up may be required to protect due dates.',
      tone: 'watch',
    });
  }

  const overloadedEmployees = employeeWorkload.filter(
    (employee) => employee.pressure === 'OVERLOADED',
  );

  if (overloadedEmployees.length > 0) {
    attentionItems.push({
      title: `${overloadedEmployees.length} employee${
        overloadedEmployees.length === 1 ? '' : 's'
      } under high workload pressure`,
      detail: 'Consider redistribution before additional work is assigned.',
      tone: 'risk',
    });
  }

  if (attentionItems.length === 0) {
    attentionItems.push({
      title: 'No critical operational exceptions',
      detail: 'Current workload and deadlines appear under control.',
      tone: 'info',
    });
  }

  const healthPenalty =
    (overdueWork.length * 8)
    + (highPriorityOverdue.length * 7)
    + (agedDocuments.length * 3)
    + (overloadedEmployees.length * 6)
    + (reworkRequired.length * 4);

  const healthScore = Math.max(35, Math.min(100, 100 - healthPenalty));

  const healthLabel =
    healthScore >= 85
      ? 'Strong'
      : healthScore >= 70
        ? 'Stable'
        : healthScore >= 55
          ? 'Attention required'
          : 'At risk';

  const healthTone =
    healthScore >= 85
      ? 'good'
      : healthScore >= 70
        ? 'stable'
        : healthScore >= 55
          ? 'watch'
          : 'risk';

  const kpis = [
    {
      label: 'Active Clients',
      value: activeClients.length,
      note: `${clients.rows.length} total client records`,
      tone: 'blue',
    },
    {
      label: 'Open Work',
      value: openWork.length,
      note: `${completedToday.length} completed today`,
      tone: 'indigo',
    },
    {
      label: 'Overdue',
      value: overdueWork.length,
      note: highPriorityOverdue.length
        ? `${highPriorityOverdue.length} high priority`
        : 'No high-priority exposure',
      tone: overdueWork.length ? 'red' : 'green',
    },
    {
      label: 'Due in 7 Days',
      value: dueSoon.length + dueToday.length,
      note: `${dueToday.length} due today`,
      tone: dueToday.length ? 'amber' : 'violet',
    },
    {
      label: 'Waiting for Client',
      value: waitingForClient.length,
      note: `${pendingDocuments.length} document requests pending`,
      tone: waitingForClient.length ? 'amber' : 'green',
    },
    {
      label: 'Ready for Review',
      value: readyForReview.length,
      note: `${reworkRequired.length} in rework`,
      tone: readyForReview.length ? 'violet' : 'green',
    },
  ];

  const error =
    clients.error
    || employees.error
    || services.error
    || work.error
    || docs.error;

  return (
    <div className="cx-executive-dashboard">
      <ErrorBar error={error} />

      <section className="cx-executive-hero">
        <div>
          <span className="cx-executive-eyebrow">
            Firm Operations Command Center
          </span>

          <h1>Vridhi Consultants</h1>

          <p>
            A live executive view of client delivery, deadlines,
            document dependencies and team workload.
          </p>
        </div>

        <div className={`cx-health-card ${healthTone}`}>
          <div className="cx-health-ring">
            <strong>{healthScore}</strong>
            <small>/100</small>
          </div>

          <div>
            <span>Firm Health</span>
            <strong>{healthLabel}</strong>
            <small>Updated from current operational data</small>

            <span
              className="cx-health-method"
              title="The score considers overdue work, high-priority overdue exposure, aged client-document requests, rework and employee workload pressure."
            >
              ⓘ How this score is calculated
            </span>
          </div>
        </div>
      </section>

      <section className="cx-executive-kpis">
        {kpis.map((kpi) => (
          <article
            key={kpi.label}
            className={`cx-executive-kpi ${kpi.tone}`}
          >
            <span>{kpi.label}</span>
            <strong>{kpi.value}</strong>
            <small>{kpi.note}</small>
          </article>
        ))}
      </section>

      <section className="cx-executive-grid primary">
        <article className="cx-executive-panel attention">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Action Center</span>
              <h2>Needs Attention</h2>
            </div>

            <span className="cx-panel-count">
              {attentionItems.length}
            </span>
          </div>

          <div className="cx-attention-list">
            {attentionItems.map((item) => (
              <div
                key={`${item.title}-${item.detail}`}
                className={`cx-attention-item ${item.tone}`}
              >
                <span className="cx-attention-marker" />

                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="cx-executive-panel deadline">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Delivery Control</span>
              <h2>Deadline Risk</h2>
            </div>
          </div>

          <div className="cx-risk-grid">
            <div className="cx-risk-metric good">
              <strong>
                {Math.max(
                  0,
                  openWork.length
                  - overdueWork.length
                  - dueSoon.length
                  - dueToday.length,
                )}
              </strong>
              <span>On Track</span>
            </div>

            <div className="cx-risk-metric watch">
              <strong>{dueSoon.length}</strong>
              <span>Due Soon</span>
            </div>

            <div className="cx-risk-metric amber">
              <strong>{dueToday.length}</strong>
              <span>Due Today</span>
            </div>

            <div className="cx-risk-metric critical">
              <strong>{overdueWork.length}</strong>
              <span>Overdue</span>
            </div>
          </div>

          <div className="cx-risk-summary">
            <span>High-priority overdue exposure</span>
            <strong>{highPriorityOverdue.length}</strong>
          </div>
        </article>
      </section>

      <section className="cx-executive-grid analytics">
        <article className="cx-executive-panel">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Portfolio Flow</span>
              <h2>Work Status Distribution</h2>
            </div>

            <span className="cx-panel-count">
              {work.rows.length}
            </span>
          </div>

          {statusDistribution.length === 0 ? (
            <div className="cx-executive-empty">
              No work items available.
            </div>
          ) : (
            <div className="cx-status-bars">
              {statusDistribution.map((item) => (
                <div className="cx-status-row" key={item.status}>
                  <div className="cx-status-label">
                    <Chip
                      value={item.status}
                      tone={statusTone(item.status)}
                    />
                    <strong>{item.count}</strong>
                  </div>

                  <div className="cx-status-track">
                    <span
                      style={{
                        width: `${
                          Math.max(
                            8,
                            (item.count / maxStatusCount) * 100,
                          )
                        }%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="cx-executive-panel">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Client Dependency</span>
              <h2>Document Aging</h2>
            </div>

            <span className="cx-panel-count">
              {pendingDocuments.length}
            </span>
          </div>

          <div className="cx-aging-grid">
            {documentAgeBuckets.map((bucket) => (
              <div
                key={bucket.label}
                className={`cx-aging-card ${bucket.tone}`}
              >
                <strong>{bucket.count}</strong>
                <span>{bucket.label}</span>
              </div>
            ))}
          </div>

          <p className="cx-panel-footnote">
            Pending client documents grouped by request age.
          </p>
        </article>
      </section>

      <section className="cx-executive-grid wide">
        <article className="cx-executive-panel workload">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Resource Management</span>
              <h2>Team Workload Pressure</h2>
            </div>

            <span className="cx-panel-count">
              {employeeWorkload.length}
            </span>
          </div>

          {employeeWorkload.length === 0 ? (
            <div className="cx-executive-empty">
              No active employees available.
            </div>
          ) : (
            <div className="cx-workload-table">
              <div className="cx-workload-header">
                <span>Employee</span>
                <span>Open</span>
                <span>Overdue</span>
                <span>Review</span>
                <span>Pressure</span>
              </div>

              {employeeWorkload.slice(0, 8).map((employee) => (
                <div
                  className="cx-workload-row"
                  key={employee.id}
                >
                  <div>
                    <strong>{employee.name}</strong>

                    <div className="cx-workload-track">
                      <span
                        style={{
                          width: `${
                            Math.max(
                              4,
                              (employee.score / maxEmployeeScore) * 100,
                            )
                          }%`,
                        }}
                      />
                    </div>
                  </div>

                  <span>{employee.assigned}</span>

                  <span className={
                    employee.overdue > 0
                      ? 'cx-number-danger'
                      : ''
                  }>
                    {employee.overdue}
                  </span>

                  <span>{employee.review}</span>

                  <Chip
                    value={employee.pressure}
                    tone={
                      employee.pressure === 'OVERLOADED'
                        ? 'danger'
                        : employee.pressure === 'BUSY'
                          ? 'warn'
                          : employee.pressure === 'BALANCED'
                            ? 'ok'
                            : 'muted'
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </article>
      </section>

      <section className="cx-executive-grid bottom">
        <article className="cx-executive-panel client-risk">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Client Portfolio</span>
              <h2>Client Risk Snapshot</h2>
            </div>
          </div>

          {clientRisk.length === 0 ? (
            <div className="cx-executive-empty">
              No active client risk detected.
            </div>
          ) : (
            <div className="cx-client-risk-table">
              <div className="cx-client-risk-header">
                <span>Client</span>
                <span>Open</span>
                <span>Overdue</span>
                <span>Waiting</span>
                <span>Next Due</span>
                <span>Risk</span>
              </div>

              {clientRisk.map((client) => (
                <div
                  className="cx-client-risk-row"
                  key={client.id}
                >
                  <strong>{client.name}</strong>
                  <span>{client.open}</span>

                  <span className={
                    client.overdue > 0
                      ? 'cx-number-danger'
                      : ''
                  }>
                    {client.overdue}
                  </span>

                  <span>{client.waiting}</span>
                  <span>{client.nextDue || '—'}</span>

                  <Chip
                    value={client.risk}
                    tone={
                      client.risk === 'HIGH'
                        ? 'danger'
                        : client.risk === 'MEDIUM'
                          ? 'warn'
                          : 'ok'
                    }
                  />
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="cx-executive-panel activity">
          <div className="cx-executive-panel-head">
            <div>
              <span className="cx-panel-kicker">Latest Movement</span>
              <h2>Recent Firm Activity</h2>
            </div>
          </div>

          {recentActivity.length === 0 ? (
            <div className="cx-executive-empty">
              No recent activity available.
            </div>
          ) : (
            <div className="cx-activity-feed">
              {recentActivity.map((row) => (
                <div
                  className="cx-activity-item"
                  key={String(row.id)}
                >
                  <span className="cx-activity-dot" />

                  <div>
                    <strong>{String(row.title || 'Work item')}</strong>

                    <p>
                      {String(row.client_name || 'Internal')}
                      {' · '}
                      {label(String(row.status || 'UPDATED'))}
                    </p>
                  </div>

                  <time>
                    {String(row.updated_at ?? '')
                      .slice(0, 16)
                      .replace('T', ' ')}
                  </time>
                </div>
              ))}
            </div>
          )}
        </article>
      </section>
    </div>
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
function OperationalConsole(): React.JSX.Element {
  const [area, setArea] = useState<Area>('dashboard');
  const { identity } = useIdentity();
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
      case 'identity':
        return isProviderAdmin(identity) ? <ConsultantAdministration /> : <div className="cx-warning">Administrator access is required.</div>;
      case 'clients':
        return (
          <ResourceManager
            resource="clients"
            title="Client"
            filters={[{ name: 'client_type', options: CLIENT_TYPES }, { name: 'engagement_status', options: ENGAGEMENT_STATUS }, { name: 'lifecycle_status', options: CLIENT_LIFECYCLE_STATUS }]}
            columns={[
              { key: 'legal_name', header: 'Client', render: (r) => String(r.trade_name || r.legal_name) },
              { key: 'client_type', header: 'Type', render: (r) => label(String(r.client_type)) },
              { key: 'pan', header: 'PAN' },
              { key: 'lifecycle_status', header: 'Lifecycle', render: (r) => <Chip value={String(r.lifecycle_status ?? 'PROSPECT')} /> },
              { key: 'engagement_status', header: 'Status', render: (r) => <Chip value={String(r.engagement_status)} tone={statusTone(String(r.engagement_status))} /> },
            ]}
            blank={{ legal_name: '', trade_name: '', client_type: 'PRIVATE_LIMITED', engagement_status: 'ACTIVE', lifecycle_status: 'PROSPECT' }}
            fields={[
              { name: 'legal_name' },
              { name: 'trade_name' },
              { name: 'client_type', kind: 'select', options: CLIENT_TYPES },
              { name: 'industry' },
              { name: 'pan' },
              { name: 'tan' },
              { name: 'cin_or_llpin' },
              { name: 'registered_address', kind: 'textarea' },
              { name: 'engagement_status', kind: 'select', options: ENGAGEMENT_STATUS },
              { name: 'lifecycle_status', kind: 'select', options: CLIENT_LIFECYCLE_STATUS },
              { name: 'onboarding_date', kind: 'date' },
              { name: 'activation_date', kind: 'date' },
              { name: 'suspension_date', kind: 'date' },
              { name: 'suspension_reason', kind: 'textarea' },
              { name: 'closure_date', kind: 'date' },
              { name: 'closure_reason', kind: 'textarea' },
              { name: 'archive_date', kind: 'date' },
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
      case 'servicing':
        return <ServicingArea />;
      case 'employee-ops':
        return <EmployeeOpsArea />;
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
          {NAV.filter((n) => {
            if (n.key === 'identity') return isProviderAdmin(identity);
            if (n.key === 'firm-overview' || n.key === 'audit') {
              return brand.capabilities?.is_executive === true;
            }
            return true;
          }).map((n) => (
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
          <GlobalSearch onNavigate={setArea} />
          <UserMenu />
        </header>
        <div className="cx-body">{view}</div>
      </div>
    </div>
  );
}
export function ConsoleApp(): React.JSX.Element {
  return (
    <IdentityGate>
      <OperationalConsole />
    </IdentityGate>
  );
}
