// Central internal-plane API client. Dev headers live here only (charter section 7).
const API_BASE = '/api/v1';

let csrfToken = '';

const DEV_TENANT = '11111111-1111-1111-1111-111111111111';
const DEV_PRINCIPAL = '22222222-2222-2222-2222-222222222222';

function developmentIdentity(): {
  tenantId: string;
  principalId: string;
} {
  const storedTenant =
    localStorage.getItem('tenantId');

  const storedPrincipal =
    localStorage.getItem('principalId');

  const tenantId =
    storedTenant === DEV_TENANT
      ? storedTenant
      : DEV_TENANT;

  const principalId =
    storedPrincipal === DEV_PRINCIPAL
      ? storedPrincipal
      : DEV_PRINCIPAL;

  if (storedTenant !== tenantId) {
    localStorage.setItem(
      'tenantId',
      tenantId,
    );
  }

  if (storedPrincipal !== principalId) {
    localStorage.setItem(
      'principalId',
      principalId,
    );
  }

  return {
    tenantId,
    principalId,
  };
}

function cookieValue(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
}

function headers(json = true): Record<string, string> {
  const identity = developmentIdentity();

  const base: Record<string, string> = {
    'X-Tenant-ID': identity.tenantId,
    'X-Principal-ID': identity.principalId,
  };
  const csrf = csrfToken || cookieValue('csrftoken');
  if (csrf) base['X-CSRFToken'] = csrf;
  if (json) base['Content-Type'] = 'application/json';
  return base;
}

function options(init: RequestInit = {}): RequestInit {
  return {
    credentials: 'include',
    ...init,
    headers: {
      ...headers(!(init.body instanceof FormData)),
      ...(init.headers ?? {}),
    },
  };
}

export type Row = Record<string, unknown>;

const FIELD_LABELS: Record<string, string> = {
  domain_id: 'Domain',
  vertical_id: 'Vertical',
  service_id: 'Service',
  client_id: 'Client',
  owner_user_id: 'Owner',
  reviewer_user_id: 'Reviewer',
  legal_name: 'Legal name',
  due_date: 'Due date',
  pan: 'PAN',
  gstin: 'GSTIN',
};

const fieldLabel = (key: string): string => {
  const explicit = FIELD_LABELS[key];

  if (explicit) return explicit;

  const fallback = key.replace(/_/g, ' ');

  return fallback
    ? fallback.charAt(0).toUpperCase() + fallback.slice(1)
    : fallback;
};

// Turn a DRF error body into one readable sentence (charter section 6).
export function translateError(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed === 'string') return parsed;
    if (parsed && typeof parsed === 'object') {
      const obj = parsed as Record<string, unknown>;
      if (typeof obj.detail === 'string') return obj.detail;
      const parts: string[] = [];
      for (const [key, val] of Object.entries(obj)) {
        const label = fieldLabel(key);
        const formatValue = (value: unknown): string => {
          if (Array.isArray(value)) {
            return value.map(formatValue).filter(Boolean).join(', ');
          }

          if (
            value &&
            typeof value === 'object'
          ) {
            return Object.entries(
              value as Record<string, unknown>,
            )
              .map(([nestedKey, nestedValue]) => {
                const nestedMessage =
                  formatValue(nestedValue);

                return nestedMessage
                  ? `${fieldLabel(nestedKey)}: ${nestedMessage}`
                  : '';
              })
              .filter(Boolean)
              .join('; ');
          }

          return String(value ?? '');
        };

        const msg = formatValue(val);
        if (/valid uuid/i.test(msg)) parts.push(`Please select a valid ${label}.`);
        else parts.push(`${label}: ${msg}`);
      }
      if (parts.length) return parts.join(' ');
    }
  } catch {
    // not JSON "" fall through
  }
  return raw.length > 200 ? 'The request could not be completed. Please check your input.' : raw;
}

function qs(params: Record<string, string | undefined>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: Row | null;

  constructor(
    message: string,
    status: number,
    payload: Row | null,
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.payload = payload;
  }
}

async function fail(res: Response): Promise<never> {
  const raw = await res.text();

  let payload: Row | null = null;

  try {
    const parsed = JSON.parse(raw) as unknown;

    if (
      parsed !== null &&
      typeof parsed === 'object' &&
      !Array.isArray(parsed)
    ) {
      payload = parsed as Row;
    }
  } catch {
    payload = null;
  }

  const message =
    payload && typeof payload.detail === 'string'
      ? payload.detail
      : translateError(raw);

  throw new ApiRequestError(
    message,
    res.status,
    payload,
  );
}

export async function list(resource: string, params: Record<string, string | undefined> = {}): Promise<Row[]> {
  const res = await fetch(`${API_BASE}/${resource}/${qs(params)}`, options());
  if (!res.ok) return fail(res);
  return (await res.json()) as Row[];
}

export async function getObject(path: string, params: Record<string, string | undefined> = {}): Promise<Row> {
  const res = await fetch(`${API_BASE}/${path}/${qs(params)}`, options());
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function save(resource: string, value: Row): Promise<Row> {
  const id = value.id as string | undefined;
  const res = await fetch(`${API_BASE}/${resource}/${id ? `${id}/` : ''}`, options({
    method: id ? 'PATCH' : 'POST',
    body: JSON.stringify(value),
  }));
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function remove(resource: string, id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${resource}/${id}/`, options({ method: 'DELETE' }));
  if (!res.ok && res.status !== 404) return fail(res);
}

export async function collectionAct(
  resource: string,
  verb: string,
  body: Row = {},
): Promise<Row> {
  const res = await fetch(
    `${API_BASE}/${resource}/${verb}/`,
    options({
      method: 'POST',
      body: JSON.stringify(body),
    }),
  );

  if (!res.ok) return fail(res);

  return (await res.json()) as Row;
}
export async function act(resource: string, id: string, verb: string, body: Row = {}): Promise<Row> {
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, options({
    method: 'POST',
    body: JSON.stringify(body),
  }));
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function upload(resource: string, id: string, verb: string, file: File): Promise<Row> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, options({
    method: 'POST',
    body: form,
  }));
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function uploadMany(resource: string, id: string, verb: string, files: File[], extra: Record<string, string> = {}): Promise<Row[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  for (const [key, value] of Object.entries(extra)) form.append(key, value);
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, options({ method: 'POST', body: form }));
  if (!res.ok) return fail(res);
  return (await res.json()) as Row[];
}

export async function requestObject(
  path: string,
  init: RequestInit = {},
): Promise<Row> {
  const res = await fetch(`${API_BASE}/${path}`, options(init));
  if (!res.ok) return fail(res);
  if (res.status === 204) return {};

  const row = (await res.json()) as Row;

  if (
    path === 'auth/login/' &&
    typeof row.csrf_token === 'string'
  ) {
    csrfToken = row.csrf_token;
  }

  return row;
}

export async function requestRows(
  path: string,
  params: Record<string, string | undefined> = {},
): Promise<Row[]> {
  const res = await fetch(`${API_BASE}/${path}${qs(params)}`, options());
  if (!res.ok) return fail(res);
  return (await res.json()) as Row[];
}

export async function postPath(path: string, body: Row = {}): Promise<Row> {
  return requestObject(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function deletePath(path: string, body?: Row): Promise<Row> {
  const init: RequestInit = { method: 'DELETE' };

  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  return requestObject(path, init);
}
