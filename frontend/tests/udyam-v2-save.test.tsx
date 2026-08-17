import { describe, expect, it, vi, beforeEach } from 'vitest';
import { persistWorkItem } from '../src/features/console/work';

// V2 frontend regression: the generic Work save payload must no longer strip
// udyam_* process-owned keys.  The server serializer owns preservation, so the
// client sends operational_data as-is.  (Item 7 of the V2 frontend matrix.)

function captureFetch(): { calls: Array<{ url: string; init: RequestInit }> } {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fn = vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url: String(url), init });
    return new Response(JSON.stringify({ id: 'w1' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fn);
  return { calls };
}

describe('V2 generic Work save payload', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('does not strip udyam_* process-owned keys from the save payload', async () => {
    const { calls } = captureFetch();

    const editing = {
      id: 'w1',
      title: 'Udyam work',
      operational_data: {
        filing_status: 'Filed',
        udyam_application_reference: 'UDYAM-REF-001',
        udyam_submission_date: '2026-08-12',
        udyam_submission_time: '14:30',
      },
    };

    await persistWorkItem(
      editing,
      () => {},
      () => {},
      () => {},
      null,
    );

    // Find the PATCH to work-items.
    const patch = calls.find(
      (c) => (c.init.method === 'PATCH') && c.url.includes('/work-items/'),
    );
    expect(patch).toBeTruthy();

    const body = JSON.parse(String(patch?.init.body ?? '{}'));
    const opdata = body.operational_data ?? {};

    // The udyam_* keys must still be present in the transmitted payload
    // (the server ignores them for authority; the client no longer strips).
    expect(opdata.filing_status).toBe('Filed');
    expect(opdata).toHaveProperty('udyam_application_reference');
    expect(opdata).toHaveProperty('udyam_submission_date');
    expect(opdata).toHaveProperty('udyam_submission_time');
  });
});
