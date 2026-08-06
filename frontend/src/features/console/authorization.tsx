import type * as React from 'react';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  postPath,
  requestObject,
  requestRows,
} from './api';
import { ConsultantAdministration } from './identity';
import type { Row } from './types';
import {
  Chip,
  ErrorBar,
  Loading,
} from './ui';


type AccessGroup = {
  module: string;
  rows: Row[];
};


function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item));
}


function roleAccessCodes(role: Row | null): string[] {
  if (!role || !Array.isArray(role.access)) return [];

  return (role.access as Row[])
    .map((access) => String(access.code ?? ''))
    .filter(Boolean);
}


function optionLabel(row: Row): string {
  return String(
    row.name ??
    row.legal_name ??
    row.display_name ??
    row.email ??
    row.id ??
    '',
  );
}


function ToggleList({
  rows,
  selected,
  onChange,
}: {
  rows: Row[];
  selected: string[];
  onChange: (codes: string[]) => void;
}): React.JSX.Element {
  const grouped = useMemo<AccessGroup[]>(() => {
    const groups = new Map<string, Row[]>();

    for (const row of rows) {
      const module = String(row.module ?? 'Other');
      const current = groups.get(module) ?? [];
      current.push(row);
      groups.set(module, current);
    }

    return [...groups.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([module, accessRows]) => ({
        module,
        rows: accessRows.sort((left, right) =>
          String(left.name).localeCompare(String(right.name)),
        ),
      }));
  }, [rows]);

  const toggle = (code: string): void => {
    if (selected.includes(code)) {
      onChange(selected.filter((item) => item !== code));
    } else {
      onChange([...selected, code]);
    }
  };

  return (
    <div className="cx-access-groups">
      {grouped.map((group) => (
        <section key={group.module}>
          <h4>{group.module}</h4>

          <div className="cx-access-options">
            {group.rows.map((access) => {
              const code = String(access.code);

              return (
                <label key={code}>
                  <input
                    type="checkbox"
                    checked={selected.includes(code)}
                    onChange={() => toggle(code)}
                  />

                  <span>
                    <strong>{String(access.name)}</strong>
                    <small>{code}</small>
                  </span>
                </label>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}


export function RoleAdministration(): React.JSX.Element {
  const [roles, setRoles] = useState<Row[]>([]);
  const [access, setAccess] = useState<Row[]>([]);
  const [consultants, setConsultants] = useState<Row[]>([]);
  const [departments, setDepartments] = useState<Row[]>([]);
  const [teams, setTeams] = useState<Row[]>([]);
  const [services, setServices] = useState<Row[]>([]);

  const [selectedRole, setSelectedRole] = useState<Row | null>(null);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [userProfile, setUserProfile] = useState<Row | null>(null);

  const [roleDraft, setRoleDraft] = useState<Row>({
    code: '',
    name: '',
    description: '',
    access_codes: [],
  });

  const [profileDraft, setProfileDraft] = useState<Row>({
    role_id: null,
    additional_access_codes: [],
    department_ids: [],
    team_ids: [],
    service_ids: [],
    is_active: true,
  });

  const [cloneCode, setCloneCode] = useState('');
  const [cloneName, setCloneName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState('');

  const reload = (): void => {
    setBusy(true);

    Promise.all([
      requestRows('authorization/roles/'),
      requestRows('authorization/access/'),
      requestRows('identity/consultants/'),
      requestRows('departments/'),
      requestRows('teams/'),
      requestRows('services/'),
    ])
      .then(([
        roleRows,
        accessRows,
        consultantRows,
        departmentRows,
        teamRows,
        serviceRows,
      ]) => {
        setRoles(roleRows);
        setAccess(accessRows);
        setConsultants(consultantRows);
        setDepartments(departmentRows);
        setTeams(teamRows);
        setServices(serviceRows);
        setError('');
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      })
      .finally(() => setBusy(false));
  };

  useEffect(reload, []);

  const openRole = (role: Row): void => {
    setSelectedRole(role);
    setRoleDraft({
      name: String(role.name ?? ''),
      description: String(role.description ?? ''),
      access_codes: roleAccessCodes(role),
      is_active: role.is_active !== false,
    });
    setCloneCode('');
    setCloneName('');
    setMessage('');
  };

  const createRole = (event: React.FormEvent): void => {
    event.preventDefault();
    setError('');
    setMessage('');

    postPath('authorization/roles/', roleDraft)
      .then((created) => {
        setRoleDraft({
          code: '',
          name: '',
          description: '',
          access_codes: [],
        });
        setMessage(`Role ${String(created.name)} created.`);
        reload();
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      });
  };

  const saveRole = (): void => {
    if (!selectedRole) return;

    requestObject(
      `authorization/roles/${String(selectedRole.id)}/`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          name: roleDraft.name,
          description: roleDraft.description,
          access_codes: roleDraft.access_codes,
          is_active: roleDraft.is_active,
        }),
      },
    )
      .then((updated) => {
        setSelectedRole(updated);
        setMessage('Role changes saved.');
        reload();
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      });
  };

  const cloneRole = (): void => {
    if (!selectedRole) return;

    postPath(
      `authorization/roles/${String(selectedRole.id)}/clone/`,
      {
        code: cloneCode,
        name: cloneName,
      },
    )
      .then((created) => {
        setMessage(`Role ${String(created.name)} cloned.`);
        setCloneCode('');
        setCloneName('');
        reload();
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      });
  };

  const loadUserProfile = (accountId: string): void => {
    setSelectedUserId(accountId);
    setUserProfile(null);
    setMessage('');

    if (!accountId) return;

    requestObject(`authorization/users/${accountId}/`)
      .then((profile) => {
        setUserProfile(profile);

        setProfileDraft({
          role_id:
            profile.role &&
            typeof profile.role === 'object'
              ? (profile.role as Row).id ?? null
              : null,
          additional_access_codes: stringList(
            profile.additional_access_codes,
          ),
          department_ids: stringList(profile.department_ids),
          team_ids: stringList(profile.team_ids),
          service_ids: stringList(profile.service_ids),
          is_active: profile.is_active === true,
        });
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      });
  };

  const saveUserProfile = (): void => {
    if (!selectedUserId) return;

    requestObject(
      `authorization/users/${selectedUserId}/`,
      {
        method: 'PUT',
        body: JSON.stringify(profileDraft),
      },
    )
      .then((profile) => {
        setUserProfile(profile);
        setMessage('Employee access saved.');
      })
      .catch((value: unknown) => {
        setError(String(value instanceof Error ? value.message : value));
      });
  };

  const changeScope = (
    field: 'department_ids' | 'team_ids' | 'service_ids',
    values: string[],
  ): void => {
    setProfileDraft({
      ...profileDraft,
      [field]: values,
    });
  };

  const selectedConsultant = consultants.find(
    (row) => String(row.id) === selectedUserId,
  );

  if (busy) return <Loading />;

  return (
    <div className="cx-role-admin">
      <ErrorBar error={error} />

      {message ? (
        <div className="cx-success-banner" role="status">
          {message}
        </div>
      ) : null}

      <section className="cx-identity-summary">
        <article>
          <span>Available roles</span>
          <strong>{roles.length}</strong>
        </article>

        <article>
          <span>Custom roles</span>
          <strong>
            {roles.filter((row) => row.is_system !== true).length}
          </strong>
        </article>

        <article>
          <span>Access capabilities</span>
          <strong>{access.length}</strong>
        </article>

        <article>
          <span>Consultants</span>
          <strong>{consultants.length}</strong>
        </article>
      </section>

      <div className="cx-role-layout">
        <section className="cx-panel">
          <div className="cx-identity-head">
            <div>
              <span className="cx-panel-kicker">Simple access setup</span>
              <h3>Roles</h3>
              <p>
                Use standard roles or create a role tailored to the firm.
              </p>
            </div>
          </div>

          <div className="cx-role-list">
            {roles.map((role) => (
              <button
                key={String(role.id)}
                type="button"
                className={
                  String(selectedRole?.id) === String(role.id)
                    ? 'active'
                    : ''
                }
                onClick={() => openRole(role)}
              >
                <span>
                  <strong>{String(role.name)}</strong>
                  <small>{String(role.code)}</small>
                </span>

                <span className="cx-role-list-meta">
                  {role.is_system === true ? (
                    <Chip value="SYSTEM" />
                  ) : (
                    <Chip value="CUSTOM" />
                  )}

                  <Chip
                    value={role.is_active === false ? 'INACTIVE' : 'ACTIVE'}
                    tone={role.is_active === false ? 'danger' : 'ok'}
                  />
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="cx-panel">
          {selectedRole ? (
            <>
              <div className="cx-identity-head">
                <div>
                  <span className="cx-panel-kicker">Role configuration</span>
                  <h3>{String(selectedRole.name)}</h3>
                </div>

                <button
                  className="cx-btn subtle"
                  type="button"
                  onClick={() => setSelectedRole(null)}
                >
                  Close
                </button>
              </div>

              {selectedRole.is_system === true ? (
                <div className="cx-warning">
                  Standard roles are protected. Clone this role to customise it.
                </div>
              ) : (
                <div className="cx-role-fields">
                  <label>
                    Role name
                    <input
                      value={String(roleDraft.name ?? '')}
                      onChange={(event) =>
                        setRoleDraft({
                          ...roleDraft,
                          name: event.target.value,
                        })
                      }
                    />
                  </label>

                  <label>
                    Description
                    <textarea
                      value={String(roleDraft.description ?? '')}
                      onChange={(event) =>
                        setRoleDraft({
                          ...roleDraft,
                          description: event.target.value,
                        })
                      }
                    />
                  </label>

                  <label className="cx-inline-check">
                    <input
                      type="checkbox"
                      checked={roleDraft.is_active !== false}
                      onChange={(event) =>
                        setRoleDraft({
                          ...roleDraft,
                          is_active: event.target.checked,
                        })
                      }
                    />
                    Active role
                  </label>
                </div>
              )}

              <ToggleList
                rows={access}
                selected={stringList(roleDraft.access_codes)}
                onChange={(codes) =>
                  setRoleDraft({
                    ...roleDraft,
                    access_codes: codes,
                  })
                }
              />

              {selectedRole.is_system !== true ? (
                <button
                  className="cx-btn"
                  type="button"
                  onClick={saveRole}
                >
                  Save role
                </button>
              ) : null}

              <div className="cx-role-clone">
                <h4>Clone role</h4>

                <input
                  placeholder="New role code"
                  value={cloneCode}
                  onChange={(event) => setCloneCode(event.target.value)}
                />

                <input
                  placeholder="New role name"
                  value={cloneName}
                  onChange={(event) => setCloneName(event.target.value)}
                />

                <button
                  className="cx-btn subtle"
                  type="button"
                  disabled={!cloneCode || !cloneName}
                  onClick={cloneRole}
                >
                  Clone role
                </button>
              </div>
            </>
          ) : (
            <div className="cx-empty">
              Select a role to inspect its access.
            </div>
          )}
        </section>
      </div>

      <section className="cx-panel">
        <div className="cx-identity-head">
          <div>
            <span className="cx-panel-kicker">Employee access</span>
            <h3>Assign role and scope</h3>
            <p>
              Choose one role, then add exceptional access only when needed.
            </p>
          </div>

          <select
            aria-label="Select consultant"
            value={selectedUserId}
            onChange={(event) => loadUserProfile(event.target.value)}
          >
            <option value="">Select consultant</option>

            {consultants.map((row) => (
              <option key={String(row.id)} value={String(row.id)}>
                {String(row.display_name)} - {String(row.email)}
              </option>
            ))}
          </select>
        </div>

        {selectedUserId ? (
          <div className="cx-access-profile">
            <div className="cx-access-profile-head">
              <div>
                <strong>
                  {String(
                    selectedConsultant?.display_name ??
                    selectedConsultant?.email ??
                    selectedUserId,
                  )}
                </strong>

                <small>{String(selectedConsultant?.email ?? '')}</small>
              </div>

              <label className="cx-inline-check">
                <input
                  type="checkbox"
                  checked={profileDraft.is_active === true}
                  onChange={(event) =>
                    setProfileDraft({
                      ...profileDraft,
                      is_active: event.target.checked,
                    })
                  }
                />
                Access active
              </label>
            </div>

            <div className="cx-access-profile-grid">
              <label>
                Role
                <select
                  value={String(profileDraft.role_id ?? '')}
                  onChange={(event) =>
                    setProfileDraft({
                      ...profileDraft,
                      role_id:
                        event.target.value === ''
                          ? null
                          : Number(event.target.value),
                    })
                  }
                >
                  <option value="">No role</option>

                  {roles
                    .filter((role) => role.is_active !== false)
                    .map((role) => (
                      <option
                        key={String(role.id)}
                        value={String(role.id)}
                      >
                        {String(role.name)}
                      </option>
                    ))}
                </select>
              </label>

              <label>
                Departments
                <select
                  multiple
                  value={stringList(profileDraft.department_ids)}
                  onChange={(event) =>
                    changeScope(
                      'department_ids',
                      Array.from(event.target.selectedOptions)
                        .map((option) => option.value),
                    )
                  }
                >
                  {departments.map((row) => (
                    <option key={String(row.id)} value={String(row.id)}>
                      {optionLabel(row)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Teams
                <select
                  multiple
                  value={stringList(profileDraft.team_ids)}
                  onChange={(event) =>
                    changeScope(
                      'team_ids',
                      Array.from(event.target.selectedOptions)
                        .map((option) => option.value),
                    )
                  }
                >
                  {teams.map((row) => (
                    <option key={String(row.id)} value={String(row.id)}>
                      {optionLabel(row)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Services
                <select
                  multiple
                  value={stringList(profileDraft.service_ids)}
                  onChange={(event) =>
                    changeScope(
                      'service_ids',
                      Array.from(event.target.selectedOptions)
                        .map((option) => option.value),
                    )
                  }
                >
                  {services.map((row) => (
                    <option key={String(row.id)} value={String(row.id)}>
                      {optionLabel(row)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div>
              <h4>Additional access</h4>
              <p className="cx-help">
                Use only for exceptional responsibilities not covered by the role.
              </p>

              <ToggleList
                rows={access}
                selected={stringList(
                  profileDraft.additional_access_codes,
                )}
                onChange={(codes) =>
                  setProfileDraft({
                    ...profileDraft,
                    additional_access_codes: codes,
                  })
                }
              />
            </div>

            <div className="cx-effective-access">
              <h4>Effective access preview</h4>

              <div>
                {stringList(userProfile?.effective_access_codes).length === 0 ? (
                  <span>No effective access assigned.</span>
                ) : (
                  stringList(userProfile?.effective_access_codes)
                    .map((code) => (
                      <code key={code}>{code}</code>
                    ))
                )}
              </div>
            </div>

            <button
              className="cx-btn"
              type="button"
              onClick={saveUserProfile}
            >
              Save employee access
            </button>
          </div>
        ) : (
          <div className="cx-empty">
            Select a consultant to configure access.
          </div>
        )}
      </section>

      <section className="cx-panel">
        <h3>Create custom role</h3>

        <form className="cx-role-create" onSubmit={createRole}>
          <label>
            Role code
            <input
              required
              placeholder="GST_MANAGER"
              value={String(roleDraft.code ?? '')}
              onChange={(event) =>
                setRoleDraft({
                  ...roleDraft,
                  code: event.target.value.toUpperCase(),
                })
              }
            />
          </label>

          <label>
            Role name
            <input
              required
              placeholder="GST Manager"
              value={
                selectedRole
                  ? ''
                  : String(roleDraft.name ?? '')
              }
              onChange={(event) =>
                setRoleDraft({
                  ...roleDraft,
                  name: event.target.value,
                })
              }
            />
          </label>

          <label>
            Description
            <input
              value={
                selectedRole
                  ? ''
                  : String(roleDraft.description ?? '')
              }
              onChange={(event) =>
                setRoleDraft({
                  ...roleDraft,
                  description: event.target.value,
                })
              }
            />
          </label>

          <button className="cx-btn" type="submit">
            Create role
          </button>
        </form>
      </section>
    </div>
  );
}


export function IdentityAccessAdministration(): React.JSX.Element {
  const [section, setSection] = useState<'consultants' | 'roles'>(
    'consultants',
  );

  return (
    <div className="cx-identity-access">
      <div className="cx-section-tabs" aria-label="Identity and access sections">
        <button
          type="button"
          className={section === 'consultants' ? 'active' : ''}
          onClick={() => setSection('consultants')}
        >
          Consultants
        </button>

        <button
          type="button"
          className={section === 'roles' ? 'active' : ''}
          onClick={() => setSection('roles')}
        >
          Roles & Access
        </button>
      </div>

      {section === 'consultants' ? (
        <ConsultantAdministration />
      ) : (
        <RoleAdministration />
      )}
    </div>
  );
}
