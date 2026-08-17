import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { act, list, save, collectionAct } from './api';
import { label } from './types';
import {
  EMPLOYMENT_TYPES,
  EMPLOYMENT_STATUS,
  PROFICIENCY_LEVELS,
  EXPERTISE_CATEGORIES,
  REVIEWER_SCOPES,
  REVIEWER_LEVELS,
} from './types';
import type { Row } from './types';
import { Chip, DataTable, Drawer, Empty, ErrorBar, Loading } from './ui';
import type { Column, Field } from './ui';

// Employee Operations V1 console area. Reuses the shared UI kit and API client.
// Every UUID reference is chosen from a selector whose options are existing row
// ids with a human-readable label lookup — no raw-UUID inputs anywhere.

type Section =
  | 'directory'
  | 'organisation'
  | 'expertise'
  | 'capacity'
  | 'leave'
  | 'reviewer'
  | 'assignment';

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'directory', label: 'Employee Directory' },
  { key: 'organisation', label: 'Organisation' },
  { key: 'expertise', label: 'Expertise' },
  { key: 'capacity', label: 'Capacity' },
  { key: 'leave', label: 'Leave & Holidays' },
  { key: 'reviewer', label: 'Reviewer Hierarchy' },
  { key: 'assignment', label: 'Assignment' },
];

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

export function EmployeeOpsArea({
  initialSection,
  onInitialSectionHandled,
}: {
  initialSection?: Section | undefined;
  onInitialSectionHandled?: () => void;
} = {}): React.JSX.Element {
  const [section, setSection] = useState<Section>(
    initialSection ?? 'directory',
  );

  useEffect(() => {
    if (!initialSection) return;

    setSection(initialSection);
    onInitialSectionHandled?.();
  }, [
    initialSection,
  ]);

  return (
    <div className="cx-area">
      <div className="cx-subnav">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            type="button"
            className={s.key === section ? 'cx-btn' : 'cx-btn subtle'}
            onClick={() => setSection(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>
      {section === 'directory' ? <DirectorySection /> : null}
      {section === 'organisation' ? <OrganisationSection /> : null}
      {section === 'expertise' ? <ExpertiseSection /> : null}
      {section === 'capacity' ? <CapacitySection /> : null}
      {section === 'leave' ? <LeaveSection /> : null}
      {section === 'reviewer' ? <ReviewerSection /> : null}
      {section === 'assignment' ? <AssignmentSection /> : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Employee Directory + Profile + Employment details
// --------------------------------------------------------------------------

function DirectorySection(): React.JSX.Element {
  const employees = useList('employees');
  const departments = useList('departments');
  const designations = useList('designations');
  const teams = useList('teams');
  const branches = useList('branches');
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const nameOf = (rows: Row[], id: unknown): string => String(rows.find((r) => r.id === id)?.name ?? '-');
  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const options = (rows: Row[]): string[] => rows.map((r) => String(r.id));

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '' && k !== 'expertise_records') clean[k] = v;
    save('employees', clean)
      .then(() => {
        setEditing(null);
        setErr('');
        employees.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (employees.loading) return <Loading />;

  const columns: Column[] = [
    { key: 'name', header: 'Name' },
    { key: 'employee_code', header: 'Code' },
    { key: 'department_id', header: 'Department', render: (r) => nameOf(departments.rows, r.department_id) },
    { key: 'designation_id', header: 'Designation', render: (r) => nameOf(designations.rows, r.designation_id) },
    { key: 'manager_id', header: 'Manager', render: (r) => empName(r.manager_id) },
    { key: 'employment_status', header: 'Status', render: (r) => (r.employment_status ? <Chip value={String(r.employment_status)} /> : '-') },
    { key: 'is_active', header: 'Active', render: (r) => (r.is_active ? 'Yes' : 'No') },
  ];

  const fields: Field[] = [
    { name: 'name', kind: 'text' },
    { name: 'email', kind: 'text' },
    { name: 'mobile', kind: 'text' },
    { name: 'employee_code', kind: 'text' },
    { name: 'department_id', kind: 'select', options: options(departments.rows), labels: (v) => nameOf(departments.rows, v) },
    { name: 'designation_id', kind: 'select', options: options(designations.rows), labels: (v) => nameOf(designations.rows, v) },
    { name: 'team_id', kind: 'select', options: options(teams.rows), labels: (v) => nameOf(teams.rows, v) },
    { name: 'branch_id', kind: 'select', options: options(branches.rows), labels: (v) => nameOf(branches.rows, v) },
    { name: 'manager_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
    { name: 'employment_type', kind: 'select', options: [...EMPLOYMENT_TYPES] },
    { name: 'employment_status', kind: 'select', options: [...EMPLOYMENT_STATUS] },
    { name: 'joining_date', kind: 'date' },
    { name: 'confirmation_date', kind: 'date' },
    { name: 'exit_date', kind: 'date' },
    { name: 'timezone', kind: 'text' },
    { name: 'notes', kind: 'textarea' },
  ];

  return (
    <div>
      <div className="cx-toolbar">
        <button type="button" className="cx-btn" onClick={() => setEditing({ name: '', email: '', is_active: true })}>
          New employee
        </button>
      </div>
      <ErrorBar error={employees.error} />
      <DataTable columns={columns} rows={employees.rows} onRow={(r) => setEditing(r)} empty="No employees yet." />
      {editing ? (
        <Drawer
          title="Employee"
          fields={fields}
          value={editing}
          onChange={setEditing}
          onSave={submit}
          onClose={() => setEditing(null)}
          extra={<ErrorBar error={err} />}
        />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Organisation: departments, designations, reporting relationships
// --------------------------------------------------------------------------

function OrganisationSection(): React.JSX.Element {
  type Tab = 'departments' | 'designations' | 'reporting-relationships';
  const [tab, setTab] = useState<Tab>('departments');
  const current = useList(tab);
  const employees = useList('employees');
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save(tab, clean)
      .then(() => {
        setEditing(null);
        setErr('');
        current.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const blank = (): Row => {
    if (tab === 'reporting-relationships') return { employee_id: '', manager_id: '', relation_type: 'PRIMARY', is_active: true };
    return { name: '', code: '', status: 'ACTIVE' };
  };

  const columns = (): Column[] => {
    if (tab === 'reporting-relationships') {
      return [
        { key: 'employee_id', header: 'Employee', render: (r) => empName(r.employee_id) },
        { key: 'manager_id', header: 'Manager', render: (r) => empName(r.manager_id) },
        { key: 'relation_type', header: 'Type', render: (r) => label(String(r.relation_type)) },
        { key: 'is_active', header: 'Active', render: (r) => (r.is_active ? 'Yes' : 'No') },
      ];
    }
    return [
      { key: 'name', header: 'Name' },
      { key: 'code', header: 'Code' },
      { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} /> },
    ];
  };

  const fields = (): Field[] => {
    if (tab === 'reporting-relationships') {
      return [
        { name: 'employee_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
        { name: 'manager_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
        { name: 'relation_type', kind: 'select', options: ['PRIMARY', 'DOTTED'] },
        { name: 'effective_from', kind: 'date' },
        { name: 'effective_to', kind: 'date' },
      ];
    }
    return [
      { name: 'name', kind: 'text' },
      { name: 'code', kind: 'text' },
      { name: 'description', kind: 'textarea' },
      { name: 'status', kind: 'select', options: ['ACTIVE', 'INACTIVE'] },
    ];
  };

  if (current.loading) return <Loading />;

  const TABS: { key: Tab; label: string }[] = [
    { key: 'departments', label: 'Departments' },
    { key: 'designations', label: 'Designations' },
    { key: 'reporting-relationships', label: 'Reporting' },
  ];

  return (
    <div>
      <div className="cx-subnav">
        {TABS.map((t) => (
          <button key={t.key} type="button" className={t.key === tab ? 'cx-btn' : 'cx-btn subtle'} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
        <button type="button" className="cx-btn" onClick={() => setEditing(blank())}>
          New
        </button>
      </div>
      <ErrorBar error={current.error || err} />
      <DataTable columns={columns()} rows={current.rows} onRow={(r) => setEditing(r)} empty="Nothing here yet." />
      {editing ? (
        <Drawer title="Organisation" fields={fields()} value={editing} onChange={setEditing} onSave={submit} onClose={() => setEditing(null)} extra={<ErrorBar error={err} />} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Expertise management
// --------------------------------------------------------------------------

function ExpertiseSection(): React.JSX.Element {
  const records = useList('employee-expertise');
  const employees = useList('employees');
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save('employee-expertise', clean)
      .then(() => {
        setEditing(null);
        setErr('');
        records.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (records.loading) return <Loading />;

  const columns: Column[] = [
    { key: 'employee_id', header: 'Employee', render: (r) => empName(r.employee_id) },
    { key: 'category', header: 'Category', render: (r) => label(String(r.category)) },
    { key: 'proficiency', header: 'Proficiency', render: (r) => <Chip value={String(r.proficiency)} /> },
    { key: 'reviewer_eligible', header: 'Reviewer', render: (r) => (r.reviewer_eligible ? 'Yes' : 'No') },
    { key: 'is_active', header: 'Active', render: (r) => (r.is_active ? 'Yes' : 'No') },
  ];

  const fields: Field[] = [
    { name: 'employee_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
    { name: 'category', kind: 'select', options: [...EXPERTISE_CATEGORIES] },
    { name: 'proficiency', kind: 'select', options: [...PROFICIENCY_LEVELS] },
    { name: 'experience_months', kind: 'text' },
    { name: 'certification', kind: 'text' },
    { name: 'reviewer_eligible', kind: 'checkbox' },
    { name: 'is_primary', kind: 'checkbox' },
    { name: 'effective_from', kind: 'date' },
    { name: 'evidence', kind: 'textarea' },
  ];

  return (
    <div>
      <div className="cx-toolbar">
        <button type="button" className="cx-btn" onClick={() => setEditing({ employee_id: '', category: 'GST', proficiency: 'INTERMEDIATE', is_active: true })}>
          New expertise
        </button>
      </div>
      <ErrorBar error={records.error} />
      <DataTable columns={columns} rows={records.rows} onRow={(r) => setEditing(r)} empty="No expertise records yet." />
      {editing ? (
        <Drawer title="Expertise" fields={fields} value={editing} onChange={setEditing} onSave={submit} onClose={() => setEditing(null)} extra={<ErrorBar error={err} />} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Capacity & availability
// --------------------------------------------------------------------------

function CapacitySection(): React.JSX.Element {
  const profiles = useList('capacity-profiles');
  const employees = useList('employees');
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save('capacity-profiles', clean)
      .then(() => {
        setEditing(null);
        setErr('');
        profiles.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (profiles.loading) return <Loading />;

  const columns: Column[] = [
    { key: 'employee_id', header: 'Employee', render: (r) => empName(r.employee_id) },
    { key: 'daily_hours', header: 'Daily hours' },
    { key: 'effective_from', header: 'From', render: (r) => String(r.effective_from ?? '-') },
    { key: 'is_active', header: 'Active', render: (r) => (r.is_active ? 'Yes' : 'No') },
  ];

  const fields: Field[] = [
    { name: 'employee_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
    { name: 'daily_hours', kind: 'text' },
    { name: 'works_monday', kind: 'checkbox' },
    { name: 'works_tuesday', kind: 'checkbox' },
    { name: 'works_wednesday', kind: 'checkbox' },
    { name: 'works_thursday', kind: 'checkbox' },
    { name: 'works_friday', kind: 'checkbox' },
    { name: 'works_saturday', kind: 'checkbox' },
    { name: 'works_sunday', kind: 'checkbox' },
    { name: 'effective_from', kind: 'date' },
    { name: 'effective_to', kind: 'date' },
  ];

  return (
    <div>
      <div className="cx-toolbar">
        <button type="button" className="cx-btn" onClick={() => setEditing({ employee_id: '', daily_hours: '8', works_monday: true, works_tuesday: true, works_wednesday: true, works_thursday: true, works_friday: true, is_active: true })}>
          New capacity profile
        </button>
      </div>
      <ErrorBar error={profiles.error} />
      <DataTable columns={columns} rows={profiles.rows} onRow={(r) => setEditing(r)} empty="No capacity profiles yet." />
      {editing ? (
        <Drawer title="Capacity profile" fields={fields} value={editing} onChange={setEditing} onSave={submit} onClose={() => setEditing(null)} extra={<ErrorBar error={err} />} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Leave & holidays
// --------------------------------------------------------------------------

function LeaveSection(): React.JSX.Element {
  const leave = useList('leave-records');
  const holidays = useList('holidays');
  const employees = useList('employees');
  const [editing, setEditing] = useState<Row | null>(null);
  const [holidayEditing, setHolidayEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const decide = (row: Row, verb: 'approve' | 'reject' | 'cancel'): void => {
    act('leave-records', String(row.id), verb, {})
      .then(() => leave.reload())
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const submitLeave = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save('leave-records', clean)
      .then(() => {
        setEditing(null);
        setErr('');
        leave.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  const submitHoliday = (): void => {
    if (!holidayEditing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(holidayEditing)) if (v !== '') clean[k] = v;
    save('holidays', clean)
      .then(() => {
        setHolidayEditing(null);
        setErr('');
        holidays.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (leave.loading) return <Loading />;

  const leaveColumns: Column[] = [
    { key: 'employee_id', header: 'Employee', render: (r) => empName(r.employee_id) },
    { key: 'start_date', header: 'From' },
    { key: 'end_date', header: 'To' },
    { key: 'status', header: 'Status', render: (r) => <Chip value={String(r.status)} /> },
    {
      key: 'actions',
      header: '',
      render: (r) =>
        r.status === 'REQUESTED' ? (
          <span>
            <button type="button" className="cx-btn subtle" onClick={() => decide(r, 'approve')}>Approve</button>{' '}
            <button type="button" className="cx-btn subtle" onClick={() => decide(r, 'reject')}>Reject</button>
          </span>
        ) : r.status === 'APPROVED' ? (
          <button type="button" className="cx-btn subtle" onClick={() => decide(r, 'cancel')}>Cancel</button>
        ) : (
          <span>-</span>
        ),
    },
  ];

  return (
    <div>
      <div className="cx-toolbar">
        <button type="button" className="cx-btn" onClick={() => setEditing({ employee_id: '', start_date: '', end_date: '' })}>
          New leave request
        </button>{' '}
        <button type="button" className="cx-btn subtle" onClick={() => setHolidayEditing({ name: '', holiday_date: '', is_active: true })}>
          New holiday
        </button>
      </div>
      <ErrorBar error={leave.error || err} />
      <h4>Leave</h4>
      <DataTable columns={leaveColumns} rows={leave.rows} empty="No leave records yet." />
      <h4>Holidays</h4>
      {holidays.rows.length === 0 ? (
        <Empty message="No holidays configured." />
      ) : (
        <DataTable
          columns={[
            { key: 'name', header: 'Name' },
            { key: 'holiday_date', header: 'Date' },
          ]}
          rows={holidays.rows}
          empty="No holidays configured."
        />
      )}
      {editing ? (
        <Drawer
          title="Leave request"
          fields={[
            { name: 'employee_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
            { name: 'start_date', kind: 'date' },
            { name: 'end_date', kind: 'date' },
            { name: 'is_partial_day', kind: 'checkbox' },
            { name: 'hours', kind: 'text' },
            { name: 'reason', kind: 'textarea' },
          ]}
          value={editing}
          onChange={setEditing}
          onSave={submitLeave}
          onClose={() => setEditing(null)}
          extra={<ErrorBar error={err} />}
        />
      ) : null}
      {holidayEditing ? (
        <Drawer
          title="Holiday"
          fields={[
            { name: 'name', kind: 'text' },
            { name: 'holiday_date', kind: 'date' },
          ]}
          value={holidayEditing}
          onChange={setHolidayEditing}
          onSave={submitHoliday}
          onClose={() => setHolidayEditing(null)}
          extra={<ErrorBar error={err} />}
        />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Reviewer hierarchy
// --------------------------------------------------------------------------

function ReviewerSection(): React.JSX.Element {
  const rules = useList('reviewer-rules');
  const employees = useList('employees');
  const services = useList('services');
  const [editing, setEditing] = useState<Row | null>(null);
  const [err, setErr] = useState('');

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const submit = (): void => {
    if (!editing) return;
    const clean: Row = {};
    for (const [k, v] of Object.entries(editing)) if (v !== '') clean[k] = v;
    save('reviewer-rules', clean)
      .then(() => {
        setEditing(null);
        setErr('');
        rules.reload();
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (rules.loading) return <Loading />;

  const columns: Column[] = [
    { key: 'scope', header: 'Scope', render: (r) => label(String(r.scope)) },
    { key: 'level', header: 'Level', render: (r) => label(String(r.level)) },
    { key: 'reviewer_user_id', header: 'Reviewer', render: (r) => empName(r.reviewer_user_id) },
    { key: 'is_active', header: 'Active', render: (r) => (r.is_active ? 'Yes' : 'No') },
  ];

  const fields: Field[] = [
    { name: 'scope', kind: 'select', options: [...REVIEWER_SCOPES] },
    { name: 'level', kind: 'select', options: [...REVIEWER_LEVELS] },
    { name: 'reviewer_user_id', kind: 'select', options: employees.rows.map((e) => String(e.id)), labels: (v) => empName(v) },
    { name: 'service_id', kind: 'select', options: services.rows.map((s) => String(s.id)), labels: (v) => String(services.rows.find((s) => s.id === v)?.name ?? v) },
    { name: 'effective_from', kind: 'date' },
    { name: 'effective_to', kind: 'date' },
  ];

  return (
    <div>
      <div className="cx-toolbar">
        <button type="button" className="cx-btn" onClick={() => setEditing({ scope: 'SERVICE', level: 'PRIMARY', reviewer_user_id: '', is_active: true })}>
          New reviewer rule
        </button>
      </div>
      <ErrorBar error={rules.error || err} />
      <DataTable columns={columns} rows={rules.rows} onRow={(r) => setEditing(r)} empty="No reviewer rules yet." />
      {editing ? (
        <Drawer title="Reviewer rule" fields={fields} value={editing} onChange={setEditing} onSave={submit} onClose={() => setEditing(null)} extra={<ErrorBar error={err} />} />
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------
// Assignment recommendations panel
// --------------------------------------------------------------------------

function AssignmentSection(): React.JSX.Element {
  const work = useList('work-items');
  const employees = useList('employees');
  const [workItemId, setWorkItemId] = useState('');
  const [category, setCategory] = useState('');
  const [candidates, setCandidates] = useState<Row[]>([]);
  const [explanationShown, setExplanationShown] = useState<string | null>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const empName = (id: unknown): string => String(employees.rows.find((e) => e.id === id)?.name ?? '-');

  const openWork = useMemo(
    () => work.rows.filter((w) => w.status !== 'COMPLETED' && w.status !== 'CANCELLED'),
    [work.rows],
  );

  const recommend = (): void => {
    setBusy(true);
    setErr('');
    collectionAct('assignment-recommendations', 'recommend', {
      required_category: category || undefined,
    })
      .then((r) => setCandidates(((r as Row).candidates as Row[]) ?? []))
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)))
      .finally(() => setBusy(false));
  };

  const execute = (candidate: Row, isOverride: boolean): void => {
    if (!workItemId) {
      setErr('Select a work item first.');
      return;
    }
    const body: Row = {
      work_item_id: workItemId,
      owner_user_id: candidate.employee_id,
      was_override: isOverride,
      recommended_owner_user_id: candidates[0]?.employee_id,
      explanation: candidate.score_breakdown ?? {},
    };
    if (isOverride) body.override_reason = 'Manual override from recommendation panel';
    collectionAct('assignment-recommendations', 'execute', body)
      .then(() => {
        setErr('');
        work.reload();
        setCandidates([]);
      })
      .catch((e: unknown) => setErr(String(e instanceof Error ? e.message : e)));
  };

  if (work.loading) return <Loading />;

  return (
    <div>
      <div className="cx-panel">
        <div className="cx-field">
          <label>Work item</label>
          <select value={workItemId} onChange={(e) => setWorkItemId(e.target.value)}>
            <option value="">- select work item -</option>
            {openWork.map((w) => (
              <option key={String(w.id)} value={String(w.id)}>
                {String(w.title)}
              </option>
            ))}
          </select>
        </div>
        <div className="cx-field">
          <label>Required expertise (optional)</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">- any -</option>
            {EXPERTISE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {label(c)}
              </option>
            ))}
          </select>
        </div>
        <button type="button" className="cx-btn" disabled={busy} onClick={recommend}>
          {busy ? 'Computing…' : 'Get recommendations'}
        </button>
      </div>
      <ErrorBar error={work.error || err} />
      {candidates.length === 0 ? (
        <Empty message="No recommendations computed yet." />
      ) : (
        <table className="cx-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>Eligible</th>
              <th>Score</th>
              <th>Open work</th>
              <th>Available h</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c, idx) => (
              <tr key={String(c.employee_id)}>
                <td>{empName(c.employee_id)}</td>
                <td>{c.eligible ? 'Yes' : 'No'}</td>
                <td>
                  {String(c.score)}{' '}
                  <button type="button" className="cx-btn subtle" onClick={() => setExplanationShown(JSON.stringify(c.score_breakdown ?? {}, null, 2))}>
                    Why?
                  </button>
                </td>
                <td>{String(c.open_workload ?? 0)}</td>
                <td>{String(c.available_hours ?? 0)}</td>
                <td>
                  <button type="button" className="cx-btn" disabled={!c.eligible} onClick={() => execute(c, idx !== 0)}>
                    {idx === 0 ? 'Assign' : 'Assign (override)'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {explanationShown ? (
        <div className="cx-drawer-backdrop" onClick={() => setExplanationShown(null)}>
          <div className="cx-drawer" onClick={(e) => e.stopPropagation()}>
            <h3>Score breakdown</h3>
            <pre>{explanationShown}</pre>
            <button type="button" className="cx-btn" onClick={() => setExplanationShown(null)}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
