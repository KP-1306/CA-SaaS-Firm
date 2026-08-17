/**
 * V1.2 Save / Save & Close behavior contract tests.
 * Tests L-Q correspond to Command_6 §12.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { persistWorkItem } from '../src/features/console/work';

function okFetch(): ReturnType<typeof vi.fn> {
  const fn = vi.fn(async () =>
    new Response(JSON.stringify({ id: 'w1', status: 'IN_PROGRESS' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fn);
  return fn;
}

function failFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Validation failed.' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  );
}

describe('Save / Save & Close (Requirements 3 / Tests L-O)', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

  it('TEST L: successful Save keeps drawer open and calls onSaved', async () => {
    okFetch();
    let closed = false; let saved = false; let error = '';
    await persistWorkItem(
      { id: 'w1', title: 'Work' },
      () => { closed = true; },
      (m) => { error = m; },
      () => {},
      null,
      false,           // closeAfterSave = false => Save
      () => { saved = true; },
    );
    expect(error).toBe('');
    expect(closed).toBe(false);
    expect(saved).toBe(true);
  });

  it('TEST M: successful Save & Close closes drawer', async () => {
    okFetch();
    let closed = false; let error = '';
    await persistWorkItem(
      { id: 'w1', title: 'Work' },
      () => { closed = true; },
      (m) => { error = m; },
      () => {},
      null,
      true,            // closeAfterSave = true => Save & Close
    );
    expect(error).toBe('');
    expect(closed).toBe(true);
  });

  it('TEST N: Save failure keeps drawer open and surfaces error', async () => {
    failFetch();
    let closed = false; let saved = false; let error = '';
    await persistWorkItem(
      { id: 'w1', title: 'Work' },
      () => { closed = true; },
      (m) => { error = m; },
      () => {},
      null,
      false,
      () => { saved = true; },
    );
    expect(closed).toBe(false);
    expect(saved).toBe(false);
    expect(error).not.toBe('');
  });

  it('TEST O: Save & Close failure keeps drawer open', async () => {
    failFetch();
    let closed = false; let error = '';
    await persistWorkItem(
      { id: 'w1', title: 'Work' },
      () => { closed = true; },
      (m) => { error = m; },
      () => {},
      null,
      true,
    );
    expect(closed).toBe(false);
    expect(error).not.toBe('');
  });
});

describe('Workflow API contract (Test P)', () => {
  beforeEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

  it('TEST P: workflow action invokes the dedicated endpoint, not generic PATCH only', async () => {
    const fn = okFetch();
    let closed = false;
    await persistWorkItem(
      { id: 'w1', title: 'Work', can_edit: true },
      () => { closed = true; },
      () => {},
      () => {},
      { kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' } as never,
      false,           // even with Save-style flag, workflow action concludes
    );
    expect(closed).toBe(true);
    const urls = fn.mock.calls.map((c) => String(c[0]));
    // The dedicated submit_for_review endpoint must be called.
    expect(urls.some((u) => u.includes('submit_for_review'))).toBe(true);
  });

  it('legacy call (no closeAfterSave arg) still closes drawer on success', async () => {
    okFetch();
    let closed = false;
    // call without closeAfterSave - backward compat, defaults to close
    await persistWorkItem(
      { id: 'w1', title: 'Work' },
      () => { closed = true; },
      () => {},
      () => {},
    );
    expect(closed).toBe(true);
  });
});
