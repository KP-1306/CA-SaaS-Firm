import { useEffect, useState } from 'react';
import type * as React from 'react';

import { collectionAct } from './api';
import type { Row } from './types';
import { ErrorBar, Loading } from './ui';

type Props = {
  workItem: Row;
  employees: Row[];
  onAssigned: (result: Row) => void;
};

export function AssignmentWorkspace({
  workItem,
  employees,
  onAssigned,
}: Props): React.JSX.Element {
  const [candidates, setCandidates] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [executingId, setExecutingId] = useState('');
  const [error, setError] = useState('');
  const [explanation, setExplanation] = useState<Row | null>(null);

  const workItemId = String(workItem.id ?? '');

  useEffect(() => {
    setCandidates([]);
    setExplanation(null);
    setError('');
  }, [workItemId]);

  const employeeName = (candidate: Row): string => {
    if (candidate.name) return String(candidate.name);

    const id = String(candidate.employee_id ?? '');

    return String(
      employees.find(
        (employee) => String(employee.id) === id,
      )?.name ?? id,
    );
  };

  const recommend = (): void => {
    if (!workItemId) return;

    setLoading(true);
    setError('');
    setCandidates([]);

    void collectionAct(
      'assignment-recommendations',
      'recommend',
      {
        work_item_id: workItemId,
        service_id: workItem.service_id || undefined,
        estimated_hours: workItem.estimated_hours || undefined,
      },
    )
      .then((response) => {
        const rows =
          Array.isArray((response as Row).candidates)
            ? ((response as Row).candidates as Row[])
            : [];

        setCandidates(rows);
      })
      .catch((reason: unknown) => {
        setError(
          String(
            reason instanceof Error
              ? reason.message
              : reason,
          ),
        );
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const execute = (
    candidate: Row,
    index: number,
  ): void => {
    if (!workItemId || candidate.eligible !== true) return;

    const isOverride = index !== 0;

    let overrideReason = '';

    if (isOverride) {
      overrideReason =
        window.prompt(
          'Why are you overriding the top recommendation?',
        )?.trim() ?? '';

      if (!overrideReason) return;
    }

    const employeeId = String(
      candidate.employee_id ?? '',
    );

    const body: Row = {
      work_item_id: workItemId,
      owner_user_id: employeeId,
      reviewer_user_id:
        workItem.reviewer_user_id || undefined,
      was_override: isOverride,
      recommended_owner_user_id:
        candidates[0]?.employee_id || undefined,
      explanation:
        candidate.score_breakdown ?? {},
    };

    if (isOverride) {
      body.override_reason = overrideReason;
    }

    setExecutingId(employeeId);
    setError('');

    void collectionAct(
      'assignment-recommendations',
      'execute',
      body,
    )
      .then((response) => {
        setCandidates([]);
        setExplanation(null);
        onAssigned(response as Row);
      })
      .catch((reason: unknown) => {
        setError(
          String(
            reason instanceof Error
              ? reason.message
              : reason,
          ),
        );
      })
      .finally(() => {
        setExecutingId('');
      });
  };

  return (
    <div>
      <div className="cx-panel">
        <div>
          <strong>Assignment recommendation</strong>
          <div className="cx-muted">
            Recommendations are ranked by the existing assignment engine.
            Nothing is assigned until you approve a candidate.
          </div>
        </div>

        <button
          type="button"
          className="cx-btn"
          disabled={
            loading ||
            String(workItem.status) === 'COMPLETED' ||
            String(workItem.status) === 'CANCELLED'
          }
          onClick={recommend}
        >
          {loading ? 'Computing...' : 'Get recommendations'}
        </button>
      </div>

      <ErrorBar error={error} />

      {loading ? <Loading /> : null}

      {!loading && candidates.length === 0 ? (
        <div className="cx-muted">
          No recommendations computed yet.
        </div>
      ) : null}

      {candidates.length > 0 ? (
        <table className="cx-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Employee</th>
              <th>Eligible</th>
              <th>Score</th>
              <th>Open work</th>
              <th>Available h</th>
              <th>Reason</th>
              <th />
            </tr>
          </thead>

          <tbody>
            {candidates.map((candidate, index) => {
              const employeeId =
                String(candidate.employee_id ?? '');

              return (
                <tr key={employeeId}>
                  <td>{index + 1}</td>

                  <td>
                    {employeeName(candidate)}
                  </td>

                  <td>
                    {candidate.eligible === true
                      ? 'Yes'
                      : 'No'}
                  </td>

                  <td>
                    {String(candidate.score ?? 0)}
                  </td>

                  <td>
                    {String(
                      candidate.open_workload ?? 0,
                    )}
                  </td>

                  <td>
                    {String(
                      candidate.available_hours ?? 0,
                    )}
                  </td>

                  <td>
                    <button
                      type="button"
                      className="cx-btn subtle"
                      onClick={() =>
                        setExplanation(candidate)
                      }
                    >
                      Why?
                    </button>
                  </td>

                  <td>
                    <button
                      type="button"
                      className="cx-btn"
                      disabled={
                        candidate.eligible !== true ||
                        Boolean(executingId)
                      }
                      onClick={() =>
                        execute(candidate, index)
                      }
                    >
                      {executingId === employeeId
                        ? 'Assigning...'
                        : index === 0
                          ? 'Assign'
                          : 'Override & assign'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}

      {explanation ? (
        <div
          className="cx-drawer-backdrop"
          onClick={() => setExplanation(null)}
        >
          <div
            className="cx-drawer"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <h3>
              Why {employeeName(explanation)}?
            </h3>

            {Array.isArray(
              explanation.eligibility_reasons,
            ) ? (
              <div>
                <strong>Eligibility</strong>
                <ul>
                  {(
                    explanation.eligibility_reasons as unknown[]
                  ).map((reason) => (
                    <li key={String(reason)}>
                      {String(reason)}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <strong>Score breakdown</strong>
            <pre>
              {JSON.stringify(
                explanation.score_breakdown ?? {},
                null,
                2,
              )}
            </pre>

            <button
              type="button"
              className="cx-btn"
              onClick={() =>
                setExplanation(null)
              }
            >
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}