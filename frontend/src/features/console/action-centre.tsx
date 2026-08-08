import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';

import { getObject } from './api';
import type { Row } from './types';
import { ErrorBar, Loading } from './ui';

import './action-centre.css';

type Dict = Record<string, unknown>;

type ActionFilter =
  | 'ALL'
  | 'OVERDUE'
  | 'CLIENT'
  | 'REVIEW'
  | 'REWORK';

function asDict(value: unknown): Dict {
  if (
    value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
  ) {
    return value as Dict;
  }

  return {};
}

function asRows(value: unknown): Row[] {
  return Array.isArray(value) ? value as Row[] : [];
}

function count(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dueLabel(row: Row): string {
  const state = String(row.due_state ?? '');
  const rawDays = Number(row.days_to_due);

  if (state === 'OVERDUE') {
    if (Number.isFinite(rawDays)) {
      const days = Math.abs(rawDays);
      return `${days} day${days === 1 ? '' : 's'} overdue`;
    }

    return 'Overdue';
  }

  if (state === 'DUE_SOON') {
    if (rawDays === 0) return 'Due today';

    if (Number.isFinite(rawDays)) {
      return `Due in ${rawDays} day${rawDays === 1 ? '' : 's'}`;
    }

    return 'Due soon';
  }

  return '';
}

function matches(row: Row, filter: ActionFilter): boolean {
  if (filter === 'ALL') return true;

  if (filter === 'OVERDUE') {
    return row.due_state === 'OVERDUE';
  }

  if (filter === 'CLIENT') {
    return row.current_controller === 'CLIENT';
  }

  if (filter === 'REVIEW') {
    return (
      row.current_controller === 'REVIEWER'
      || row.status === 'READY_FOR_REVIEW'
    );
  }

  return row.status === 'REWORK_REQUIRED';
}

export function ActionCentre({
  onOpenWork,
}: {
  onOpenWork: (workItemId: string) => void;
}): React.JSX.Element {
  const [employeeData, setEmployeeData] = useState<Row>({});
  const [firmData, setFirmData] = useState<Row>({});
  const [canViewFirm, setCanViewFirm] = useState(false);
  const [filter, setFilter] = useState<ActionFilter>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const branding = await getObject('branding');
        const capabilities = asDict(branding.capabilities);

        const employee = await getObject(
          'dashboard/employee',
          { period: 'month' },
        );

        const firmAllowed =
          capabilities.can_view_firm_operations === true;

        let firm: Row = {};

        if (firmAllowed) {
          firm = await getObject(
            'dashboard/executive',
            { period: 'month' },
          );
        }

        if (!active) return;

        setEmployeeData(employee);
        setFirmData(firm);
        setCanViewFirm(firmAllowed);
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

  const employeeHealth = asDict(employeeData.work_health);
  const firmHealth = asDict(firmData.work_health);

  // Work Health remains authoritative for ordering and urgency.
  const sourceHealth = canViewFirm
    ? firmHealth
    : employeeHealth;

  const actions = asRows(sourceHealth.immediate_actions);

  const visibleActions = useMemo(
    () => actions.filter((row) => matches(row, filter)),
    [actions, filter],
  );

  const executiveActions = asDict(firmData.action_centre);

  const filters: Array<{
    key: ActionFilter;
    label: string;
    count: number;
  }> = [
    {
      key: 'ALL',
      label: 'All Actions',
      count: actions.length,
    },
    {
      key: 'OVERDUE',
      label: 'Overdue',
      count: count(sourceHealth.overdue),
    },
    {
      key: 'CLIENT',
      label: 'Client Follow-up',
      count: count(sourceHealth.waiting_on_client),
    },
    {
      key: 'REVIEW',
      label: 'Review / QA',
      count: count(sourceHealth.waiting_on_reviewer),
    },
    {
      key: 'REWORK',
      label: 'Rework',
      count: canViewFirm
        ? count(executiveActions.rework_required)
        : actions.filter(
            (row) => row.status === 'REWORK_REQUIRED',
          ).length,
    },
  ];

  if (loading) return <Loading />;

  return (
    <div className="cx-action-centre">
      <header className="cx-action-centre-head">
        <div>
          <span className="cx-panel-kicker">
            Operational inbox
          </span>
          <h1>Action Centre</h1>
          <p>Only work that needs attention now.</p>
        </div>

        <span className="cx-action-scope">
          {canViewFirm
            ? 'Firm operational view'
            : 'My operational view'}
        </span>
      </header>

      <ErrorBar error={error} />

      <nav
        className="cx-action-filter"
        aria-label="Action Centre filters"
      >
        {filters.map((item) => (
          <button
            key={item.key}
            type="button"
            className={filter === item.key ? 'active' : ''}
            onClick={() => setFilter(item.key)}
          >
            <span>{item.label}</span>
            <strong>{item.count}</strong>
          </button>
        ))}
      </nav>

      {visibleActions.length === 0 ? (
        <section className="cx-action-empty">
          <strong>Nothing requires action here.</strong>
          <span>
            Actionable work will appear from existing
            operational intelligence.
          </span>
        </section>
      ) : (
        <section
          className="cx-action-list"
          aria-label="Actionable work"
        >
          {visibleActions.map((row) => {
            const id = String(
              row.work_item_id ?? row.id ?? '',
            );

            const due = dueLabel(row);
            const waitingDays = count(row.waiting_days);

            return (
              <article
                key={id}
                className="cx-action-row"
              >
                <div className="cx-action-main">
                  <div className="cx-action-title">
                    <strong>
                      {String(row.title ?? 'Work item')}
                    </strong>

                    {row.risk === 'HIGH' ? (
                      <span className="danger">
                        High risk
                      </span>
                    ) : null}

                    {row.due_state === 'OVERDUE' ? (
                      <span className="danger">
                        Overdue
                      </span>
                    ) : null}
                  </div>

                  <div className="cx-action-context">
                    {due ? <span>{due}</span> : null}

                    {row.current_controller ? (
                      <span>
                        Controller: {
                          String(row.current_controller)
                        }
                      </span>
                    ) : null}

                    {waitingDays > 0 ? (
                      <span>
                        Waiting {waitingDays} day{
                          waitingDays === 1 ? '' : 's'
                        }
                      </span>
                    ) : null}
                  </div>

                  <div className="cx-action-next">
                    <span>Next action</span>
                    <strong>
                      {String(
                        row.next_action ?? 'Open work',
                      )}
                    </strong>
                  </div>
                </div>

                <button
                  type="button"
                  className="cx-btn"
                  onClick={() => {
                    if (id) onOpenWork(id);
                  }}
                >
                  Open
                </button>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}
