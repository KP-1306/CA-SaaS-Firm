// Central internal-plane API client. Dev headers live here only (charter section 7).
const API_BASE = '/api/v1';

const DEV_TENANT = '11111111-1111-1111-1111-111111111111';
const DEV_PRINCIPAL = '22222222-2222-2222-2222-222222222222';

function headers(json = true): Record<string, string> {
  const base: Record<string, string> = {
    'X-Tenant-ID': localStorage.getItem('tenantId') ?? DEV_TENANT,
    'X-Principal-ID': localStorage.getItem('principalId') ?? DEV_PRINCIPAL,
  };
  if (json) base['Content-Type'] = 'application/json';
  return base;
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
        const label = FIELD_LABELS[key] ?? key.replace(/_/g, ' ');
        const msg = Array.isArray(val) ? String(val[0]) : String(val);
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

async function fail(res: Response): Promise<never> {
  throw new Error(translateError(await res.text()));
}

export async function list(resource: string, params: Record<string, string | undefined> = {}): Promise<Row[]> {
  const res = await fetch(`${API_BASE}/${resource}/${qs(params)}`, { headers: headers() });
  if (!res.ok) return fail(res);
  return (await res.json()) as Row[];
}

export async function save(resource: string, value: Row): Promise<Row> {
  const id = value.id as string | undefined;
  const res = await fetch(`${API_BASE}/${resource}/${id ? `${id}/` : ''}`, {
    method: id ? 'PATCH' : 'POST',
    headers: headers(),
    body: JSON.stringify(value),
  });
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function remove(resource: string, id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${resource}/${id}/`, { method: 'DELETE', headers: headers() });
  if (!res.ok && res.status !== 404) return fail(res);
}

export async function act(resource: string, id: string, verb: string, body: Row = {}): Promise<Row> {
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function upload(resource: string, id: string, verb: string, file: File): Promise<Row> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, {
    method: 'POST',
    headers: headers(false),
    body: form,
  });
  if (!res.ok) return fail(res);
  return (await res.json()) as Row;
}

export async function uploadMany(resource: string, id: string, verb: string, files: File[], extra: Record<string, string> = {}): Promise<Row[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  for (const [key, value] of Object.entries(extra)) form.append(key, value);
  const res = await fetch(`${API_BASE}/${resource}/${id}/${verb}/`, { method: 'POST', headers: headers(false), body: form });
  if (!res.ok) return fail(res);
  return (await res.json()) as Row[];
}
