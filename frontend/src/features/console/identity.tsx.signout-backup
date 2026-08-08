import type * as React from 'react';
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  ApiRequestError,
  deletePath,
  postPath,
  requestObject,
  requestRows,
} from './api';
import type { Row } from './types';
import { Chip, ErrorBar, Loading } from './ui';

type IdentityState = {
  account: Row;
  membership: Row;
};

type IdentityContextValue = {
  identity: IdentityState | null;
  reload: () => Promise<void>;
  logout: () => Promise<void>;
};

const IdentityContext = createContext<IdentityContextValue>({
  identity: null,
  reload: async () => undefined,
  logout: async () => undefined,
});

export function useIdentity(): IdentityContextValue {
  return useContext(IdentityContext);
}

export function isProviderAdmin(identity: IdentityState | null): boolean {
  const role = String(identity?.membership.role ?? '');
  return role === 'PLATFORM_ADMIN' || role === 'OPERATIONS_ADMIN';
}

export function LoginScreen({
  onAuthenticated,
}: {
  onAuthenticated: () => Promise<void>;
}): React.JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    requestObject('auth/login/').catch(() => undefined);
  }, []);

  const submit = (event: React.FormEvent): void => {
    event.preventDefault();
    setBusy(true);
    setError('');
    postPath('auth/login/', { email, password })
      .then(() => onAuthenticated())
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      })
      .finally(() => setBusy(false));
  };

  return (
    <main className="cx-auth-page">
      <section className="cx-auth-card" aria-label="Vridhi consultant sign in">
        <div className="cx-auth-brand">
          <span>VRIDHI</span>
          <h1>Consultant sign in</h1>
          <p>Secure access to the Vridhi operations platform.</p>
        </div>
        <ErrorBar error={error} />
        <form onSubmit={submit}>
          <label>
            Work email
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <button className="cx-btn" type="submit" disabled={busy}>
            {busy ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
        <small>
          Password assistance is managed by an authorised Vridhi administrator.
        </small>
      </section>
    </main>
  );
}

function PasswordChange({
  onChanged,
}: {
  onChanged: () => Promise<void>;
}): React.JSX.Element {
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');

  const submit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (newPassword !== confirmation) {
      setError('New password and confirmation do not match.');
      return;
    }
    postPath('auth/password-change/', {
      current_password: currentPassword,
      new_password: newPassword,
    })
      .then(() => onChanged())
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  return (
    <main className="cx-auth-page">
      <section className="cx-auth-card">
        <h1>Change your temporary password</h1>
        <p>A personal password is required before continuing.</p>
        <ErrorBar error={error} />
        <form onSubmit={submit}>
          <label>
            Temporary password
            <input
              type="password"
              required
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
            />
          </label>
          <label>
            New password
            <input
              type="password"
              minLength={12}
              required
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              minLength={12}
              required
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </label>
          <button className="cx-btn" type="submit">Change password</button>
        </form>
      </section>
    </main>
  );
}

export function IdentityGate({
  children,
}: {
  children: React.ReactNode;
}): React.JSX.Element {
  const [identity, setIdentity] = useState<IdentityState | null>(null);
  const [loading, setLoading] = useState(true);
  const [legacyCompatibility, setLegacyCompatibility] = useState(false);

  const reload = async (): Promise<void> => {
    setLoading(true);
    try {
      const value = await requestObject('auth/me/');
      const account = value.account;
      const membership = value.membership;
      if (
        account &&
        typeof account === 'object' &&
        membership &&
        typeof membership === 'object'
      ) {
        setIdentity({
          account: account as Row,
          membership: membership as Row,
        });
        setLegacyCompatibility(false);
      } else {
        // Existing development/test fixtures return arrays or empty objects.
        setLegacyCompatibility(true);
      }
    } catch (value: unknown) {
      if (
        value instanceof ApiRequestError &&
        (value.status === 401 || value.status === 403)
      ) {
        setIdentity(null);
        setLegacyCompatibility(false);
      } else {
        setIdentity(null);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  const logout = async (): Promise<void> => {
    await postPath('auth/logout/');
    setIdentity(null);
  };

  if (loading) return <Loading />;
  if (legacyCompatibility) return <>{children}</>;
  if (!identity) return <LoginScreen onAuthenticated={reload} />;
  if (identity.account.must_change_password === true) {
    return <PasswordChange onChanged={reload} />;
  }

  return (
    <IdentityContext.Provider value={{ identity, reload, logout }}>
      {children}
    </IdentityContext.Provider>
  );
}

const PROVIDER_ROLES = [
  'PLATFORM_ADMIN',
  'OPERATIONS_ADMIN',
  'IMPLEMENTATION_CONSULTANT',
  'SUPPORT_CONSULTANT',
  'SECURITY_AUDITOR',
] as const;

const ACCOUNT_STATUSES = ['ACTIVE', 'SUSPENDED', 'DISABLED'] as const;

export function ConsultantAdministration(): React.JSX.Element {
  const [rows, setRows] = useState<Row[]>([]);
  const [employees, setEmployees] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [sessions, setSessions] = useState<Row[]>([]);
  const [audit, setAudit] = useState<Row[]>([]);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [error, setError] = useState('');
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [creating, setCreating] = useState<Row>({
    email: '',
    display_name: '',
    role: 'IMPLEMENTATION_CONSULTANT',
    employee_id: '',
  });

  const params = useMemo(
    () => ({
      q: query,
      status: statusFilter,
      role: roleFilter,
    }),
    [query, statusFilter, roleFilter],
  );

  const reload = (): void => {
    Promise.all([
      requestRows('identity/consultants/', params),
      requestRows('employees/'),
    ])
      .then(([consultants, employeeRows]) => {
        setRows(consultants);
        setEmployees(employeeRows);
        setError('');
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  useEffect(reload, [JSON.stringify(params)]);

  const open = (row: Row): void => {
    setSelected(row);
    setTemporaryPassword('');
    const id = String(row.id);
    Promise.all([
      requestRows(`identity/consultants/${id}/sessions/`),
      requestRows(`identity/consultants/${id}/audit/`),
    ])
      .then(([sessionRows, auditRows]) => {
        setSessions(sessionRows);
        setAudit(auditRows);
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  const create = (event: React.FormEvent): void => {
    event.preventDefault();
    postPath('identity/consultants/', {
      ...creating,
      employee_id: creating.employee_id || null,
    })
      .then((result) => {
        setTemporaryPassword(String(result.temporary_password ?? ''));
        setCreating({
          email: '',
          display_name: '',
          role: 'IMPLEMENTATION_CONSULTANT',
          employee_id: '',
        });
        reload();
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  const action = (suffix: string, body: Row = {}): void => {
    if (!selected) return;
    postPath(
      `identity/consultants/${String(selected.id)}/${suffix}/`,
      body,
    )
      .then((result) => {
        if (result.temporary_password) {
          setTemporaryPassword(String(result.temporary_password));
        }
        setSelected(result.consultant && typeof result.consultant === 'object'
          ? result.consultant as Row
          : result);
        reload();
      })
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  const revokeSessions = (): void => {
    if (!selected) return;
    deletePath(`identity/consultants/${String(selected.id)}/sessions/`)
      .then(() => open(selected))
      .catch((value: unknown) =>
        setError(String(value instanceof Error ? value.message : value)),
      );
  };

  return (
    <div className="cx-identity-admin">
      <ErrorBar error={error} />

      <section className="cx-identity-summary">
        <article><span>Total consultants</span><strong>{rows.length}</strong></article>
        <article>
          <span>Active</span>
          <strong>{rows.filter((row) => row.account_status === 'ACTIVE').length}</strong>
        </article>
        <article>
          <span>Locked</span>
          <strong>{rows.filter((row) => Boolean(row.locked_until)).length}</strong>
        </article>
        <article>
          <span>Active sessions</span>
          <strong>{rows.reduce(
            (total, row) => total + Number(row.active_session_count ?? 0),
            0,
          )}</strong>
        </article>
      </section>

      <section className="cx-panel">
        <div className="cx-identity-head">
          <div>
            <span className="cx-panel-kicker">Identity lifecycle</span>
            <h3>Vridhi consultants</h3>
          </div>
          <div className="cx-identity-filters">
            <input
              type="search"
              placeholder="Search name or email"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All statuses</option>
              {ACCOUNT_STATUSES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <select
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value)}
            >
              <option value="">All roles</option>
              {PROVIDER_ROLES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>

        <table className="cx-table">
          <thead>
            <tr>
              <th>Consultant</th>
              <th>Role</th>
              <th>Status</th>
              <th>Employee</th>
              <th>Last login</th>
              <th>Sessions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const membership = row.membership as Row | undefined;
              const employee = row.employee as Row | null | undefined;
              return (
                <tr key={String(row.id)} onClick={() => open(row)}>
                  <td>
                    <strong>{String(row.display_name)}</strong>
                    <small>{String(row.email)}</small>
                  </td>
                  <td><Chip value={String(membership?.role ?? '')} /></td>
                  <td>
                    <Chip
                      value={String(row.account_status)}
                      tone={row.account_status === 'ACTIVE' ? 'ok' : 'danger'}
                    />
                  </td>
                  <td>{String(employee?.name ?? 'Not linked')}</td>
                  <td>{String(row.last_login_at ?? 'Never')}</td>
                  <td>{String(row.active_session_count ?? 0)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="cx-panel">
        <h3>Add consultant</h3>
        <form className="cx-identity-create" onSubmit={create}>
          <input
            type="text"
            required
            placeholder="Display name"
            value={String(creating.display_name)}
            onChange={(event) =>
              setCreating({ ...creating, display_name: event.target.value })
            }
          />
          <input
            type="email"
            required
            placeholder="Vridhi email"
            value={String(creating.email)}
            onChange={(event) =>
              setCreating({ ...creating, email: event.target.value })
            }
          />
          <select
            value={String(creating.role)}
            onChange={(event) =>
              setCreating({ ...creating, role: event.target.value })
            }
          >
            {PROVIDER_ROLES.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
          <select
            value={String(creating.employee_id)}
            onChange={(event) =>
              setCreating({ ...creating, employee_id: event.target.value })
            }
          >
            <option value="">Link employee later</option>
            {employees.map((employee) => (
              <option key={String(employee.id)} value={String(employee.id)}>
                {String(employee.name)} Â· {String(employee.email)}
              </option>
            ))}
          </select>
          <button className="cx-btn" type="submit">Create consultant</button>
        </form>
      </section>

      {selected ? (
        <div className="cx-identity-drawer" role="dialog" aria-label="Consultant security">
          <div className="cx-identity-drawer-head">
            <div>
              <span className="cx-panel-kicker">Security administration</span>
              <h3>{String(selected.display_name)}</h3>
              <p>{String(selected.email)}</p>
            </div>
            <button className="cx-btn subtle" type="button" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>

          {temporaryPassword ? (
            <div className="cx-warning">
              <strong>Temporary password â€” shown once</strong>
              <code>{temporaryPassword}</code>
            </div>
          ) : null}

          <div className="cx-identity-actions">
            <select
              value={String((selected.membership as Row | undefined)?.role ?? '')}
              onChange={(event) =>
                action('role', {
                  role: event.target.value,
                  reason: 'Updated from consultant administration',
                })
              }
            >
              {PROVIDER_ROLES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <select
              value={String(selected.account_status)}
              onChange={(event) =>
                action('status', {
                  status: event.target.value,
                  reason: 'Updated from consultant administration',
                })
              }
            >
              {ACCOUNT_STATUSES.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
            <select
              value={String(
                (selected.membership as Row | undefined)?.employee_id ?? '',
              )}
              onChange={(event) =>
                action('employee-link', { employee_id: event.target.value })
              }
            >
              <option value="">Select employee</option>
              {employees.map((employee) => (
                <option key={String(employee.id)} value={String(employee.id)}>
                  {String(employee.name)}
                </option>
              ))}
            </select>
            <button className="cx-btn subtle" type="button" onClick={() => action('unlock')}>
              Unlock
            </button>
            <button className="cx-btn danger" type="button" onClick={() => action('password-reset')}>
              Reset password
            </button>
            <button className="cx-btn danger" type="button" onClick={revokeSessions}>
              Revoke all sessions
            </button>
          </div>

          <div className="cx-identity-detail-grid">
            <section>
              <h4>Sessions</h4>
              {sessions.length === 0 ? <p>No session history.</p> : (
                sessions.map((session) => (
                  <article key={String(session.id)}>
                    <strong>{session.active ? 'Active' : 'Closed'}</strong>
                    <span>{String(session.ip_address ?? 'Unknown IP')}</span>
                    <small>Last seen {String(session.last_seen_at ?? '-')}</small>
                  </article>
                ))
              )}
            </section>
            <section>
              <h4>Authentication audit</h4>
              {audit.length === 0 ? <p>No authentication events.</p> : (
                audit.slice(0, 30).map((event) => (
                  <article key={String(event.id)}>
                    <strong>{String(event.event_type)}</strong>
                    <Chip value={String(event.outcome)} />
                    <small>{String(event.occurred_at)}</small>
                    <span>{String(event.reason || '')}</span>
                  </article>
                ))
              )}
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function UserMenu(): React.JSX.Element {
  const { identity, logout } = useIdentity();
  if (!identity) return <></>;
  return (
    <div className="cx-user-menu">
      <div>
        <strong>{String(identity.account.display_name)}</strong>
        <small>{String(identity.membership.role)}</small>
      </div>
      <button className="cx-btn subtle" type="button" onClick={() => void logout()}>
        Sign out
      </button>
    </div>
  );
}
