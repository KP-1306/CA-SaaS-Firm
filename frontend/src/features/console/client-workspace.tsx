import type * as React from 'react';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  getObject,
  list,
} from './api';

import type {
  Row,
} from './types';

import {
  Chip,
  ErrorBar,
  Loading,
} from './ui';

import {
  label,
} from './types';

import './client-workspace.css';


type ClientWorkspaceProjection = Row & {
  work_health?: Row;
  recent_activity?: Row[];
  history?: Row[];
  upcoming_deadlines?: Row[];
};


function count(value: unknown): number {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}


function displayDate(value: unknown): string {
  const text = String(value ?? '');
  return text ? text.slice(0, 10) : '-';
}


function displayTime(value: unknown): string {
  const text = String(value ?? '');

  if (!text) return '';

  return text
    .slice(0, 16)
    .replace('T', ' ');
}


function isOpenWork(row: Row): boolean {
  return (
    row.status !== 'COMPLETED'
    && row.status !== 'CANCELLED'
  );
}


function isPendingDocument(row: Row): boolean {
  return (
    row.status !== 'ACCEPTED'
    && row.status !== 'WAIVED'
  );
}


export function ClientWorkspace({
  clientId,
  onBack,
  onEditClient,
  onOpenWork,
}: {
  clientId: string;
  onBack: () => void;
  onEditClient: (client: Row) => void;
  onOpenWork: (workItemId: string) => void;
}): React.JSX.Element {
  const [client, setClient] = useState<Row | null>(null);
  const [work, setWork] = useState<Row[]>([]);
  const [documents, setDocuments] = useState<Row[]>([]);
  const [contacts, setContacts] = useState<Row[]>([]);
  const [projection, setProjection] =
    useState<ClientWorkspaceProjection>({});

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async (): Promise<void> => {
      setLoading(true);
      setError('');

      try {
        const [
          clientRow,
          workRows,
          documentRows,
          contactRows,
          operational,
        ] = await Promise.all([
          getObject(`clients/${clientId}`),
          list('work-items', {
            client_id: clientId,
          }),
          list('document-requests', {
            client_id: clientId,
          }),
          list('client-contacts', {
            client_id: clientId,
          }),
          getObject('client-workspace', {
            client_id: clientId,
          }),
        ]);

        if (!active) return;

        setClient(clientRow);
        setWork(workRows);
        setDocuments(documentRows);
        setContacts(contactRows);
        setProjection(
          operational as ClientWorkspaceProjection,
        );
      } catch (reason: unknown) {
        if (!active) return;

        setError(
          String(
            reason instanceof Error
              ? reason.message
              : reason,
          ),
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, [
    clientId,
  ]);

  const activeWork = useMemo(
    () => work.filter(isOpenWork),
    [work],
  );

  const overdueWork = useMemo(
    () => activeWork.filter(
      (row) => row.is_overdue === true,
    ),
    [activeWork],
  );

  const pendingDocuments = useMemo(
    () => documents.filter(isPendingDocument),
    [documents],
  );

  const assignedEmployees = useMemo(() => {
    const people = new Map<
      string,
      {
        id: string;
        name: string;
        roles: Set<string>;
      }
    >();

    for (const item of activeWork) {
      const ownerId = String(
        item.owner_user_id ?? '',
      );

      const ownerName = String(
        item.owner_name ?? '',
      );

      if (ownerId && ownerName) {
        const current = people.get(ownerId) ?? {
          id: ownerId,
          name: ownerName,
          roles: new Set<string>(),
        };

        current.roles.add('Owner');
        people.set(ownerId, current);
      }

      const reviewerId = String(
        item.reviewer_user_id ?? '',
      );

      const reviewerName = String(
        item.reviewer_name ?? '',
      );

      if (reviewerId && reviewerName) {
        const current = people.get(reviewerId) ?? {
          id: reviewerId,
          name: reviewerName,
          roles: new Set<string>(),
        };

        current.roles.add('Reviewer');
        people.set(reviewerId, current);
      }
    }

    return [...people.values()];
  }, [
    activeWork,
  ]);

  const health = (
    projection.work_health ?? {}
  ) as Row;

  const recentActivity = Array.isArray(
    projection.recent_activity,
  )
    ? projection.recent_activity
    : [];

  const history = Array.isArray(
    projection.history,
  )
    ? projection.history
    : [];

  const upcoming = Array.isArray(
    projection.upcoming_deadlines,
  )
    ? projection.upcoming_deadlines
    : [];

  if (loading) {
    return <Loading />;
  }

  if (error) {
    return (
      <div className="cx-client-workspace">
        <button
          type="button"
          className="cx-btn subtle"
          onClick={onBack}
        >
          Back to Clients
        </button>

        <ErrorBar error={error} />
      </div>
    );
  }

  if (!client) {
    return (
      <div className="cx-client-workspace">
        <button
          type="button"
          className="cx-btn subtle"
          onClick={onBack}
        >
          Back to Clients
        </button>

        <div className="cx-empty">
          Client was not found.
        </div>
      </div>
    );
  }

  const clientName = String(
    client.trade_name
    || client.legal_name
    || 'Client',
  );

  return (
    <div className="cx-client-workspace">
      <section className="cx-client-workspace-head">
        <div className="cx-client-workspace-head-main">
          <button
            type="button"
            className="cx-btn subtle"
            onClick={onBack}
          >
            ← Clients
          </button>

          <div>
            <span className="cx-client-workspace-kicker">
              Client Workspace
            </span>

            <h1>{clientName}</h1>

            {client.trade_name && client.legal_name ? (
              <p>{String(client.legal_name)}</p>
            ) : null}
          </div>
        </div>

        <div className="cx-client-workspace-head-actions">
          <Chip
            value={String(
              client.engagement_status ?? 'ACTIVE',
            )}
          />

          <button
            type="button"
            className="cx-btn"
            onClick={() => onEditClient(client)}
          >
            Edit Client
          </button>
        </div>
      </section>

      <section className="cx-client-identity-grid">
        <div>
          <span>Type</span>
          <strong>
            {label(String(client.client_type ?? ''))}
          </strong>
        </div>

        <div>
          <span>PAN</span>
          <strong>{String(client.pan || '-')}</strong>
        </div>

        <div>
          <span>TAN</span>
          <strong>{String(client.tan || '-')}</strong>
        </div>

        <div>
          <span>Lifecycle</span>
          <strong>
            {label(String(
              client.lifecycle_status ?? 'PROSPECT',
            ))}
          </strong>
        </div>
      </section>

      <section className="cx-client-metrics">
        <div>
          <strong>{activeWork.length}</strong>
          <span>Active Work</span>
        </div>

        <div>
          <strong>{overdueWork.length}</strong>
          <span>Overdue</span>
        </div>

        <div>
          <strong>{pendingDocuments.length}</strong>
          <span>Pending Documents</span>
        </div>

        <div>
          <strong>{upcoming.length}</strong>
          <span>Upcoming Obligations</span>
        </div>
      </section>

      <div className="cx-client-workspace-grid">
        <section className="cx-client-section cx-client-section-wide">
          <div className="cx-client-section-head">
            <div>
              <span>Operations</span>
              <h2>Active Work</h2>
            </div>

            <strong>{activeWork.length}</strong>
          </div>

          {activeWork.length === 0 ? (
            <div className="cx-empty">
              No active work for this client.
            </div>
          ) : (
            <div className="cx-client-work-list">
              {activeWork.map((item) => (
                <button
                  type="button"
                  className="cx-client-work-row"
                  key={String(item.id)}
                  onClick={() =>
                    onOpenWork(String(item.id))
                  }
                >
                  <div>
                    <strong>
                      {String(item.title || 'Work Item')}
                    </strong>

                    <span>
                      {String(item.service_name || '')}
                    </span>
                  </div>

                  <div>
                    <span>
                      {item.due_date
                        ? `Due ${displayDate(item.due_date)}`
                        : 'No due date'}
                    </span>

                    <Chip
                      value={String(
                        item.status ?? 'NOT_STARTED',
                      )}
                    />
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Work Health</span>
              <h2>Operational Health</h2>
            </div>
          </div>

          <div className="cx-client-health-grid">
            <div>
              <strong>{count(health.healthy)}</strong>
              <span>Healthy</span>
            </div>

            <div>
              <strong>
                {count(health.attention_required)}
              </strong>
              <span>Attention</span>
            </div>

            <div>
              <strong>{count(health.high_risk)}</strong>
              <span>High Risk</span>
            </div>

            <div>
              <strong>{count(health.due_soon)}</strong>
              <span>Due Soon</span>
            </div>

            <div>
              <strong>
                {count(health.waiting_on_client)}
              </strong>
              <span>Waiting Client</span>
            </div>

            <div>
              <strong>
                {count(health.waiting_on_reviewer)}
              </strong>
              <span>Reviewer</span>
            </div>
          </div>
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Documents</span>
              <h2>Pending Documents</h2>
            </div>

            <strong>{pendingDocuments.length}</strong>
          </div>

          {pendingDocuments.length === 0 ? (
            <div className="cx-empty">
              No pending client documents.
            </div>
          ) : (
            <div className="cx-client-simple-list">
              {pendingDocuments.map((document) => (
                <div key={String(document.id)}>
                  <div>
                    <strong>
                      {String(
                        document.name || 'Document',
                      )}
                    </strong>

                    <span>
                      {String(
                        document.work_item_title
                        || document.category
                        || '',
                      )}
                    </span>
                  </div>

                  <Chip
                    value={String(
                      document.status ?? 'REQUESTED',
                    )}
                  />
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Deadlines</span>
              <h2>Upcoming Obligations</h2>
            </div>
          </div>

          {upcoming.length === 0 ? (
            <div className="cx-empty">
              No upcoming dated work.
            </div>
          ) : (
            <div className="cx-client-simple-list">
              {upcoming.map((item) => (
                <button
                  type="button"
                  key={String(item.work_item_id)}
                  onClick={() =>
                    onOpenWork(
                      String(item.work_item_id),
                    )
                  }
                >
                  <div>
                    <strong>
                      {String(item.title || 'Work Item')}
                    </strong>

                    <span>
                      {String(item.next_action || '')}
                    </span>
                  </div>

                  <span>
                    {displayDate(item.due_date)}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>People</span>
              <h2>Contacts</h2>
            </div>
          </div>

          {contacts.length === 0 ? (
            <div className="cx-empty">
              No contacts have been added.
            </div>
          ) : (
            <div className="cx-client-simple-list">
              {contacts.map((contact) => (
                <div key={String(contact.id)}>
                  <div>
                    <strong>
                      {String(
                        contact.name || 'Contact',
                      )}
                    </strong>

                    <span>
                      {String(
                        contact.designation
                        || contact.email
                        || contact.mobile
                        || '',
                      )}
                    </span>
                  </div>

                  {contact.is_primary ? (
                    <Chip value="PRIMARY" tone="ok" />
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Responsibility</span>
              <h2>Assigned Employees</h2>
            </div>
          </div>

          {assignedEmployees.length === 0 ? (
            <div className="cx-empty">
              No employees assigned to active work.
            </div>
          ) : (
            <div className="cx-client-simple-list">
              {assignedEmployees.map((employee) => (
                <div key={employee.id}>
                  <div>
                    <strong>{employee.name}</strong>
                    <span>
                      {[...employee.roles].join(' · ')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Latest Movement</span>
              <h2>Recent Activity</h2>
            </div>
          </div>

          {recentActivity.length === 0 ? (
            <div className="cx-empty">
              No recent operational activity.
            </div>
          ) : (
            <div className="cx-client-timeline">
              {recentActivity.map((activity) => (
                <div key={String(activity.id)}>
                  <time>
                    {displayTime(activity.created_at)}
                  </time>

                  <div>
                    <strong>
                      {String(
                        activity.title || 'Work Item',
                      )}
                    </strong>

                    <span>
                      {String(activity.entry || '')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="cx-client-section">
          <div className="cx-client-section-head">
            <div>
              <span>Record</span>
              <h2>History</h2>
            </div>

            <strong>{history.length}</strong>
          </div>

          {history.length === 0 ? (
            <div className="cx-empty">
              No work history recorded for this client.
            </div>
          ) : (
            <div className="cx-client-timeline">
              {history.map((activity) => (
                <div key={String(activity.id)}>
                  <time>
                    {displayTime(activity.created_at)}
                  </time>

                  <div>
                    <strong>
                      {String(
                        activity.title || 'Work Item',
                      )}
                    </strong>

                    <span>
                      {String(activity.entry || '')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
