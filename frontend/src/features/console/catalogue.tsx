import type * as React from 'react';
import { useEffect, useMemo, useState } from 'react';

import { list, save } from './api';
import {
  DOCUMENT_CATEGORIES,
  label,
} from './types';
import type { Row } from './types';
import {
  Chip,
  DataTable,
  Drawer,
  ErrorBar,
  Loading,
} from './ui';
import { QACataloguePanel } from './qa';

type Level =
  | 'verticals'
  | 'domains'
  | 'services'
  | 'requirement-sets'
  | 'document-requirements';

interface ListState {
  rows: Row[];
  error: string;
  loading: boolean;
  reload: () => void;
}

function useList(
  resource: string,
  params: Record<string, string | undefined> = {},
): ListState {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const dependency = JSON.stringify(params);

  const reload = (): void => {
    setLoading(true);

    list(resource, params)
      .then((result) => {
        setRows(result);
        setError('');
      })
      .catch((value: unknown) => {
        setError(
          String(
            value instanceof Error
              ? value.message
              : value,
          ),
        );
      })
      .finally(() => setLoading(false));
  };

  useEffect(reload, [resource, dependency]);

  return {
    rows,
    error,
    loading,
    reload,
  };
}

function valueName(
  rows: Row[],
  id: unknown,
  fallback = '',
): string {
  const row = rows.find(
    (candidate) => String(candidate.id) === String(id),
  );

  return String(row?.name ?? fallback);
}

export function CatalogueArea(): React.JSX.Element {
  const [level, setLevel] = useState<Level>('verticals');
  const [editing, setEditing] = useState<Row | null>(null);
  const [saveError, setSaveError] = useState('');

  const verticals = useList('verticals');
  const domains = useList('domains');
  const services = useList('services');

  const requirementSets = useList(
    'service-document-requirement-sets',
  );

  const requirements = useList(
    'service-document-requirements',
  );

  const activeVerticals = useMemo(
    () =>
      verticals.rows.filter(
        (row) => row.status === 'ACTIVE',
      ),
    [verticals.rows],
  );

  const activeDomains = useMemo(
    () =>
      domains.rows.filter(
        (row) => row.status === 'ACTIVE',
      ),
    [domains.rows],
  );

  const activeServices = useMemo(
    () =>
      services.rows.filter(
        (row) => row.status === 'ACTIVE',
      ),
    [services.rows],
  );

  const availableSets = useMemo(
    () =>
      requirementSets.rows.filter(
        (row) => row.status !== 'RETIRED',
      ),
    [requirementSets.rows],
  );

  const verticalName = (id: unknown): string =>
    valueName(verticals.rows, id);

  const domainName = (id: unknown): string =>
    valueName(domains.rows, id);

  const serviceName = (id: unknown): string =>
    valueName(services.rows, id);

  const setName = (id: unknown): string => {
    const row = requirementSets.rows.find(
      (candidate) =>
        String(candidate.id) === String(id),
    );

    if (!row) return '';

    return `${String(row.name)} · V${String(
      row.version_number ?? 1,
    )}`;
  };

  const current: ListState =
    level === 'verticals'
      ? verticals
      : level === 'domains'
        ? domains
        : level === 'services'
          ? services
          : level === 'requirement-sets'
            ? requirementSets
            : requirements;

  const blank = (): Row => {
    if (level === 'verticals') {
      return {
        name: '',
        code: '',
        description: '',
        status: 'ACTIVE',
      };
    }

    if (level === 'domains') {
      return {
        name: '',
        code: '',
        vertical_id: '',
        description: '',
        status: 'ACTIVE',
      };
    }

    if (level === 'services') {
      return {
        name: '',
        code: '',
        domain_id: '',
        description: '',
        default_due_days: '',
        status: 'ACTIVE',
      };
    }

    if (level === 'requirement-sets') {
      return {
        service_id: '',
        name: '',
        version_number: 1,
        effective_from: '',
        effective_until: '',
        status: 'DRAFT',
        description: '',
      };
    }

    return {
      service_id: '',
      requirement_set_id: '',
      name: '',
      code: '',
      category: 'OTHER',
      mandatory: true,
      display_order: 10,
      financial_year_required: false,
      assessment_year_required: false,
      filing_period_required: false,
      expiry_applicable: false,
      expiry_reminder_days: '',
      requires_review: true,
      allow_multiple_versions: true,
      allow_multiple_files: false,
      allowed_extensions: 'pdf,xlsx,xls,csv',
      maximum_file_size_mb: 15,
      is_active: true,
      description: '',
    };
  };

  const submit = (): void => {
    if (!editing) return;

    const clean: Row = {};

    for (const [key, value] of Object.entries(editing)) {
      if (value !== '') clean[key] = value;
    }

    const resource =
      level === 'requirement-sets'
        ? 'service-document-requirement-sets'
        : level === 'document-requirements'
          ? 'service-document-requirements'
          : level;

    save(resource, clean)
      .then(() => {
        setEditing(null);
        setSaveError('');
        current.reload();

        if (level === 'document-requirements') {
          requirementSets.reload();
        }
      })
      .catch((value: unknown) => {
        setSaveError(
          String(
            value instanceof Error
              ? value.message
              : value,
          ),
        );
      });
  };

  const columns =
    level === 'verticals'
      ? [
          {
            key: 'name',
            header: 'Vertical',
          },
          {
            key: 'code',
            header: 'Code',
          },
          {
            key: 'status',
            header: 'Status',
            render: (row: Row) => (
              <Chip
                value={String(row.status)}
                tone={
                  row.status === 'ACTIVE'
                    ? 'ok'
                    : 'danger'
                }
              />
            ),
          },
        ]
      : level === 'domains'
        ? [
            {
              key: 'name',
              header: 'Domain',
            },
            {
              key: 'vertical_id',
              header: 'Vertical',
              render: (row: Row) =>
                verticalName(row.vertical_id),
            },
            {
              key: 'status',
              header: 'Status',
              render: (row: Row) => (
                <Chip
                  value={String(row.status)}
                  tone={
                    row.status === 'ACTIVE'
                      ? 'ok'
                      : 'danger'
                  }
                />
              ),
            },
          ]
        : level === 'services'
          ? [
              {
                key: 'name',
                header: 'Service',
              },
              {
                key: 'domain_id',
                header: 'Domain',
                render: (row: Row) =>
                  domainName(row.domain_id),
              },
              {
                key: 'default_due_days',
                header: 'Default due days',
              },
              {
                key: 'status',
                header: 'Status',
                render: (row: Row) => (
                  <Chip
                    value={String(row.status)}
                    tone={
                      row.status === 'ACTIVE'
                        ? 'ok'
                        : 'danger'
                    }
                  />
                ),
              },
            ]
          : level === 'requirement-sets'
            ? [
                {
                  key: 'name',
                  header: 'Requirement set',
                },
                {
                  key: 'service_id',
                  header: 'Service',
                  render: (row: Row) =>
                    serviceName(row.service_id),
                },
                {
                  key: 'version_number',
                  header: 'Version',
                  render: (row: Row) =>
                    `V${String(
                      row.version_number ?? 1,
                    )}`,
                },
                {
                  key: 'effective_from',
                  header: 'Effective from',
                },
                {
                  key: 'requirement_count',
                  header: 'Documents',
                },
                {
                  key: 'mandatory_count',
                  header: 'Mandatory',
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row: Row) => (
                    <Chip
                      value={String(row.status)}
                      tone={
                        row.status === 'ACTIVE'
                          ? 'ok'
                          : row.status === 'DRAFT'
                            ? 'warn'
                            : 'muted'
                      }
                    />
                  ),
                },
              ]
            : [
                {
                  key: 'name',
                  header: 'Document',
                },
                {
                  key: 'service_id',
                  header: 'Service',
                  render: (row: Row) =>
                    serviceName(row.service_id),
                },
                {
                  key: 'requirement_set_id',
                  header: 'Requirement set',
                  render: (row: Row) =>
                    setName(row.requirement_set_id),
                },
                {
                  key: 'category',
                  header: 'Category',
                  render: (row: Row) => (
                    <Chip
                      value={String(row.category)}
                      tone="muted"
                    />
                  ),
                },
                {
                  key: 'mandatory',
                  header: 'Requirement',
                  render: (row: Row) => (
                    <Chip
                      value={
                        row.mandatory === true
                          ? 'MANDATORY'
                          : 'OPTIONAL'
                      }
                      tone={
                        row.mandatory === true
                          ? 'warn'
                          : 'muted'
                      }
                    />
                  ),
                },
                {
                  key: 'allowed_extensions',
                  header: 'Allowed files',
                },
                {
                  key: 'is_active',
                  header: 'Status',
                  render: (row: Row) => (
                    <Chip
                      value={
                        row.is_active === true
                          ? 'ACTIVE'
                          : 'INACTIVE'
                      }
                      tone={
                        row.is_active === true
                          ? 'ok'
                          : 'danger'
                      }
                    />
                  ),
                },
              ];

  const levelLabel =
    level === 'requirement-sets'
      ? 'Requirement sets'
      : level === 'document-requirements'
        ? 'Document requirements'
        : label(level);

  const addLabel =
    level === 'requirement-sets'
      ? 'Add requirement set'
      : level === 'document-requirements'
        ? 'Add document requirement'
        : `Add ${label(level).replace(/s$/, '')}`;

  return (
    <>
      <div className="cx-toolbar">
        {(
          [
            'verticals',
            'domains',
            'services',
            'requirement-sets',
            'document-requirements',
          ] as Level[]
        ).map((item) => (
          <button
            key={item}
            type="button"
            className={`cx-btn ${
              item === level ? '' : 'subtle'
            }`}
            onClick={() => {
              setLevel(item);
              setEditing(null);
              setSaveError('');
            }}
          >
            {item === 'requirement-sets'
              ? 'Requirement sets'
              : item === 'document-requirements'
                ? 'Document catalogue'
                : label(item)}
          </button>
        ))}

        <div className="cx-spacer" />

        <button
          type="button"
          className="cx-btn"
          onClick={() => {
            setEditing(blank());
            setSaveError('');
          }}
        >
          {addLabel}
        </button>
      </div>

      {level === 'requirement-sets' ? (
        <div className="cx-muted">
          Versioned checklists preserve historical document
          requirements when statutory rules change.
        </div>
      ) : null}

      {level === 'document-requirements' ? (
        <div className="cx-muted">
          Configure the documents VRIDHI should request for each
          CA service.
        </div>
      ) : null}

      <ErrorBar error={current.error} />

      {current.loading ? (
        <Loading />
      ) : (
        <DataTable
          columns={columns}
          rows={current.rows}
          onRow={(row) => {
            setEditing({ ...row });
            setSaveError('');
          }}
          empty={`No ${levelLabel.toLowerCase()} yet.`}
        />
      )}

      {editing ? (
        <Drawer
          title={
            editing.id
              ? `Edit ${levelLabel.replace(/s$/, '')}`
              : addLabel
          }
          value={editing}
          onChange={setEditing}
          onClose={() => setEditing(null)}
          onSave={submit}
          extra={<ErrorBar error={saveError} />}
          fields={[
            ...(level === 'verticals'
              ? [
                  { name: 'name' },
                  { name: 'code' },
                ]
              : []),

            ...(level === 'domains'
              ? [
                  { name: 'name' },
                  { name: 'code' },
                  {
                    name: 'vertical_id',
                    kind: 'select' as const,
                    options: activeVerticals.map(
                      (row) => String(row.id),
                    ),
                    labels: verticalName,
                  },
                ]
              : []),

            ...(level === 'services'
              ? [
                  { name: 'name' },
                  { name: 'code' },
                  {
                    name: 'domain_id',
                    kind: 'select' as const,
                    options: activeDomains.map(
                      (row) => String(row.id),
                    ),
                    labels: domainName,
                  },
                  { name: 'default_due_days' },
                ]
              : []),

            ...(level === 'requirement-sets'
              ? [
                  {
                    name: 'service_id',
                    kind: 'select' as const,
                    options: activeServices.map(
                      (row) => String(row.id),
                    ),
                    labels: serviceName,
                  },
                  { name: 'name' },
                  { name: 'version_number' },
                  {
                    name: 'effective_from',
                    kind: 'date' as const,
                  },
                  {
                    name: 'effective_until',
                    kind: 'date' as const,
                  },
                  {
                    name: 'status',
                    kind: 'select' as const,
                    options: [
                      'DRAFT',
                      'ACTIVE',
                      'RETIRED',
                    ],
                  },
                ]
              : []),

            ...(level === 'document-requirements'
              ? [
                  {
                    name: 'service_id',
                    kind: 'select' as const,
                    options: activeServices.map(
                      (row) => String(row.id),
                    ),
                    labels: serviceName,
                  },
                  {
                    name: 'requirement_set_id',
                    kind: 'select' as const,
                    options: availableSets.map(
                      (row) => String(row.id),
                    ),
                    labels: setName,
                  },
                  { name: 'name' },
                  { name: 'code' },
                  {
                    name: 'category',
                    kind: 'select' as const,
                    options: DOCUMENT_CATEGORIES,
                  },
                  { name: 'display_order' },
                  {
                    name: 'mandatory',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'financial_year_required',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'assessment_year_required',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'filing_period_required',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'expiry_applicable',
                    kind: 'checkbox' as const,
                  },
                  { name: 'expiry_reminder_days' },
                  {
                    name: 'requires_review',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'allow_multiple_versions',
                    kind: 'checkbox' as const,
                  },
                  {
                    name: 'allow_multiple_files',
                    kind: 'checkbox' as const,
                  },
                  { name: 'allowed_extensions' },
                  { name: 'maximum_file_size_mb' },
                  {
                    name: 'is_active',
                    kind: 'checkbox' as const,
                  },
                ]
              : []),

            {
              name: 'description',
              kind: 'textarea',
            },

            ...(level === 'verticals' ||
            level === 'domains' ||
            level === 'services'
              ? [
                  {
                    name: 'status',
                    kind: 'select' as const,
                    options: ['ACTIVE', 'INACTIVE'],
                  },
                ]
              : []),
          ]}
        />
      ) : null}
      <QACataloguePanel services={activeServices} />
    </>
  );
}
