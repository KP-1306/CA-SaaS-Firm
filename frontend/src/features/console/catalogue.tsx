import type * as React from 'react';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  list,
  save,
} from './api';

import {
  DOCUMENT_CATEGORIES,
} from './types';

import type {
  Row,
} from './types';

import {
  Chip,
  Drawer,
  ErrorBar,
  Loading,
} from './ui';

import {
  QACataloguePanel,
} from './qa';


interface ListState {
  rows: Row[];
  error: string;
  loading: boolean;
  reload: () => void;
}


type ServiceTab =
  | 'overview'
  | 'documents'
  | 'qa';


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


function rowName(
  row: Row | null | undefined,
  fallback = '—',
): string {
  return String(row?.name ?? fallback);
}


function isActive(row: Row): boolean {
  return row.status === 'ACTIVE';
}


function sameId(
  left: unknown,
  right: unknown,
): boolean {
  return String(left ?? '') === String(right ?? '');
}


function CatalogueButton({
  title,
  detail,
  selected,
  status,
  onClick,
}: {
  title: string;
  detail?: string | undefined;
  selected: boolean;
  status?: unknown;
  onClick: () => void;
}): React.JSX.Element {
  return (
    <button
      type="button"
      className={`cx-catalogue-choice ${
        selected
          ? 'is-selected'
          : ''
      }`}
      onClick={onClick}
    >
      <span className="cx-catalogue-choice-main">
        <strong>{title}</strong>

        {detail ? (
          <span>{detail}</span>
        ) : null}
      </span>

      {status ? (
        <Chip
          value={String(status)}
          tone={
            status === 'ACTIVE'
              ? 'ok'
              : 'danger'
          }
        />
      ) : null}
    </button>
  );
}


export function CatalogueArea(): React.JSX.Element {
  const verticals = useList('verticals');
  const domains = useList('domains');
  const services = useList('services');

  const requirementSets = useList(
    'service-document-requirement-sets',
  );

  const requirements = useList(
    'service-document-requirements',
  );

  const [verticalId, setVerticalId] =
    useState('');

  const [domainId, setDomainId] =
    useState('');

  const [serviceId, setServiceId] =
    useState('');

  const [serviceTab, setServiceTab] =
    useState<ServiceTab>('overview');

  const [editingCatalogue, setEditingCatalogue] =
    useState<{
      kind: 'vertical' | 'domain' | 'service';
      row: Row;
    } | null>(null);

  const [editingDocument, setEditingDocument] =
    useState<Row | null>(null);

  const [saveError, setSaveError] =
    useState('');


  const activeVerticals = useMemo(
    () =>
      verticals.rows.filter(isActive),
    [verticals.rows],
  );


  const visibleDomains = useMemo(
    () =>
      domains.rows.filter(
        (row) =>
          sameId(
            row.vertical_id,
            verticalId,
          ),
      ),
    [
      domains.rows,
      verticalId,
    ],
  );


  const visibleServices = useMemo(
    () =>
      services.rows.filter(
        (row) =>
          sameId(
            row.domain_id,
            domainId,
          ),
      ),
    [
      services.rows,
      domainId,
    ],
  );


  const selectedVertical =
    verticals.rows.find(
      (row) =>
        sameId(
          row.id,
          verticalId,
        ),
    ) ?? null;


  const selectedDomain =
    domains.rows.find(
      (row) =>
        sameId(
          row.id,
          domainId,
        ),
    ) ?? null;


  const selectedService =
    services.rows.find(
      (row) =>
        sameId(
          row.id,
          serviceId,
        ),
    ) ?? null;


  const serviceSets = useMemo(
    () =>
      requirementSets.rows
        .filter(
          (row) =>
            sameId(
              row.service_id,
              serviceId,
            ),
        )
        .sort(
          (left, right) =>
            Number(
              right.version_number ?? 0,
            ) -
            Number(
              left.version_number ?? 0,
            ),
        ),
    [
      requirementSets.rows,
      serviceId,
    ],
  );


  const currentRequirementSet =
    serviceSets.find(
      (row) =>
        row.status === 'ACTIVE',
    ) ??
    serviceSets[0] ??
    null;


  const serviceDocuments = useMemo(
    () =>
      requirements.rows
        .filter(
          (row) =>
            sameId(
              row.service_id,
              serviceId,
            ) &&
            (
              !currentRequirementSet ||
              sameId(
                row.requirement_set_id,
                currentRequirementSet.id,
              )
            )
        )
        .sort(
          (left, right) =>
            Number(
              left.display_order ?? 0,
            ) -
            Number(
              right.display_order ?? 0,
            ),
        ),
    [
      requirements.rows,
      serviceId,
      currentRequirementSet,
    ],
  );


  const allLoading =
    verticals.loading ||
    domains.loading ||
    services.loading;


  const allError =
    verticals.error ||
    domains.error ||
    services.error;


  const clearService = (): void => {
    setServiceId('');
    setServiceTab('overview');
    setEditingDocument(null);
    setSaveError('');
  };


  const selectVertical = (
    row: Row,
  ): void => {
    setVerticalId(String(row.id));
    setDomainId('');
    clearService();
  };


  const selectDomain = (
    row: Row,
  ): void => {
    setDomainId(String(row.id));
    clearService();
  };


  const openService = (
    row: Row,
  ): void => {
    setServiceId(String(row.id));
    setServiceTab('overview');
    setEditingDocument(null);
    setSaveError('');
  };


  const saveCatalogue = (): void => {
    if (!editingCatalogue) return;

    const {
      kind,
      row,
    } = editingCatalogue;

    const resource =
      kind === 'vertical'
        ? 'verticals'
        : kind === 'domain'
          ? 'domains'
          : 'services';

    save(resource, row)
      .then(() => {
        setEditingCatalogue(null);
        setSaveError('');

        if (kind === 'vertical') {
          verticals.reload();
        }

        if (kind === 'domain') {
          domains.reload();
        }

        if (kind === 'service') {
          services.reload();
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


  const saveDocument = (): void => {
    if (!editingDocument) return;

    save(
      'service-document-requirements',
      editingDocument,
    )
      .then(() => {
        setEditingDocument(null);
        setSaveError('');
        requirements.reload();
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


  const addVertical = (): void => {
    setEditingCatalogue({
      kind: 'vertical',
      row: {
        name: '',
        code: '',
        description: '',
        status: 'ACTIVE',
      },
    });
  };


  const addDomain = (): void => {
    if (!selectedVertical) return;

    setEditingCatalogue({
      kind: 'domain',
      row: {
        name: '',
        code: '',
        vertical_id:
          selectedVertical.id,
        description: '',
        status: 'ACTIVE',
      },
    });
  };


  const addService = (): void => {
    if (!selectedDomain) return;

    setEditingCatalogue({
      kind: 'service',
      row: {
        name: '',
        code: '',
        domain_id:
          selectedDomain.id,
        description: '',
        default_due_days: '',
        status: 'ACTIVE',
      },
    });
  };


  const addDocument = (): void => {
    if (
      !selectedService ||
      !currentRequirementSet
    ) {
      return;
    }

    setEditingDocument({
      service_id:
        selectedService.id,

      requirement_set_id:
        currentRequirementSet.id,

      name: '',
      code: '',
      category: 'OTHER',
      mandatory: true,
      display_order:
        (serviceDocuments.length + 1) * 10,
      financial_year_required: false,
      assessment_year_required: false,
      filing_period_required: false,
      expiry_applicable: false,
      expiry_reminder_days: '',
      requires_review: true,
      description: '',
    });
  };


  if (allLoading) {
    return <Loading />;
  }


  if (selectedService) {
    return (
      <section className="cx-service-workspace">
        <div className="cx-service-workspace-head">
          <button
            type="button"
            className="cx-btn subtle"
            onClick={clearService}
          >
            ← Back to Services
          </button>

          <div>
            <div className="cx-eyebrow">
              {rowName(selectedVertical)}
              {'  /  '}
              {rowName(selectedDomain)}
            </div>

            <h2>
              {rowName(selectedService)}
            </h2>
          </div>

          <Chip
            value={String(
              selectedService.status ??
              'ACTIVE',
            )}
            tone={
              selectedService.status ===
              'ACTIVE'
                ? 'ok'
                : 'danger'
            }
          />
        </div>

        <div className="cx-service-tabs">
          {(
            [
              ['overview', 'Overview'],
              ['documents', 'Documents'],
              ['qa', 'QA Checklist'],
            ] as [
              ServiceTab,
              string,
            ][]
          ).map(([key, title]) => (
            <button
              key={key}
              type="button"
              className={`cx-btn ${
                serviceTab === key
                  ? ''
                  : 'subtle'
              }`}
              onClick={() =>
                setServiceTab(key)
              }
            >
              {title}
            </button>
          ))}
        </div>

        {serviceTab === 'overview' ? (
          <div className="cx-service-overview">
            <div className="cx-service-summary-card">
              <div className="cx-eyebrow">
                SERVICE
              </div>

              <h3>
                {rowName(selectedService)}
              </h3>

              <p>
                {String(
                  selectedService.description ??
                  'No description provided.',
                )}
              </p>

              <dl className="cx-service-facts">
                <div>
                  <dt>Vertical</dt>
                  <dd>
                    {rowName(selectedVertical)}
                  </dd>
                </div>

                <div>
                  <dt>Domain</dt>
                  <dd>
                    {rowName(selectedDomain)}
                  </dd>
                </div>

                <div>
                  <dt>Code</dt>
                  <dd>
                    {String(
                      selectedService.code ??
                      '—',
                    )}
                  </dd>
                </div>

                <div>
                  <dt>Default due</dt>
                  <dd>
                    {selectedService.default_due_days
                      ? `${String(
                          selectedService.default_due_days,
                        )} days`
                      : 'Not configured'}
                  </dd>
                </div>

                <div>
                  <dt>Documents</dt>
                  <dd>
                    {serviceDocuments.length}
                  </dd>
                </div>

                <div>
                  <dt>Checklist version</dt>
                  <dd>
                    {currentRequirementSet
                      ? `V${String(
                          currentRequirementSet.version_number ??
                          1,
                        )}`
                      : 'Not configured'}
                  </dd>
                </div>
              </dl>

              <button
                type="button"
                className="cx-btn"
                onClick={() =>
                  setEditingCatalogue({
                    kind: 'service',
                    row: {
                      ...selectedService,
                    },
                  })
                }
              >
                Edit service
              </button>
            </div>
          </div>
        ) : null}


        {serviceTab === 'documents' ? (
          <div className="cx-service-documents">
            <div className="cx-section-head">
              <div>
                <h3>
                  Required Documents
                </h3>

                <p className="cx-muted">
                  Documents Vridhi should request
                  for this service.
                </p>
              </div>

              {currentRequirementSet ? (
                <button
                  type="button"
                  className="cx-btn"
                  onClick={addDocument}
                >
                  Add document
                </button>
              ) : null}
            </div>

            <ErrorBar
              error={
                requirementSets.error ||
                requirements.error
              }
            />

            {!currentRequirementSet ? (
              <div className="cx-empty-state">
                <strong>
                  Document checklist is not configured.
                </strong>

                <span>
                  No versioned requirement set exists
                  for this service yet.
                </span>
              </div>
            ) : serviceDocuments.length === 0 ? (
              <div className="cx-empty-state">
                No required documents yet.
              </div>
            ) : (
              <div className="cx-document-catalogue-list">
                {serviceDocuments.map(
                  (document) => (
                    <button
                      key={String(document.id)}
                      type="button"
                      className="cx-document-catalogue-row"
                      onClick={() => {
                        setEditingDocument({
                          ...document,
                        });
                        setSaveError('');
                      }}
                    >
                      <span>
                        <strong>
                          {String(document.name)}
                        </strong>

                        <small>
                          {String(
                            document.category ??
                            'OTHER',
                          )}
                        </small>
                      </span>

                      <span className="cx-document-catalogue-meta">
                        {document.mandatory
                          ? 'Required'
                          : 'Conditional'}
                      </span>
                    </button>
                  ),
                )}
              </div>
            )}

            {currentRequirementSet ? (
              <div className="cx-internal-note">
                Checklist version{' '}
                V{String(
                  currentRequirementSet.version_number ??
                  1,
                )}
                {' • '}
                managed automatically for
                history and audit.
              </div>
            ) : null}
          </div>
        ) : null}


        {serviceTab === 'qa' ? (
          <div className="cx-service-qa">
            <QACataloguePanel
              services={[selectedService]}
            />
          </div>
        ) : null}


        {editingCatalogue ? (
          <Drawer
            title="Edit service"
            value={editingCatalogue.row}
            onChange={(row) =>
              setEditingCatalogue({
                ...editingCatalogue,
                row,
              })
            }
            onClose={() => {
              setEditingCatalogue(null);
              setSaveError('');
            }}
            onSave={saveCatalogue}
            extra={
              <ErrorBar error={saveError} />
            }
            fields={[
              { name: 'name' },
              { name: 'code' },
              {
                name: 'domain_id',
                kind: 'select',
                options:
                  domains.rows.map(
                    (row) =>
                      String(row.id),
                  ),
                labels: (id: unknown) =>
                  rowName(
                    domains.rows.find(
                      (row) =>
                        sameId(
                          row.id,
                          id,
                        ),
                    ),
                  ),
              },
              {
                name: 'default_due_days',
              },
              {
                name: 'description',
                kind: 'textarea',
              },
              {
                name: 'status',
                kind: 'select',
                options: [
                  'ACTIVE',
                  'INACTIVE',
                ],
              },
            ]}
          />
        ) : null}


        {editingDocument ? (
          <Drawer
            title={
              editingDocument.id
                ? 'Edit document'
                : 'Add document'
            }
            value={editingDocument}
            onChange={setEditingDocument}
            onClose={() => {
              setEditingDocument(null);
              setSaveError('');
            }}
            onSave={saveDocument}
            extra={
              <ErrorBar error={saveError} />
            }
            fields={[
              { name: 'name' },
              { name: 'code' },
              {
                name: 'category',
                kind: 'select',
                options:
                  DOCUMENT_CATEGORIES,
              },
              {
                name: 'display_order',
              },
              {
                name: 'mandatory',
                kind: 'checkbox',
              },
              {
                name: 'requires_review',
                kind: 'checkbox',
              },
              {
                name: 'expiry_applicable',
                kind: 'checkbox',
              },
              {
                name: 'description',
                kind: 'textarea',
              },
            ]}
          />
        ) : null}
      </section>
    );
  }


  return (
    <section className="cx-catalogue-browser">
      <div className="cx-catalogue-intro">
        <div>
          <div className="cx-eyebrow">
            SERVICE CATALOGUE
          </div>

          <h2>
            Services
          </h2>

          <p>
            Choose a Vertical, then a Domain,
            then the Service you want to configure.
          </p>
        </div>
      </div>

      <ErrorBar error={allError} />

      <div className="cx-catalogue-columns">

        <section className="cx-catalogue-column">
          <div className="cx-section-head">
            <div>
              <div className="cx-step-number">
                1
              </div>

              <h3>Vertical</h3>
            </div>

            <button
              type="button"
              className="cx-btn subtle"
              onClick={addVertical}
            >
              + Add
            </button>
          </div>

          <div className="cx-catalogue-choice-list">
            {verticals.rows.map(
              (row) => (
                <CatalogueButton
                  key={String(row.id)}
                  title={rowName(row)}
                  detail={String(
                    row.code ?? '',
                  )}
                  selected={sameId(
                    row.id,
                    verticalId,
                  )}
                  status={row.status}
                  onClick={() =>
                    selectVertical(row)
                  }
                />
              ),
            )}
          </div>

          {selectedVertical ? (
            <button
              type="button"
              className="cx-link-button"
              onClick={() =>
                setEditingCatalogue({
                  kind: 'vertical',
                  row: {
                    ...selectedVertical,
                  },
                })
              }
            >
              Edit selected vertical
            </button>
          ) : null}
        </section>


        <section className="cx-catalogue-column">
          <div className="cx-section-head">
            <div>
              <div className="cx-step-number">
                2
              </div>

              <h3>Domain</h3>
            </div>

            {selectedVertical ? (
              <button
                type="button"
                className="cx-btn subtle"
                onClick={addDomain}
              >
                + Add
              </button>
            ) : null}
          </div>

          {!selectedVertical ? (
            <div className="cx-empty-state">
              Select a Vertical first.
            </div>
          ) : visibleDomains.length === 0 ? (
            <div className="cx-empty-state">
              No Domains under this Vertical.
            </div>
          ) : (
            <div className="cx-catalogue-choice-list">
              {visibleDomains.map(
                (row) => (
                  <CatalogueButton
                    key={String(row.id)}
                    title={rowName(row)}
                    detail={String(
                      row.code ?? '',
                    )}
                    selected={sameId(
                      row.id,
                      domainId,
                    )}
                    status={row.status}
                    onClick={() =>
                      selectDomain(row)
                    }
                  />
                ),
              )}
            </div>
          )}

          {selectedDomain ? (
            <button
              type="button"
              className="cx-link-button"
              onClick={() =>
                setEditingCatalogue({
                  kind: 'domain',
                  row: {
                    ...selectedDomain,
                  },
                })
              }
            >
              Edit selected domain
            </button>
          ) : null}
        </section>


        <section className="cx-catalogue-column">
          <div className="cx-section-head">
            <div>
              <div className="cx-step-number">
                3
              </div>

              <h3>Service</h3>
            </div>

            {selectedDomain ? (
              <button
                type="button"
                className="cx-btn subtle"
                onClick={addService}
              >
                + Add
              </button>
            ) : null}
          </div>

          {!selectedDomain ? (
            <div className="cx-empty-state">
              Select a Domain first.
            </div>
          ) : visibleServices.length === 0 ? (
            <div className="cx-empty-state">
              No Services under this Domain.
            </div>
          ) : (
            <div className="cx-catalogue-choice-list">
              {visibleServices.map(
                (row) => (
                  <CatalogueButton
                    key={String(row.id)}
                    title={rowName(row)}
                    detail={
                      row.default_due_days
                        ? `${String(
                            row.default_due_days,
                          )} day default`
                        : undefined
                    }
                    selected={false}
                    status={row.status}
                    onClick={() =>
                      openService(row)
                    }
                  />
                ),
              )}
            </div>
          )}
        </section>
      </div>


      {editingCatalogue ? (
        <Drawer
          title={
            editingCatalogue.row.id
              ? `Edit ${editingCatalogue.kind}`
              : `Add ${editingCatalogue.kind}`
          }
          value={editingCatalogue.row}
          onChange={(row) =>
            setEditingCatalogue({
              ...editingCatalogue,
              row,
            })
          }
          onClose={() => {
            setEditingCatalogue(null);
            setSaveError('');
          }}
          onSave={saveCatalogue}
          extra={
            <ErrorBar error={saveError} />
          }
          fields={[
            { name: 'name' },
            { name: 'code' },

            ...(editingCatalogue.kind ===
            'domain'
              ? [
                  {
                    name: 'vertical_id',
                    kind: 'select' as const,
                    options:
                      activeVerticals.map(
                        (row) =>
                          String(row.id),
                      ),
                    labels: (
                      id: unknown,
                    ) =>
                      rowName(
                        verticals.rows.find(
                          (row) =>
                            sameId(
                              row.id,
                              id,
                            ),
                        ),
                      ),
                  },
                ]
              : []),

            ...(editingCatalogue.kind ===
            'service'
              ? [
                  {
                    name: 'domain_id',
                    kind: 'select' as const,
                    options:
                      domains.rows.map(
                        (row) =>
                          String(row.id),
                      ),
                    labels: (
                      id: unknown,
                    ) =>
                      rowName(
                        domains.rows.find(
                          (row) =>
                            sameId(
                              row.id,
                              id,
                            ),
                        ),
                      ),
                  },
                  {
                    name:
                      'default_due_days',
                  },
                ]
              : []),

            {
              name: 'description',
              kind: 'textarea',
            },
            {
              name: 'status',
              kind: 'select',
              options: [
                'ACTIVE',
                'INACTIVE',
              ],
            },
          ]}
        />
      ) : null}
    </section>
  );
}
