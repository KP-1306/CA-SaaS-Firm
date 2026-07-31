import type * as React from 'react';
import { useEffect, useState } from 'react';
import { getObject } from './api';
import type { Row } from './types';
import { DataTable, Empty, ErrorBar, Loading } from './ui';

type Dict = Record<string, unknown>;

function useDashboard(path: string, params: Record<string, string>): { data: Dict | null; error: string; loading: boolean } {
  const [data, setData] = useState<Dict | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify([path, params]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    getObject(path, params)
      .then((row) => {
        if (active) {
          setData(row as Dict);
          setError('');
        }
      })
      .catch((e: unknown) => active && setError(String(e instanceof Error ? e.message : e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [key]);
  return { data, error, loading };
}

function num(v: unknown): number {
  return typeof v === 'number' ? v : Number(v ?? 0);
}

function MetricCard({ n, label, danger, onClick }: { n: unknown; label: string; danger?: boolean; onClick?: (() => void) | undefined }): React.JSX.Element {
  return (
    <div className={`cx-card${onClick ? ' cx-card-link' : ''}`} onClick={onClick} role={onClick ? 'button' : undefined}>
      <div className="n" style={danger && num(n) > 0 ? { color: '#b42318' } : undefined}>{String(n ?? 0)}</div>
      <div className="l">{label}</div>
    </div>
  );
}

const PERIODS = ['today', 'week', 'month', 'quarter'] as const;

function PeriodPicker({ period, setPeriod }: { period: string; setPeriod: (p: string) => void }): React.JSX.Element {
  return (
    <div className="cx-toolbar">
      {PERIODS.map((p) => (
        <button key={p} className={`cx-btn ${p === period ? '' : 'subtle'}`} onClick={() => setPeriod(p)}>
          {p.charAt(0).toUpperCase() + p.slice(1)}
        </button>
      ))}
    </div>
  );
}

export function EmployeeDashboard({ onDrill }: { onDrill?: (filter: Record<string, string>) => void }): React.JSX.Element {
  const [period, setPeriod] = useState('month');
  const { data, error, loading } = useDashboard('dashboard/employee', { period });
  if (loading) return <Loading />;
  if (error) return <ErrorBar error={error} />;
  if (!data) return <Empty message="No dashboard data." />;
  const mw = (data.my_work ?? {}) as Dict;
  const dc = (data.document_centre ?? {}) as Dict;
  const wl = (data.workload ?? {}) as Dict;
  const drill = (f: Record<string, string>): (() => void) | undefined => (onDrill ? () => onDrill(f) : undefined);
  const statusDist = (wl.status_distribution ?? {}) as Dict;
  return (
    <>
      <PeriodPicker period={period} setPeriod={setPeriod} />
      <h3 className="cx-section-title">My Work</h3>
      <div className="cx-cards">
        <MetricCard n={mw.assigned_open} label="Assigned (open)" onClick={drill({})} />
        <MetricCard n={mw.due_today} label="Due today" onClick={drill({})} />
        <MetricCard n={mw.overdue} label="Overdue" danger onClick={drill({ overdue: '1' })} />
        <MetricCard n={mw.waiting_for_client} label="Waiting for client" onClick={drill({ status: 'WAITING_FOR_CLIENT' })} />
        <MetricCard n={mw.ready_for_review} label="Ready for review" onClick={drill({ status: 'READY_FOR_REVIEW' })} />
        <MetricCard n={mw.rework_required} label="Rework required" danger onClick={drill({ status: 'REWORK_REQUIRED' })} />
        <MetricCard n={mw.recently_completed} label="Recently completed" />
      </div>
      <h3 className="cx-section-title">Document Action Centre</h3>
      <div className="cx-cards">
        <MetricCard n={dc.awaiting_client} label="Awaiting client" />
        <MetricCard n={dc.uploads_awaiting_review} label="Uploads to review" />
        <MetricCard n={dc.rejected_attachments} label="Rejected attachments" danger />
      </div>
      <h3 className="cx-section-title">Workload &amp; Productivity</h3>
      <div className="cx-cards">
        <MetricCard n={wl.open_workload} label="Open workload" />
        <MetricCard n={wl.completed_in_period} label="Completed (period)" />
        <MetricCard n={wl.pending_reviews_assigned} label="Pending reviews" />
        <MetricCard n={wl.avg_completion_days ?? '-'} label="Avg completion (days)" />
      </div>
      <div className="cx-panel">
        <h3>Status distribution</h3>
        <div style={{ padding: '12px 16px' }}>
          {Object.keys(statusDist).length === 0 ? (
            <span style={{ color: '#64748b' }}>No work assigned.</span>
          ) : (
            Object.entries(statusDist).map(([s, n]) => (
              <span key={s} style={{ marginRight: 12 }}>{s}: {String(n)}</span>
            ))
          )}
        </div>
      </div>
    </>
  );
}

export function ExecutiveDashboard({ onDrill }: { onDrill?: (filter: Record<string, string>) => void }): React.JSX.Element {
  const [period, setPeriod] = useState('month');
  const { data, error, loading } = useDashboard('dashboard/executive', { period });
  if (loading) return <Loading />;
  if (error) return <ErrorBar error={error} />;
  if (!data) return <Empty message="No dashboard data." />;
  const ov = (data.overview ?? {}) as Dict;
  const ops = (data.operations ?? {}) as Dict;
  const wl = (data.employee_workload ?? {}) as Dict;
  const ch = (data.client_health ?? {}) as Dict;
  const ac = (data.action_centre ?? {}) as Dict;
  const drill = (f: Record<string, string>): (() => void) | undefined => (onDrill ? () => onDrill(f) : undefined);
  const ageing = (ops.ageing_buckets ?? {}) as Dict;
  const byStatus = (ops.by_status ?? {}) as Dict;
  const workloadRows = ((wl.rows ?? []) as Row[]);
  const clientRows = ((ch.rows ?? []) as Row[]);
  return (
    <>
      <PeriodPicker period={period} setPeriod={setPeriod} />
      <h3 className="cx-section-title">Executive Overview</h3>
      <div className="cx-cards">
        <MetricCard n={ov.active_clients} label="Active clients" />
        <MetricCard n={ov.active_work} label="Active work" onClick={drill({})} />
        <MetricCard n={ov.due_today} label="Due today" />
        <MetricCard n={ov.overdue} label="Overdue" danger onClick={drill({ overdue: '1' })} />
        <MetricCard n={ov.waiting_for_client} label="Waiting for client" onClick={drill({ status: 'WAITING_FOR_CLIENT' })} />
        <MetricCard n={ov.ready_for_review} label="Ready for review" onClick={drill({ status: 'READY_FOR_REVIEW' })} />
        <MetricCard n={ov.rework_required} label="Rework required" danger onClick={drill({ status: 'REWORK_REQUIRED' })} />
        <MetricCard n={ov.recently_completed} label="Recently completed" />
      </div>
      <div className="cx-panel">
        <h3>Firm operations</h3>
        <div style={{ padding: '12px 16px' }}>
          <strong>By status:</strong>{' '}
          {Object.entries(byStatus).map(([s, n]) => <span key={s} style={{ marginRight: 12 }}>{s}: {String(n)}</span>)}
          <div style={{ marginTop: 8 }}>
            <strong>Ageing (open):</strong>{' '}
            {Object.entries(ageing).map(([b, n]) => <span key={b} style={{ marginRight: 12 }}>{b}d: {String(n)}</span>)}
          </div>
          <div style={{ marginTop: 8 }}>
            <strong>Completed (period):</strong> {String(ops.completed_in_period ?? 0)} &nbsp;
            <strong>Avg days:</strong> {String(ops.avg_completion_days ?? '-')}
          </div>
        </div>
      </div>
      <div className="cx-panel">
        <h3>Employee workload</h3>
        <DataTable
          empty="No workload data."
          columns={[
            { key: 'employee_name', header: 'Employee' },
            { key: 'open_work', header: 'Open' },
            { key: 'overdue', header: 'Overdue' },
            { key: 'completed_in_period', header: 'Completed' },
            { key: 'rework_count', header: 'Rework' },
          ]}
          rows={workloadRows}
        />
        <div style={{ padding: '8px 16px', color: '#64748b' }}>
          Unassigned work: {String(wl.unassigned ?? 0)} - Pending reviews: {String(wl.pending_reviews ?? 0)}
        </div>
      </div>
      <div className="cx-panel">
        <h3>Client health</h3>
        <DataTable
          empty="No client risk data."
          columns={[
            { key: 'client_name', header: 'Client' },
            { key: 'open_work', header: 'Open work' },
            { key: 'overdue_work', header: 'Overdue' },
            { key: 'pending_documents', header: 'Pending docs' },
          ]}
          rows={clientRows}
        />
      </div>
      <h3 className="cx-section-title">Executive Action Centre</h3>
      <div className="cx-cards">
        <MetricCard n={ac.overdue} label="Overdue" danger onClick={drill({ overdue: '1' })} />
        <MetricCard n={ac.unassigned} label="Unassigned" onClick={drill({ unassigned: '1' })} />
        <MetricCard n={ac.awaiting_reviewer} label="Awaiting reviewer" />
        <MetricCard n={ac.review_backlog} label="Review backlog" onClick={drill({ status: 'READY_FOR_REVIEW' })} />
        <MetricCard n={ac.rework_required} label="Rework required" danger onClick={drill({ status: 'REWORK_REQUIRED' })} />
        <MetricCard n={ac.long_waiting_documents} label="Long-waiting docs" />
      </div>
    </>
  );
}
