import { describe, expect, it, vi, beforeEach } from 'vitest';
import { createElement } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { act, list, translateError } from '../src/features/console/api';
import { ConsoleApp, buildResourcePayload } from '../src/features/console/ConsoleApp';
import { Drawer } from '../src/features/console/ui';
import { DocumentsPanel, executePendingDocumentDecision, executePendingWorkAction, persistWorkItem, workPrimaryAction } from '../src/features/console/work';

function mockFetch(): ReturnType<typeof vi.fn> {
  const fn = vi.fn(async () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }));
  vi.stubGlobal('fetch', fn);
  return fn;
}

describe('console api client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('uses the verified development tenant and principal identifiers', async () => {
    const fn = mockFetch();
    await list('work-items');
    const init = fn.mock.calls[0]?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers['X-Tenant-ID']).toBe('11111111-1111-1111-1111-111111111111');
    expect(headers['X-Principal-ID']).toBe('22222222-2222-2222-2222-222222222222');
  });
  it('repairs stale development identity values before API requests', async () => {
    localStorage.setItem(
      'tenantId',
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    );

    localStorage.setItem(
      'principalId',
      'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    );

    const fn = mockFetch();

    await list('work-items');

    const init =
      fn.mock.calls[0]?.[1] as RequestInit;

    const headers =
      init.headers as Record<string, string>;

    expect(
      headers['X-Tenant-ID'],
    ).toBe(
      '11111111-1111-1111-1111-111111111111',
    );

    expect(
      headers['X-Principal-ID'],
    ).toBe(
      '22222222-2222-2222-2222-222222222222',
    );

    expect(
      localStorage.getItem('tenantId'),
    ).toBe(
      '11111111-1111-1111-1111-111111111111',
    );

    expect(
      localStorage.getItem('principalId'),
    ).toBe(
      '22222222-2222-2222-2222-222222222222',
    );
  });

  it('Start Work posts status IN_PROGRESS to set_status', async () => {
    const fn = mockFetch();
    await act('work-items', 'abc', 'set_status', { status: 'IN_PROGRESS' });
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/work-items/abc/set_status/');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ status: 'IN_PROGRESS' });
  });

  it('translates a DRF uuid error into a readable sentence', () => {
    expect(translateError('{"domain_id":["Must be a valid UUID."]}')).toBe('Please select a valid Domain.');
  });

  it('translates a detail error verbatim', () => {
    expect(translateError('{"detail":"Only the assigned reviewer may perform this action."}')).toBe(
      'Only the assigned reviewer may perform this action.',
    );
  });

  it('translates nested operational data errors into readable field messages', () => {
    expect(
      translateError(
        JSON.stringify({
          operational_data: {
            requested_loan_amount: [
              'This field is required.',
            ],
            business_name: [
              'This field is required.',
            ],
          },
        }),
      ),
    ).toBe(
      'Operational data: Requested loan amount: This field is required.; Business name: This field is required.',
    );
  });
});


describe('resource payload cleaning', () => {
  it('preserves editable name fields including legal_name', () => {
    expect(
      buildResourcePayload({
        legal_name: 'Workflow Smoke Test Private Limited',
        trade_name: 'Workflow Smoke Test',
        contact_name: 'Test Contact',
        client_type: 'PRIVATE_LIMITED',
        client_name: 'Server display only',
        is_overdue: false,
        attachment_count: 2,
      }),
    ).toEqual({
      legal_name: 'Workflow Smoke Test Private Limited',
      trade_name: 'Workflow Smoke Test',
      contact_name: 'Test Contact',
      client_type: 'PRIVATE_LIMITED',
    });
  });

  it('removes only known server-generated display fields', () => {
    expect(
      buildResourcePayload({
        title: 'Test work',
        client_name: 'Client display',
        service_name: 'Service display',
        owner_name: 'Owner display',
        reviewer_name: 'Reviewer display',
      }),
    ).toEqual({ title: 'Test work' });
  });
});


describe('work drawer save behaviour', () => {
  it('closes the drawer and reloads the grid after a successful save', async () => {
    mockFetch();
    const closeDrawer = vi.fn();
    const setError = vi.fn();
    const reload = vi.fn();

    await persistWorkItem(
      { id: 'work-1', title: 'Workflow V3.5 Smoke Test', client_name: 'Display only' },
      closeDrawer,
      setError,
      reload,
    );

    expect(closeDrawer).toHaveBeenCalledTimes(1);
    expect(reload).toHaveBeenCalledTimes(1);
    expect(setError).toHaveBeenCalledWith('');
  });

  it('keeps the drawer open when saving fails', async () => {
    const fn = vi.fn(async () => new Response('{"detail":"Save failed."}', { status: 400 }));
    vi.stubGlobal('fetch', fn);
    const closeDrawer = vi.fn();
    const setError = vi.fn();
    const reload = vi.fn();

    await persistWorkItem({ title: 'Invalid work' }, closeDrawer, setError, reload);

    expect(closeDrawer).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
    expect(setError).toHaveBeenCalledWith('Save failed.');
  });
});


describe('rework action presentation', () => {
  it('offers submit for review only while work is in progress', () => {
    expect(workPrimaryAction('IN_PROGRESS')).toBe('SUBMIT_FOR_REVIEW');
  });

  it('offers Resume Work for rework-required items', () => {
    expect(workPrimaryAction('REWORK_REQUIRED')).toBe('RESUME_WORK');
  });

  it('does not expose either preparation action for review or completed states', () => {
    expect(workPrimaryAction('READY_FOR_REVIEW')).toBeNull();
    expect(workPrimaryAction('COMPLETED')).toBeNull();
  });
});


describe('document operations contract', () => {
  it('reviews a selected attachment through the attachment endpoint', async () => {
    const fn = mockFetch();
    await executePendingDocumentDecision({
      kind: 'ATTACHMENT_REVIEW',
      attachmentId: 'attachment-1',
      requestId: 'doc-1',
      status: 'ACCEPTED',
      label: 'Accept',
      comment: '',
    });
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/document-attachments/attachment-1/review/');
    expect(JSON.parse(String(init.body))).toEqual({ status: 'ACCEPTED', comment: '' });
  });

  it('keeps waiver as a request-level compatibility action', async () => {
    const fn = mockFetch();
    await executePendingDocumentDecision({
      kind: 'REQUEST_WAIVER',
      requestId: 'doc-1',
      status: 'WAIVED',
      label: 'Waive',
      comment: 'Not applicable',
    });
    const [url, init] = fn.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/document-requests/doc-1/verify/');
    expect(JSON.parse(String(init.body))).toEqual({
      status: 'WAIVED',
      comment: 'Not applicable',
    });
  });
});

describe('save-gated attachment review', () => {
  it('does not review when Accept is selected and reviews only after Save & Accept', async () => {
    const documentRequest = {
      id: 'doc-1',
      name: 'Bank statement',
      status: 'PARTIALLY_RECEIVED',
      requested_from_name: 'Finance Head',
      request_channel: 'WHATSAPP',
    };
    const attachment = {
      id: 'attachment-1',
      document_request_id: 'doc-1',
      original_name: 'bank-statement.pdf',
      source: 'CLIENT',
      review_status: 'PENDING_REVIEW',
      download_url: '/download/attachment-1',
      created_at: '2026-07-29T12:00:00Z',
    };
    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/document-requests/?')) {
        return new Response(JSON.stringify([documentRequest]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/api/v1/document-attachments/?')) {
        return new Response(JSON.stringify([attachment]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.includes('/review/')) {
        return new Response(
          JSON.stringify({ ...attachment, review_status: 'ACCEPTED' }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return new Response('[]', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);

    render(createElement(DocumentsPanel, { workItemId: 'work-1', clientId: 'client-1', canUploadInternal: true }));
    const accept = await screen.findByRole('button', { name: 'Accept' });
    fireEvent.click(accept);

    expect(screen.getByText(/Pending review decision:/)).toBeInTheDocument();
    expect(fn.mock.calls.some((call) => String(call[0]).includes('/review/'))).toBe(false);

    fireEvent.click(screen.getByRole('button', { name: 'Save & Accept' }));
    await waitFor(() =>
      expect(fn.mock.calls.some((call) => String(call[0]).includes('/review/'))).toBe(true),
    );
  });

  it('shows permanent review metadata and no review buttons for an accepted attachment', async () => {
    const documentRequest = {
      id: 'doc-1',
      name: 'GST return',
      status: 'ACCEPTED',
      request_channel: 'EMAIL',
    };
    const attachment = {
      id: 'attachment-1',
      document_request_id: 'doc-1',
      original_name: 'gst-return.pdf',
      source: 'CLIENT',
      review_status: 'ACCEPTED',
      reviewed_by_name: 'Reviewer',
      reviewed_at: '2026-07-29T12:30:00Z',
      review_comment: 'Verified against ledger.',
      download_url: '/download/attachment-1',
      created_at: '2026-07-29T12:00:00Z',
    };
    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes('/api/v1/document-requests/?')
        ? [documentRequest]
        : url.includes('/api/v1/document-attachments/?')
          ? [attachment]
          : [];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);

    render(createElement(DocumentsPanel, { workItemId: 'work-1', clientId: 'client-1', canUploadInternal: true }));

    expect(await screen.findByText(/Reviewed by Reviewer/)).toBeInTheDocument();
    expect(screen.getByText('Verified against ledger.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('cancels a pending attachment decision without calling review', async () => {
    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes('/api/v1/document-requests/?')
        ? [{ id: 'doc-1', name: 'GST return', status: 'PARTIALLY_RECEIVED', request_channel: 'EMAIL' }]
        : url.includes('/api/v1/document-attachments/?')
          ? [{
              id: 'attachment-1',
              document_request_id: 'doc-1',
              original_name: 'gst.pdf',
              review_status: 'PENDING_REVIEW',
              source: 'CLIENT',
            }]
          : [];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);

    render(createElement(DocumentsPanel, { workItemId: 'work-1', clientId: 'client-1', canUploadInternal: true }));
    fireEvent.click(await screen.findByRole('button', { name: 'Accept' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('button', { name: 'Save & Accept' })).not.toBeInTheDocument();
    expect(fn.mock.calls.some((call) => String(call[0]).includes('/review/'))).toBe(false);
  });
});

describe('client contact management', () => {
  it('keeps canonical contact management in the existing client editor', async () => {
    const client = {
      id: 'client-1',
      legal_name: 'Example Private Limited',
      trade_name: 'Example',
      client_type: 'PRIVATE_LIMITED',
      engagement_status: 'ACTIVE',
    };
    const contact = {
      id: 'contact-1',
      client_id: 'client-1',
      name: 'Finance Head',
      designation: 'Chief Financial Officer',
      email: 'finance@example.test',
      mobile: '9999999999',
      whatsapp_number: '9999999999',
      preferred_channel: 'WHATSAPP',
      can_receive_document_requests: true,
      is_primary: true,
      is_active: true,
    };

    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const body =
        url.includes('/api/v1/clients/client-1/')
          ? client
          : url.includes('/api/v1/clients/')
            ? [client]
            : url.includes('/api/v1/client-contacts/')
              ? [contact]
              : [];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);

    render(createElement(ConsoleApp));
    fireEvent.click(
      await screen.findByRole('button', { name: 'Clients' }),
    );

    await screen.findByText('Example');
    fireEvent.click(screen.getByText('Example'));

    // Phase 5.2 Option A:
    // Client Workspace is the operational 360-degree view.
    // Contact CRUD remains canonical in the existing Client editor.
    expect(
      await screen.findByRole(
        'heading',
        { name: 'Example' },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        { name: 'Contacts' },
      ),
    ).toBeInTheDocument();

    expect(
      await screen.findByText('Finance Head'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Chief Financial Officer'),
    ).toBeInTheDocument();

    // No parallel contact editor is introduced in Client Workspace.
    expect(
      screen.queryByRole(
        'button',
        { name: 'Add contact' },
      ),
    ).not.toBeInTheDocument();

    // Editing returns to the existing certified Client editor,
    // where canonical ClientContactsPanel remains responsible for CRUD.
    fireEvent.click(
      screen.getByRole(
        'button',
        { name: 'Edit Client' },
      ),
    );

    expect(
      await screen.findByRole(
        'button',
        { name: 'Add contact' },
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(fn).toHaveBeenCalledWith(
        '/api/v1/client-contacts/?client_id=client-1',
        expect.any(Object),
      );
    });
  });

  it('requires a new client to be saved before contacts are added', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    render(createElement(ConsoleApp));
    fireEvent.click(
      await screen.findByRole('button', { name: 'Clients' }),
    );
    await waitFor(() => expect(screen.queryByText('Loading...')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Add Client' }));

    expect(screen.getByText('Save the client before adding contacts.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add contact' })).not.toBeInTheDocument();
  });
});


describe('contact architecture boundaries', () => {
  it('keeps recipient selection but removes contact creation from Work Item documents', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    render(createElement(DocumentsPanel, { workItemId: 'work-1', clientId: 'client-1', canUploadInternal: true }));

    expect(
      await screen.findByText(/No eligible document contact exists for this client/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add client contact' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add another contact' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Add request' }));
    expect(await screen.findByText('Requested From Contact')).toBeInTheDocument();
  });

  it('provides an explicit Back action that closes a drawer without saving', () => {
    const onClose = vi.fn();
    const onSave = vi.fn();

    render(
      createElement(Drawer, {
        title: 'New Client Contact',
        fields: [{ name: 'name' }],
        value: { name: '' },
        onChange: vi.fn(),
        onClose,
        onSave,
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Back' }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });
});


describe('save-gated work lifecycle', () => {
  it('saves work item details before executing the selected workflow action', async () => {
    const requests: Array<{ input: RequestInfo | URL; init: RequestInit | undefined }> = [];
    const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ input, init });
      const url = String(input);
      if (url === '/api/v1/work-items/work-1/') {
        return new Response('{"id":"work-1","status":"NOT_STARTED"}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url === '/api/v1/work-items/work-1/set_status/') {
        return new Response('{"id":"work-1","status":"IN_PROGRESS"}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{"detail":"Unexpected request"}', { status: 500 });
    });
    vi.stubGlobal('fetch', fn);
    const closeDrawer = vi.fn();
    const setError = vi.fn();
    const reload = vi.fn();

    await persistWorkItem(
      { id: 'work-1', title: 'Test', status: 'NOT_STARTED' },
      closeDrawer,
      setError,
      reload,
      { kind: 'START_WORK', label: 'Start Work' },
    );

    expect(fn).toHaveBeenCalledTimes(2);
    expect(String(requests[0]?.input)).toBe('/api/v1/work-items/work-1/');
    expect(String(requests[1]?.input)).toBe('/api/v1/work-items/work-1/set_status/');
    expect(JSON.parse(String(requests[1]?.init?.body))).toEqual({
      status: 'IN_PROGRESS',
    });
    expect(closeDrawer).toHaveBeenCalledTimes(1);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('does not execute a workflow action when saving the work item fails', async () => {
    const fn = vi.fn(async () =>
      new Response('{"detail":"Save failed."}', {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fn);
    const closeDrawer = vi.fn();
    const setError = vi.fn();
    const reload = vi.fn();

    await persistWorkItem(
      { id: 'work-1', title: 'Invalid' },
      closeDrawer,
      setError,
      reload,
      { kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' },
    );

    expect(fn).toHaveBeenCalledTimes(1);
    expect(closeDrawer).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
    expect(setError).toHaveBeenCalledWith('Save failed.');
  });

  it('keeps the drawer open if the workflow action fails after details were saved', async () => {
    const fn = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/v1/work-items/work-1/') {
        return new Response('{"id":"work-1","status":"IN_PROGRESS"}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{"detail":"Transition failed."}', {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fn);
    const closeDrawer = vi.fn();
    const setError = vi.fn();
    const reload = vi.fn();

    await persistWorkItem(
      { id: 'work-1', title: 'Test' },
      closeDrawer,
      setError,
      reload,
      { kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' },
    );

    expect(fn).toHaveBeenCalledTimes(2);
    expect(closeDrawer).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
    expect(setError).toHaveBeenCalledWith('Transition failed.');
  });

  it('maps every pending workflow action to the existing backend contract', async () => {
    const fn = mockFetch();

    await executePendingWorkAction('work-1', { kind: 'START_WORK', label: 'Start Work' });
    await executePendingWorkAction('work-1', {
      kind: 'SUBMIT_FOR_REVIEW',
      label: 'Submit for review',
    });
    await executePendingWorkAction('work-1', { kind: 'RESUME_WORK', label: 'Resume Work' });
    await executePendingWorkAction('work-1', { kind: 'APPROVE', label: 'Approve & complete' });
    await executePendingWorkAction('work-1', {
      kind: 'RETURN_FOR_REWORK',
      label: 'Return for rework',
      comment: 'Correction required',
    });

    expect(fn.mock.calls.map((call) => String(call[0]))).toEqual([
      '/api/v1/work-items/work-1/set_status/',
      '/api/v1/work-items/work-1/submit_for_review/',
      '/api/v1/work-items/work-1/set_status/',
      '/api/v1/work-items/work-1/approve/',
      '/api/v1/work-items/work-1/return_for_rework/',
    ]);
  });
});
