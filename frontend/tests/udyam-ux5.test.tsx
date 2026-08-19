import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  SearchableClientSelect,
  UdyamActionShell,
  UdyamExternalActions,
} from '../src/features/console/work';

/*
 * UX5 focused frontend tests.
 *
 * Change 3 - Submit Application confirmation
 * Change 4 - Query one-active-action confirmation
 * Change 5 - Collapsible action panel
 * Change 2 - Searchable client selector + Add New Client
 *
 * These prove NEW behaviour and that the confirmation gate never mutates
 * backend state until the analyst explicitly confirms.
 */

type FetchCall = { url: string; method: string; body: string };

function stubFetch(
  handler?: (url: string, init: RequestInit) => unknown,
): { calls: FetchCall[] } {
  const calls: FetchCall[] = [];
  const fn = vi.fn(async (url: string, init: RequestInit) => {
    calls.push({
      url: String(url),
      method: String(init?.method ?? 'GET'),
      body: String(init?.body ?? ''),
    });
    const custom = handler ? handler(String(url), init) : undefined;
    // useList expects an array; detail/act expect an object. Return [] for
    // GET list calls and {} otherwise unless the handler overrides.
    const isListGet =
      String(init?.method ?? 'GET') === 'GET' && !/\/[a-f0-9-]{36}\//.test(String(url));
    return new Response(
      JSON.stringify(custom ?? (isListGet ? [] : { id: 'w1' })),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    );
  });
  vi.stubGlobal('fetch', fn);
  return { calls };
}

const SUBMIT_ITEM = {
  id: 'w1',
  title: 'Udyam',
  status: 'IN_PROGRESS',
  can_edit: true,
  operational_data: {},
};

const SUBMIT_STATE = {
  current_step: { code: 'SUBMIT_APPLICATION' },
} as unknown as Parameters<typeof UdyamExternalActions>[0]['processState'];

describe('UX5 Change 3 - Submit Application explicit confirmation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('selecting the action does not call the backend; confirm calls it once', async () => {
    const { calls } = stubFetch();
    const onChanged = vi.fn(async () => {});

    render(
      <UdyamExternalActions
        workItem={SUBMIT_ITEM}
        processState={SUBMIT_STATE}
        health={null}
        onChanged={onChanged}
        onError={() => {}}
      />,
    );

    // Fill the required submission fields.
    const ref = await screen.findByLabelText(/Application \/ Reference Number/i);
    fireEvent.change(ref, { target: { value: 'UDYAM-1' } });
    const date = screen.getByLabelText(/Submission Date/i);
    fireEvent.change(date, { target: { value: '2026-08-12' } });
    const time = screen.getByLabelText(/Submission Time/i);
    fireEvent.change(time, { target: { value: '10:00' } });

    // 1) Choose the action -> selected state, NO backend action call.
    fireEvent.click(screen.getByText(/Submit Udyam application/i));
    expect(screen.getByText(/Submit Application selected/i)).toBeTruthy();
    expect(
      calls.some((c) => c.url.includes('udyam-submit-application')),
    ).toBe(false);

    // 2) Confirm -> exactly one backend action call.
    fireEvent.click(screen.getByText(/Save & Submit Application/i));
    await waitFor(() => {
      expect(
        calls.filter((c) => c.url.includes('udyam-submit-application')).length,
      ).toBe(1);
    });
  });

  it('Cancel removes the selected action without calling the backend', async () => {
    const { calls } = stubFetch();
    render(
      <UdyamExternalActions
        workItem={SUBMIT_ITEM}
        processState={SUBMIT_STATE}
        health={null}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    fireEvent.change(
      await screen.findByLabelText(/Application \/ Reference Number/i),
      { target: { value: 'UDYAM-1' } },
    );
    fireEvent.change(screen.getByLabelText(/Submission Date/i), {
      target: { value: '2026-08-12' },
    });
    fireEvent.change(screen.getByLabelText(/Submission Time/i), {
      target: { value: '10:00' },
    });

    fireEvent.click(screen.getByText(/Submit Udyam application/i));
    fireEvent.click(screen.getByText(/^Cancel$/i));
    expect(screen.queryByText(/Submit Application selected/i)).toBeNull();
    expect(
      calls.some((c) => c.url.includes('udyam-submit-application')),
    ).toBe(false);
  });
});

describe('UX5 Change 5 - collapsible action panel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('toggles collapsed/expanded and reflects aria-expanded, without lifecycle calls', () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <UdyamActionShell
        title="Submit Application"
        summary="Record submission details"
        collapsed={false}
        onToggle={onToggle}
      >
        <div>action body</div>
      </UdyamActionShell>,
    );

    // Expanded: body visible, control says Collapse, aria-expanded true.
    const toggle = screen.getByRole('button', { name: /Collapse/i });
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText('action body')).toBeTruthy();

    fireEvent.click(toggle);
    expect(onToggle).toHaveBeenCalledTimes(1);

    // Collapsed: body hidden, summary shown, aria-expanded false.
    rerender(
      <UdyamActionShell
        title="Submit Application"
        summary="Record submission details"
        collapsed={true}
        onToggle={onToggle}
      >
        <div>action body</div>
      </UdyamActionShell>,
    );
    const expand = screen.getByRole('button', { name: /Expand/i });
    expect(expand.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('action body')).toBeNull();
    expect(screen.getByText('Record submission details')).toBeTruthy();
  });
});

describe('UX5 Change 2 - searchable client selector + Add New Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const CLIENTS = [
    { id: 'c1', legal_name: 'Alpha Traders', trade_name: 'Alpha' },
    { id: 'c2', legal_name: 'Beta Industries', trade_name: 'Beta' },
    { id: 'c3', legal_name: 'Gamma LLP', trade_name: 'Gamma' },
    { id: 'c4', legal_name: 'Target', trade_name: '' },
  ];

  it('filters clients as the user types and selects an existing client', () => {
    stubFetch();
    const onChange = vi.fn();
    render(
      <SearchableClientSelect
        clients={CLIENTS}
        value=""
        onChange={onChange}
        onClientCreated={() => {}}
      />,
    );
    const input = screen.getByLabelText(/Search clients/i);
    fireEvent.focus(input);

    // A client with an empty trade_name must fall back to legal_name.
    fireEvent.change(input, { target: { value: 'Target' } });
    expect(screen.getByText('Target')).toBeTruthy();

    fireEvent.change(input, { target: { value: 'Beta' } });

    // Only the matching client is offered.
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.queryByText('Alpha')).toBeNull();

    fireEvent.click(screen.getByText('Beta'));
    expect(onChange).toHaveBeenCalledWith('c2');
  });

  it('Add New Client creates via the client API and makes the new client immediately selectable', async () => {
    const { calls } = stubFetch((url) => {
      if (url.includes('/clients/') && !url.match(/clients\/\?/)) {
        return { id: 'c-new', legal_name: 'New Co', trade_name: 'New Co' };
      }
      return undefined;
    });
    const created: Array<Record<string, unknown>> = [];
    const onClientCreated = vi.fn((client: Record<string, unknown>) => {
      created.push(client);
    });
    render(
      <SearchableClientSelect
        clients={CLIENTS}
        value=""
        onChange={() => {}}
        onClientCreated={onClientCreated}
      />,
    );
    fireEvent.focus(screen.getByLabelText(/Search clients/i));
    fireEvent.click(screen.getByText(/\+ Add New Client/i));

    fireEvent.change(screen.getByLabelText(/New client legal name/i), {
      target: { value: 'New Co' },
    });
    fireEvent.click(screen.getByText(/Create & Select Client/i));

    // The parent receives the full created row (not just an id), so it can
    // select and merge it without waiting on the async list reload.
    await waitFor(() => {
      expect(onClientCreated).toHaveBeenCalledTimes(1);
    });
    expect(created[0]).toMatchObject({ id: 'c-new' });

    // Regression (root cause of the reported bug): the newly created client is
    // available in THIS selector immediately - before any parent list reload -
    // so it is searchable even though it is not in the `clients` prop yet.
    fireEvent.focus(screen.getByLabelText(/Search clients/i));
    fireEvent.change(screen.getByLabelText(/Search clients/i), {
      target: { value: 'New Co' },
    });
    await waitFor(() => {
      expect(screen.getByText('New Co')).toBeTruthy();
    });

    // The client was created through the existing clients endpoint (POST).
    expect(
      calls.some(
        (c) => c.url.includes('/clients/') && c.method === 'POST',
      ),
    ).toBe(true);
  });

  it('a create-client failure does not call onClientCreated (Work draft preserved by caller)', async () => {
    // Return a non-ok response for the client POST.
    const fn = vi.fn(async (url: string, init: RequestInit) => {
      if (String(url).includes('/clients/') && init?.method === 'POST') {
        return new Response(JSON.stringify({ detail: 'bad' }), { status: 400 });
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);

    const onClientCreated = vi.fn();
    render(
      <SearchableClientSelect
        clients={CLIENTS}
        value=""
        onChange={() => {}}
        onClientCreated={onClientCreated}
      />,
    );
    fireEvent.focus(screen.getByLabelText(/Search clients/i));
    fireEvent.click(screen.getByText(/\+ Add New Client/i));
    fireEvent.change(screen.getByLabelText(/New client legal name/i), {
      target: { value: 'New Co' },
    });
    fireEvent.click(screen.getByText(/Create & Select Client/i));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });
    expect(onClientCreated).not.toHaveBeenCalled();
  });
});
