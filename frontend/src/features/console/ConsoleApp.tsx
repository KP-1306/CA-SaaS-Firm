import type * as React from 'react';
import { useEffect, useState } from 'react';
import { getObject, list, save } from './api';
import { CatalogueArea } from './catalogue';
import { WorkArea } from './work';
import { ClientWorkspace } from './client-workspace';
import { ServicingArea } from './servicing';
import { EmployeeOpsArea } from './employee_ops';
import { useBrand } from './branding';
import { EmployeeDashboard, ExecutiveDashboard } from './dashboards';
import { ExpertisePanel } from './expertise';
import { AuditViewer } from './audit';
import { ActionCentre } from './action-centre';
import PageHelp from '../../components/help/PageHelp';
import { GlobalSearch } from './GlobalSearch';
import {
  QuickCreateMenu,
} from './quick-create';
import type {
  QuickCreateAction,
} from './quick-create';
import { IdentityAccessAdministration } from './authorization';
import {
  IdentityGate,
  UserMenu,
  isProviderAdmin,
  useIdentity,
} from './identity';
import { CLIENT_TYPES, CLIENT_LIFECYCLE_STATUS, ENGAGEMENT_STATUS, isOverdue, label } from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, ErrorBar, Loading } from './ui';
import type { Column, Field } from './ui';
import './console.css';

type Area = 'dashboard' | 'action-centre' | 'my-dashboard' | 'firm-overview' | 'clients' | 'work' | 'servicing' | 'employee-ops' | 'team' | 'services' | 'reports' | 'audit' | 'identity' | 'settings';

const NAV: { key: Area; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'action-centre', label: 'Action Centre' },
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


// ---------------- Dashboard / Mission Control ----------------

type MissionDict = Record<string, unknown>;

function asMissionDict(value: unknown): MissionDict {
  if (
    value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
  ) {
    return value as MissionDict;
  }

  return {};
}

function asMissionRows(value: unknown): Row[] {
  return Array.isArray(value) ? value as Row[] : [];
}

function missionCount(value: unknown): number {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number : 0;
}

function missionTime(value: unknown): string {
  const raw = String(value ?? '');

  if (!raw) return '';

  return raw.slice(0, 16).replace('T', ' ');
}

type VerticalSummaryRow = {
  vertical_id: string;
  vertical_name: string;
  total_work: number;
  open_work: number;
  completed_work: number;
  overdue: number;
  due_soon: number;
  waiting_on_client: number;
  needs_review: number;
  high_risk: number;
  assigned_staff_count: number;
  staff_workload: Array<{
    employee_id: string;
    employee_name: string;
    open_work: number;
    overdue: number;
  }>;
};

const VERTICAL_DONUT_COLOURS = [
  '#2563eb',
  '#14b8a6',
  '#f59e0b',
  '#8b5cf6',
  '#ef4444',
  '#06b6d4',
  '#84cc16',
  '#f97316',
];

function VerticalDistributionDonut({
  rows,
  onOpenVertical,
}: {
  rows: VerticalSummaryRow[];
  onOpenVertical?: ((verticalId: string) => void) | undefined;
}): React.JSX.Element {
  const chartRows = rows.filter(
    (row) => row.open_work > 0,
  );

  const total = chartRows.reduce(
    (sum, row) => sum + row.open_work,
    0,
  );

  const largestVertical = chartRows.reduce<
    VerticalSummaryRow | undefined
  >(
    (largest, row) =>
      largest === undefined ||
      row.open_work > largest.open_work
        ? row
        : largest,
    undefined,
  );

  const largestShare =
    largestVertical !== undefined && total > 0
      ? (
          (largestVertical.open_work / total)
          * 100
        ).toFixed(1)
      : '0.0';

  const activeVerticalCount = chartRows.length;

  const radius = 66;
  const circumference = 2 * Math.PI * radius;

  let consumed = 0;

  return (
    <div className="cx-vertical-distribution">
      <div className="cx-vertical-donut-shell">
        <svg
          className="cx-vertical-donut"
          viewBox="0 0 180 180"
          role="img"
          aria-label="Open work distribution by vertical"
        >
          <circle
            className="cx-vertical-donut-track"
            cx="90"
            cy="90"
            r={radius}
          />

          {chartRows.map((row, index) => {
            const ratio =
              total > 0
                ? row.open_work / total
                : 0;

            const segment =
              ratio * circumference;

            const offset =
              -consumed * circumference;

            consumed += ratio;

            return (
              <circle
                key={row.vertical_id}
                className="cx-vertical-donut-segment"
                cx="90"
                cy="90"
                r={radius}
                stroke={
                  VERTICAL_DONUT_COLOURS[
                    index %
                      VERTICAL_DONUT_COLOURS.length
                  ]
                }
                strokeDasharray={
                  `${segment} ${
                    circumference - segment
                  }`
                }
                strokeDashoffset={offset}
                onClick={() =>
                  onOpenVertical?.(
                    row.vertical_id,
                  )
                }
              >
                <title>
                  {`${row.vertical_name}: ${
                    row.open_work
                  } open (${(
                    ratio * 100
                  ).toFixed(1)}%)`}
                </title>
              </circle>
            );
          })}
        </svg>

        <div className="cx-vertical-donut-centre">
          <strong>{total}</strong>
          <span>Open Work</span>
        </div>
      </div>

      <div className="cx-vertical-legend">
        {rows.map((row, index) => {
          const percentage =
            total > 0
              ? (
                  (row.open_work / total)
                  * 100
                ).toFixed(1)
              : '0.0';

          return (
            <button
              type="button"
              className="cx-vertical-legend-row"
              key={row.vertical_id}
              onClick={() =>
                onOpenVertical?.(
                  row.vertical_id,
                )
              }
            >
              <span
                className="cx-vertical-legend-dot"
                style={{
                  backgroundColor:
                    VERTICAL_DONUT_COLOURS[
                      index %
                        VERTICAL_DONUT_COLOURS.length
                    ],
                }}
              />

              <span className="cx-vertical-legend-name">
                {row.vertical_name}
              </span>

              <strong>{row.open_work}</strong>

              <span className="cx-vertical-legend-percent">
                {percentage}%
              </span>
            </button>
          );
        })}
      </div>

      <aside
        className="cx-workload-snapshot"
        aria-label="Workload snapshot"
      >
        <div className="cx-workload-snapshot-head">
          <span className="cx-panel-kicker">
            Snapshot
          </span>
          <h3>Workload Snapshot</h3>
          <p>
            Current open-work position across active
            verticals.
          </p>
        </div>

        <div className="cx-workload-snapshot-grid">
          <div className="cx-workload-snapshot-stat">
            <strong>{total}</strong>
            <span>Open Work</span>
          </div>

          <div className="cx-workload-snapshot-stat">
            <strong>
              {largestVertical?.open_work ?? 0}
            </strong>
            <span>Largest Vertical Workload</span>
          </div>

          <div className="cx-workload-snapshot-stat">
            <strong>{largestShare}%</strong>
            <span>Largest Workload Share</span>
          </div>

          <div className="cx-workload-snapshot-stat">
            <strong>{activeVerticalCount}</strong>
            <span>Active Verticals with Work</span>
          </div>
        </div>

        <div className="cx-workload-snapshot-leader">
          <span>Largest current workload</span>
          <strong>
            {largestVertical?.vertical_name ?? 'No open work'}
          </strong>
        </div>
      </aside>
    </div>
  );
}


export function Dashboard({
  onOpenWork,
  onOpenVertical,
}: {
  onOpenWork?: (workItemId: string) => void;
  onOpenVertical?: (verticalId: string) => void;
} = {}): React.JSX.Element {
  const [employeeData, setEmployeeData] = useState<Row>({});
  const [firmData, setFirmData] = useState<Row>({});
  const [capabilities, setCapabilities] = useState<MissionDict>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const brand = await getObject('branding');
        const caps = asMissionDict(brand.capabilities);

        const employee = await getObject(
          'dashboard/employee',
          { period: 'month' },
        );

        let firm: Row = {};

        // Authorization is NOT invented in the frontend.
        // This flag originates from the backend BrandingView.
        if (caps.can_view_firm_operations === true) {
          firm = await getObject(
            'dashboard/executive',
            { period: 'month' },
          );
        }

        if (!active) return;

        setCapabilities(caps);
        setEmployeeData(employee);
        setFirmData(firm);
      } catch (caught: unknown) {
        if (!active) return;

        setError(
          caught instanceof Error
            ? caught.message
            : String(caught),
        );
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  if (loading) return <Loading />;

  const canViewFirmOperations =
    capabilities.can_view_firm_operations === true;

  // ----------------------------------------------------------
  // Row 1 — ALWAYS PERSONAL
  // ----------------------------------------------------------

  const myWork = asMissionDict(employeeData.my_work);
  const personalHealth = asMissionDict(employeeData.work_health);
  const myWorkload = asMissionDict(employeeData.workload);

  // ----------------------------------------------------------
  // Leadership sections use the existing canViewFirmOperations aggregation.
  // Staff remain entirely on employee-level Insight.
  // ----------------------------------------------------------

  const firmOverview = asMissionDict(firmData.overview);
  const firmHealth = asMissionDict(firmData.work_health);
  const firmOperations = asMissionDict(firmData.operations);
  const actionCentre = asMissionDict(firmData.action_centre);
  const employeeWorkload = asMissionDict(firmData.employee_workload);

  const verticalSummary = canViewFirmOperations
    ? (
        asMissionRows(
          firmData.vertical_summary,
        ) as VerticalSummaryRow[]
      )
    : [];

  const displayHealth = canViewFirmOperations
    ? firmHealth
    : personalHealth;

  const workDistribution = asMissionDict(
    canViewFirmOperations
      ? firmOperations.by_status
      : myWorkload.status_distribution,
  );

  const immediateActions = asMissionRows(
    displayHealth.immediate_actions,
  );

  const upcomingDeadlines = asMissionRows(
    canViewFirmOperations
      ? firmData.upcoming_deadlines
      : employeeData.upcoming_deadlines,
  );

  const recentActivity = asMissionRows(
    canViewFirmOperations
      ? firmData.recent_activity
      : employeeData.recent_activity,
  );

  const clientActivity = canViewFirmOperations
    ? asMissionRows(firmData.client_activity)
    : [];

  const team = canViewFirmOperations
    ? asMissionRows(employeeWorkload.rows)
    : [];

  const myAssigned = missionCount(myWork.assigned_open);
  const myDueToday = missionCount(myWork.due_today);
  const myOverdue = missionCount(myWork.overdue);
  const myWaitingClient = missionCount(myWork.waiting_for_client);

  const myReviewQa =
    missionCount(myWork.ready_for_review)
    + missionCount(myWork.rework_required)
    + missionCount(myWorkload.pending_reviews_assigned);

  const myCompleted = missionCount(myWork.recently_completed);

  const healthHealthy = missionCount(displayHealth.healthy);
  const healthAttention = missionCount(
    displayHealth.attention_required,
  );
  const healthHighRisk = missionCount(displayHealth.high_risk);
  const healthDueSoon = missionCount(displayHealth.due_soon);
  const healthWaitingClient = missionCount(
    displayHealth.waiting_on_client,
  );
  const healthWaitingReviewer = missionCount(
    displayHealth.waiting_on_reviewer,
  );

  const flowOrder = [
    'NOT_STARTED',
    'IN_PROGRESS',
    'WAITING_FOR_CLIENT',
    'READY_FOR_REVIEW',
    'REWORK_REQUIRED',
    'COMPLETED',
  ];

  const flowLabels: Record<string, string> = {
    NOT_STARTED: 'Ready',
    IN_PROGRESS: 'In Progress',
    WAITING_FOR_CLIENT: 'Waiting Client',
    READY_FOR_REVIEW: 'QA / Review',
    REWORK_REQUIRED: 'Rework',
    COMPLETED: 'Completed',
  };

  const clientHealth = asMissionDict(firmData.client_health);
  const clientRows = asMissionRows(clientHealth.rows);

  const clientsWaiting = canViewFirmOperations
    ? clientRows.filter(
      (row) => missionCount(row.pending_documents) > 0,
    ).length
    : 0;

  const clientsOverdue = canViewFirmOperations
    ? clientRows.filter(
      (row) => missionCount(row.overdue_work) > 0,
    ).length
    : 0;

  return (
    <div className="cx-mission-control">
      <ErrorBar error={error} />

      <section className="cx-mission-hero">
        <div>
          <span className="cx-panel-kicker">
            Operations Command Center
          </span>

          <h1>Mission Control</h1>

          <p>
            Everything requiring attention, in one operational view.
          </p>
        </div>

        <div className="cx-mission-hero-status">
          <strong>{healthHighRisk}</strong>
          <span>High Risk</span>
        </div>
      </section>

      {/* ====================================================
          ROW 1 — MY WORK TODAY
         ==================================================== */}

      <section className="cx-mission-panel cx-mission-today">
        <div className="cx-mission-section-head">
          <div>
            <span className="cx-panel-kicker">My Day</span>
            <h2>My Work Today</h2>
          </div>
        </div>

        <div className="cx-mission-today-grid">
          <div>
            <strong>{myAssigned}</strong>
            <span>Assigned / Open</span>
          </div>

          <div className={myDueToday > 0 ? 'watch' : ''}>
            <strong>{myDueToday}</strong>
            <span>Due Today</span>
          </div>

          <div className={myOverdue > 0 ? 'risk' : ''}>
            <strong>{myOverdue}</strong>
            <span>Overdue</span>
          </div>

          <div className={myWaitingClient > 0 ? 'watch' : ''}>
            <strong>{myWaitingClient}</strong>
            <span>Waiting for Client</span>
          </div>

          <div className={myReviewQa > 0 ? 'watch' : ''}>
            <strong>{myReviewQa}</strong>
            <span>Needs Review / QA</span>
          </div>

          <div>
            <strong>{myCompleted}</strong>
            <span>Completed This Period</span>
          </div>
        </div>
      </section>

      {/* ====================================================
          ROW 2 — IMMEDIATE ACTIONS
         ==================================================== */}

      <section className="cx-mission-panel cx-mission-actions-panel">
        <div className="cx-mission-section-head">
          <div>
            <span className="cx-panel-kicker">
              Highest Priority
            </span>
            <h2>Immediate Actions</h2>
          </div>

          <span className="cx-panel-count">
            {immediateActions.length}
          </span>
        </div>

        {immediateActions.length === 0 ? (
          <div className="cx-mission-empty">
            No immediate operational actions.
          </div>
        ) : (
          <div className="cx-mission-actions">
            {immediateActions.map((action) => {
              const id = String(
                action.work_item_id
                ?? action.id
                ?? action.title,
              );

              return (
                <button
                  type="button"
                  className="cx-mission-action-card"
                  key={id}
                  data-work-item-id={String(
                    action.work_item_id ?? '',
                  )}
                  data-testid={`mission-action-${id}`}
                  onClick={() => {
                    const workItemId = String(
                      action.work_item_id ?? '',
                    );

                    if (workItemId) {
                      onOpenWork?.(workItemId);
                    }
                  }}
                >
                  <div className="cx-mission-action-main">
                    <div>
                      <strong>
                        {String(action.title ?? 'Work item')}
                      </strong>

                      {action.client_name ? (
                        <span>
                          {String(action.client_name)}
                        </span>
                      ) : null}
                    </div>

                    <p>
                      {String(
                        action.next_action
                        ?? 'Continue work',
                      )}
                    </p>
                  </div>

                  <div className="cx-mission-action-state">
                    <Chip
                      value={String(action.health ?? 'GREEN')}
                      tone={
                        String(action.health) === 'RED'
                          ? 'danger'
                          : String(action.health) === 'AMBER'
                            ? 'warn'
                            : 'ok'
                      }
                    />

                    <small>
                      {String(
                        action.due_state
                        ?? action.current_controller
                        ?? '',
                      )}
                    </small>

                    {missionCount(action.waiting_days) > 0 ? (
                      <small>
                        Waiting {missionCount(action.waiting_days)}d
                      </small>
                    ) : null}
                  </div>
                  <span className="cx-mission-open-label">
                    Open
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <p className="cx-panel-footnote">
          Priority and next action come directly from Work Health.
        </p>
      </section>

      {/* ====================================================
          ROW 3 — OPERATIONAL HEALTH
         ==================================================== */}

      <section className="cx-mission-grid">
        <article className="cx-mission-panel">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">
                Work Health
              </span>
              <h2>Operational Health</h2>
            </div>
          </div>

          <div className="cx-mission-health-grid">
            <div>
              <strong>{healthHealthy}</strong>
              <span>Healthy</span>
            </div>

            <div className={
              healthAttention > 0 ? 'watch' : ''
            }>
              <strong>{healthAttention}</strong>
              <span>Attention</span>
            </div>

            <div className={
              healthHighRisk > 0 ? 'risk' : ''
            }>
              <strong>{healthHighRisk}</strong>
              <span>High Risk</span>
            </div>

            <div>
              <strong>{healthDueSoon}</strong>
              <span>Due Soon</span>
            </div>

            <div>
              <strong>{healthWaitingClient}</strong>
              <span>Client</span>
            </div>

            <div>
              <strong>{healthWaitingReviewer}</strong>
              <span>Reviewer</span>
            </div>
          </div>
        </article>

        <article className="cx-mission-panel">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">
                Work Flow
              </span>
              <h2>Work Distribution</h2>
            </div>
          </div>

          <div className="cx-mission-flow">
            {flowOrder.map((status) => (
              <div key={status}>
                <strong>
                  {missionCount(workDistribution[status])}
                </strong>

                <span>{flowLabels[status]}</span>
              </div>
            ))}

            <div className={
              healthHighRisk > 0 ? 'risk' : ''
            }>
              <strong>
                {missionCount(displayHealth.overdue)}
              </strong>
              <span>Overdue</span>
            </div>
          </div>

          <p className="cx-panel-footnote">
            Overdue is due intelligence, not a workflow status.
          </p>
        </article>
      </section>

      {canViewFirmOperations && verticalSummary.length > 0 ? (
        <>
          <section className="cx-mission-panel cx-vertical-operations-panel">
            <div className="cx-mission-section-head">
              <div>
                <span className="cx-panel-kicker">
                  Firm Operations
                </span>
                <h2>Vertical Operations</h2>
                <p className="cx-vertical-section-copy">
                  Current workload, risk and staffing across
                  every active vertical.
                </p>
              </div>

              <span className="cx-panel-count">
                {verticalSummary.length}
              </span>
            </div>

            <div className="cx-vertical-card-grid">
              {verticalSummary.map((vertical) => (
                <button
                  type="button"
                  className="cx-vertical-card"
                  key={vertical.vertical_id}
                  onClick={() =>
                    onOpenVertical?.(
                      vertical.vertical_id,
                    )
                  }
                >
                  <div className="cx-vertical-card-top">
                    <div>
                      

                      <h3>
                        {vertical.vertical_name}
                      </h3>
                    </div>

                    <span className="cx-vertical-open-pill">
                      {vertical.open_work} open
                    </span>
                  </div>

                  <div className="cx-vertical-card-metrics">
                    <div className="cx-vertical-primary">
                      <span>Overdue</span>
                      <strong>
                        {vertical.overdue}
                      </strong>
                    </div>

                    <div className="cx-vertical-primary">
                      <span>High Risk</span>
                      <strong>
                        {vertical.high_risk}
                      </strong>
                    </div>

                    <div className="cx-vertical-primary">
                      <span>Staff</span>
                      <strong>
                        {
                          vertical.assigned_staff_count
                        }
                      </strong>
                    </div>

                    <div>
                      <span>Due Soon</span>
                      <strong>
                        {vertical.due_soon}
                      </strong>
                    </div>

                    <div>
                      <span>Waiting on Client</span>
                      <strong>
                        {
                          vertical.waiting_on_client
                        }
                      </strong>
                    </div>

                    <div>
                      <span>Needs Review</span>
                      <strong>
                        {vertical.needs_review}
                      </strong>
                    </div>
                  </div>

                  <div className="cx-vertical-staff">
                    <span className="cx-vertical-staff-title">
                      Work by staff
                    </span>

                    {vertical.staff_workload.length > 0 ? (
                      <div className="cx-vertical-staff-list">
                        {vertical.staff_workload
                          .slice(0, 3)
                          .map((staff) => (
                            <span
                              key={
                                staff.employee_id
                              }
                            >
                              {
                                staff.employee_name
                              }{' '}
                              <strong>
                                {staff.open_work}
                              </strong>
                            </span>
                          ))}
                      </div>
                    ) : (
                      <span className="cx-vertical-no-staff">
                        No active assigned work
                      </span>
                    )}
                  </div>

                  <div className="cx-vertical-card-bottom">
                    <span>
                      {vertical.total_work} total
                      {' / '}
                      {vertical.completed_work} completed
                    </span>

                    <strong>View Work</strong>
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="cx-mission-panel cx-vertical-distribution-panel">
            <div className="cx-mission-section-head">
              <div>
                <span className="cx-panel-kicker">
                  Workload
                </span>
                <h2>Work Distribution by Vertical</h2>
                <p className="cx-vertical-section-copy">
                  Open work split across every active
                  vertical. Select any vertical to open its
                  Work view.
                </p>
              </div>
            </div>

            <VerticalDistributionDonut
              rows={verticalSummary}
              onOpenVertical={onOpenVertical}
            />
          </section>
        </>
      ) : null}

      {/* ====================================================
          ROW 4 — TEAM SNAPSHOT
         ==================================================== */}

      {canViewFirmOperations ? (
        <section className="cx-mission-panel">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">Team</span>
              <h2>Team Snapshot</h2>
            </div>

            <span className="cx-panel-count">
              {team.length}
            </span>
          </div>

          {team.length === 0 ? (
            <div className="cx-mission-empty">
              No active team workload.
            </div>
          ) : (
            <div className="cx-mission-team">
              {team.slice(0, 8).map((member) => (
                <div
                  className="cx-mission-team-row"
                  key={String(
                    member.employee_id
                    ?? member.employee_name,
                  )}
                >
                  <strong>
                    {String(
                      member.employee_name
                      ?? 'Employee',
                    )}
                  </strong>

                  <span>
                    {missionCount(member.open_work)} work
                  </span>

                  <span className={
                    missionCount(member.overdue) > 0
                      ? 'cx-number-danger'
                      : ''
                  }>
                    {missionCount(member.overdue)} overdue
                  </span>

                  <span>
                    {missionCount(
                      member.completed_in_period,
                    )} completed
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      ) : null}

      {/* ====================================================
          ROW 5 — CLIENT ACTIVITY
         ==================================================== */}

      {canViewFirmOperations ? (
        <section className="cx-mission-panel">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">
                Clients
              </span>
              <h2>Client Activity</h2>
            </div>
          </div>

          <div className="cx-mission-client-summary">
            <div>
              <strong>{clientsWaiting}</strong>
              <span>Clients Waiting</span>
            </div>

            <div>
              <strong>
                {missionCount(
                  firmOverview.recently_completed,
                )}
              </strong>
              <span>Recently Completed</span>
            </div>

            <div className={
              clientsOverdue > 0 ? 'risk' : ''
            }>
              <strong>{clientsOverdue}</strong>
              <span>Requiring Follow-up</span>
            </div>

            <div>
              <strong>{clientActivity.length}</strong>
              <span>Recent Client Movement</span>
            </div>
          </div>

          {clientActivity.length > 0 ? (
            <div className="cx-mission-client-events">
              {clientActivity.map((activity) => (
                <article
                  key={String(activity.id)}
                  className="cx-mission-client-event"
                >
                  <strong>
                    {String(
                      activity.client_name
                      ?? 'Client',
                    )}
                  </strong>

                  <p>
                    {String(activity.entry ?? 'Updated')}
                  </p>

                  <small>
                    {String(activity.title ?? 'Work item')}
                    {' · '}
                    {missionTime(activity.created_at)}
                  </small>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      {/* ====================================================
          ROW 6 + UPCOMING — TIMELINE / DEADLINES
         ==================================================== */}

      <section className="cx-mission-grid cx-mission-bottom-grid">
        <article className="cx-mission-panel">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">
                Latest Movement
              </span>
              <h2>Timeline</h2>
            </div>
          </div>

          {recentActivity.length === 0 ? (
            <div className="cx-mission-empty">
              No recent operational activity.
            </div>
          ) : (
            <div className="cx-activity-feed">
              {recentActivity.map((activity) => (
                <div
                  className="cx-activity-item"
                  key={String(activity.id)}
                >
                  <span className="cx-activity-dot" />

                  <div>
                    <strong>
                      {String(
                        activity.title
                        ?? 'Work item',
                      )}
                    </strong>

                    <p>
                      {String(
                        activity.entry
                        ?? 'Updated',
                      )}
                    </p>

                    {activity.client_name ? (
                      <small>
                        {String(activity.client_name)}
                      </small>
                    ) : null}
                  </div>

                  <time>
                    {missionTime(activity.created_at)}
                  </time>
                </div>
              ))}
            </div>
          )}
        </article>

        <aside className="cx-mission-panel cx-mission-upcoming">
          <div className="cx-mission-section-head">
            <div>
              <span className="cx-panel-kicker">
                Upcoming
              </span>
              <h2>Deadlines</h2>
            </div>
          </div>

          {upcomingDeadlines.length === 0 ? (
            <div className="cx-mission-empty">
              No upcoming dated work.
            </div>
          ) : (
            <div className="cx-mission-deadlines">
              {upcomingDeadlines.map((item) => (
                <button
                  type="button"
                  key={String(item.work_item_id)}
                  className="cx-mission-deadline"
                  data-work-item-id={String(
                    item.work_item_id ?? '',
                  )}
                  data-testid={`mission-deadline-${String(
                    item.work_item_id ?? '',
                  )}`}
                  onClick={() => {
                    const workItemId = String(
                      item.work_item_id ?? '',
                    );

                    if (workItemId) {
                      onOpenWork?.(workItemId);
                    }
                  }}
                >
                  <div>
                    <strong>
                      {String(
                        item.title
                        ?? 'Work item',
                      )}
                    </strong>

                    <small>
                      {String(item.client_name ?? '')}
                    </small>
                  </div>

                  <div>
                    <strong>
                      {String(item.due_date ?? '')}
                    </strong>

                    <small>
                      {missionCount(item.days_to_due) === 0
                        ? 'Today'
                        : `${missionCount(
                          item.days_to_due,
                        )} day(s)`}
                    </small>
                  </div>
                  <span className="cx-mission-open-label">
                    Open
                  </span>
                </button>
              ))}
            </div>
          )}
        </aside>
      </section>

      {/* Existing action-centre figures remain available to leadership
          without creating Phase 5.4 here. */}
      {canViewFirmOperations && (
        missionCount(actionCentre.unassigned) > 0
        || missionCount(actionCentre.review_backlog) > 0
      ) ? (
        <p className="cx-mission-footnote">
          {missionCount(actionCentre.unassigned)} unassigned
          {' · '}
          {missionCount(actionCentre.review_backlog)} review backlog
        </p>
      ) : null}
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
  initialCreateRequest = 0,
  onInitialCreateHandled,
  initialEditRow = null,
  onInitialEditHandled,
  onOpenRow,
}: {
  resource: string;
  title: string;
  columns: Column[];
  fields: Field[];
  blank: Row;
  filters?: { name: string; options: readonly string[] }[];
  drawerExtra?: (editing: Row) => React.ReactNode;
  initialCreateRequest?: number;
  onInitialCreateHandled?: () => void;
  initialEditRow?: Row | null;
  onInitialEditHandled?: () => void;
  onOpenRow?: (row: Row) => void;
}): React.JSX.Element {
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState('');
  const [filterVals, setFilterVals] = useState<Record<string, string>>({});
  const params: Record<string, string> = { search: applied, ...filterVals };
  const { rows, error, loading, reload } = useRows(resource, params);
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    if (!initialCreateRequest) return;

    // Reuse the exact existing Add {title} state.
    setEditing({ ...blank });
    setSaveError('');
    onInitialCreateHandled?.();
  }, [
    initialCreateRequest,
  ]);


  useEffect(() => {
    if (!initialEditRow) return;

    // Client Workspace returns to the same certified edit Drawer.
    setEditing({ ...initialEditRow });
    setSaveError('');
    onInitialEditHandled?.();
  }, [
    initialEditRow,
  ]);

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
      {loading ? (
        <Loading />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          onRow={(row) => {
            if (onOpenRow) {
              onOpenRow(row);
              return;
            }

            setEditing({ ...row });
            setSaveError('');
          }}
          empty={`No ${title.toLowerCase()} yet.`}
        />
      )}
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

  const [
    workItemToOpen,
    setWorkItemToOpen,
  ] = useState<string | null>(null);

  const [
    clientCreateRequest,
    setClientCreateRequest,
  ] = useState(0);


  const [
    clientToOpen,
    setClientToOpen,
  ] = useState<string | null>(null);

  const [
    clientEditRow,
    setClientEditRow,
  ] = useState<Row | null>(null);

  const [
    workQuickAction,
    setWorkQuickAction,
  ] = useState<
    'create' | 'documents' | null
  >(null);

  const [
    employeeOpsInitialSection,
    setEmployeeOpsInitialSection,
  ] = useState<'assignment' | null>(null);

  const [
    dashboardVerticalId,
    setDashboardVerticalId,
  ] = useState<string | null>(null);

  const openWorkItem = (workItemId: string): void => {
    if (!workItemId) return;

    setDashboardVerticalId(null);
    setWorkItemToOpen(workItemId);
    setArea('work');
  };

  const openVerticalWork = (
    verticalId: string,
  ): void => {
    if (!verticalId) return;

    setWorkItemToOpen(null);
    setWorkQuickAction(null);
    setDashboardVerticalId(verticalId);
    setArea('work');
  };


  const openClient = (clientId: string): void => {
    if (!clientId) return;

    setClientEditRow(null);
    setClientToOpen(clientId);
    setArea('clients');
  };

  const launchQuickCreate = (
    action: QuickCreateAction,
  ): void => {
    if (action === 'NEW_CLIENT') {
      setClientToOpen(null);
      setClientEditRow(null);

      setClientCreateRequest(
        (current) => current + 1,
      );
      setArea('clients');
      return;
    }

    if (action === 'NEW_WORK') {
      setWorkQuickAction('create');
      setArea('work');
      return;
    }

    if (action === 'ASSIGN_WORK') {
      setEmployeeOpsInitialSection('assignment');
      setArea('employee-ops');
      return;
    }

    setWorkQuickAction('documents');
    setArea('work');
  };

  const { identity } = useIdentity();
  const brand = useBrand();
  const view = ((): React.JSX.Element => {
    switch (area) {
      case 'dashboard':
        return (
          <Dashboard
            onOpenWork={openWorkItem}
            onOpenVertical={openVerticalWork}
          />
        );

      case 'action-centre':
        return (
          <ActionCentre
            onOpenWork={openWorkItem}
          />
        );
case 'my-dashboard':
        return <EmployeeDashboard onDrill={(f) => { setArea('work'); void f; }} />;
      case 'firm-overview':
        return <ExecutiveDashboard onDrill={(f) => { setArea('work'); void f; }} />;
      case 'audit':
        return <AuditViewer />;
      case 'identity':
        return isProviderAdmin(identity) ? <IdentityAccessAdministration /> : <div className="cx-warning">Administrator access is required.</div>;
      case 'clients':
        if (clientToOpen) {
          return (
            <ClientWorkspace
              clientId={clientToOpen}
              onBack={() => {
                setClientToOpen(null);
              }}
              onEditClient={(client) => {
                setClientToOpen(null);
                setClientEditRow(client);
              }}
              onOpenWork={openWorkItem}
            />
          );
        }

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
            initialCreateRequest={
              clientCreateRequest
            }
            onInitialCreateHandled={() => {
              setClientCreateRequest(0);
            }}
            initialEditRow={clientEditRow}
            onInitialEditHandled={() => {
              setClientEditRow(null);
            }}
            onOpenRow={(client) => {
              openClient(String(client.id));
            }}
          />
        );
      case 'work':
        return (
          <WorkArea
            initialVerticalId={
              dashboardVerticalId ?? undefined
            }
            initialWorkItemId={
              workItemToOpen ?? undefined
            }
            onInitialWorkOpened={() => {
              setWorkItemToOpen(null);
            }}
            initialQuickAction={
              workQuickAction ?? undefined
            }
            onInitialQuickActionHandled={() => {
              setWorkQuickAction(null);
            }}
          />
        );
      case 'servicing':
        return <ServicingArea />;
      case 'employee-ops':
        return (
          <EmployeeOpsArea
            initialSection={
              employeeOpsInitialSection ?? undefined
            }
            onInitialSectionHandled={() => {
              setEmployeeOpsInitialSection(null);
            }}
          />
        );
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
            <button
              key={n.key}
              className={n.key === area ? 'active' : ''}
              onClick={() => {
                if (n.key === 'clients') {
                  setClientToOpen(null);
                }

                setArea(n.key);
              }}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className="cx-side-foot">One firm - operational build</div>
      </aside>
      <div className="cx-main">
        <header className="cx-top">
          <h2>{NAV.find((n) => n.key === area)?.label}</h2>
          <PageHelp page={area} />
          <GlobalSearch
            onNavigate={(target, id, workItemId) => {
              if (target === 'clients' && id) {
                openClient(id);
                return;
              }

              if (target === 'work' && id) {
                openWorkItem(id);
                return;
              }

              if (target === 'documents') {
                if (workItemId) {
                  openWorkItem(workItemId);
                  return;
                }

                setWorkQuickAction('documents');
                setArea('work');
                return;
              }

              if (
                target === 'team'
                || target === 'services'
              ) {
                setArea(target);
              }
            }}
          />
          <QuickCreateMenu
            canAssign={
              brand.capabilities?.is_executive === true
              || String(
                brand.capabilities?.role ?? '',
              ) === 'MANAGER'
            }
            onSelect={launchQuickCreate}
          />
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
