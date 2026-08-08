import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import {
  ClientWorkspace,
} from '../src/features/console/client-workspace';


function jsonResponse(body: unknown): Response {
  return new Response(
    JSON.stringify(body),
    {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
      },
    },
  );
}


afterEach(() => {
  vi.restoreAllMocks();
});


describe('Phase 5.2 Client Workspace', () => {
  it('renders the approved 360-degree client operational view', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/clients/client-1/')) {
          return jsonResponse({
            id: 'client-1',
            legal_name: 'Alpine Private Limited',
            trade_name: 'Alpine',
            client_type: 'PRIVATE_LIMITED',
            pan: 'ABCDE1234F',
            tan: 'ABCD12345E',
            lifecycle_status: 'ACTIVE',
            engagement_status: 'ACTIVE',
          });
        }

        if (url.includes('/work-items/')) {
          return jsonResponse([
            {
              id: 'work-1',
              title: 'GST Return',
              client_id: 'client-1',
              service_name: 'GST Return',
              status: 'IN_PROGRESS',
              priority: 'NORMAL',
              due_date: '2026-08-10',
              is_overdue: false,
              owner_user_id: 'employee-1',
              owner_name: 'Rahul',
              reviewer_user_id: 'employee-2',
              reviewer_name: 'Priya',
            },
            {
              id: 'work-2',
              title: 'TDS Return',
              client_id: 'client-1',
              status: 'IN_PROGRESS',
              is_overdue: true,
            },
          ]);
        }

        if (url.includes('/document-requests/')) {
          return jsonResponse([
            {
              id: 'doc-1',
              name: 'Bank Statement',
              status: 'REQUESTED',
              category: 'BANKING',
            },
            {
              id: 'doc-2',
              name: 'PAN',
              status: 'ACCEPTED',
              category: 'IDENTITY_KYC',
            },
          ]);
        }

        if (url.includes('/client-contacts/')) {
          return jsonResponse([
            {
              id: 'contact-1',
              name: 'Amit Sharma',
              designation: 'Accountant',
              is_primary: true,
            },
          ]);
        }

        if (url.includes('/client-workspace/')) {
          return jsonResponse({
            client_id: 'client-1',
            work_health: {
              healthy: 1,
              attention_required: 1,
              high_risk: 0,
              due_soon: 1,
              overdue: 1,
              waiting_on_client: 1,
              waiting_on_reviewer: 0,
            },
            upcoming_deadlines: [
              {
                work_item_id: 'work-1',
                title: 'GST Return',
                due_date: '2026-08-10',
                next_action: 'Continue work',
              },
            ],
            recent_activity: [
              {
                id: 'note-1',
                work_item_id: 'work-1',
                title: 'GST Return',
                entry: 'Documents requested',
                created_at: '2026-08-08T08:10:00Z',
              },
            ],
            history: [
              {
                id: 'note-1',
                work_item_id: 'work-1',
                title: 'GST Return',
                entry: 'Documents requested',
                created_at: '2026-08-08T08:10:00Z',
              },
            ],
          });
        }

        return jsonResponse([]);
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    const openWork = vi.fn();
    const editClient = vi.fn();

    render(
      <ClientWorkspace
        clientId="client-1"
        onBack={vi.fn()}
        onEditClient={editClient}
        onOpenWork={openWork}
      />,
    );

    expect(
      await screen.findByRole(
        'heading',
        {
          name: 'Alpine',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'Active Work',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'Pending Documents',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Bank Statement'),
    ).toBeInTheDocument();

    // The client identity header legitimately contains the label "PAN".
    // Prove instead that only the pending document is rendered and the
    // accepted document is absent from the Pending Documents section.
    const pendingDocumentsHeading = screen.getByRole(
      'heading',
      {
        name: 'Pending Documents',
      },
    );

    const pendingDocumentsSection =
      pendingDocumentsHeading.closest('section');

    expect(pendingDocumentsSection).not.toBeNull();

    expect(
      pendingDocumentsSection,
    ).toHaveTextContent('Bank Statement');

    expect(
      pendingDocumentsSection,
    ).not.toHaveTextContent('IDENTITY_KYC');

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'Operational Health',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'Upcoming Obligations',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Amit Sharma'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Rahul'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Priya'),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'Recent Activity',
        },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'heading',
        {
          name: 'History',
        },
      ),
    ).toBeInTheDocument();

    // Vridhi testing standard:
    // repeated business objects are queried within their
    // operational section, never globally across the page.

    const activeWorkSection = screen
      .getByRole(
        'heading',
        {
          name: 'Active Work',
        },
      )
      .closest('section');

    expect(activeWorkSection).not.toBeNull();

    fireEvent.click(
      within(
        activeWorkSection as HTMLElement,
      ).getByRole(
        'button',
        {
          name: /GST Return/,
        },
      ),
    );

    expect(openWork).toHaveBeenCalledWith('work-1');

    const upcomingSection = screen
      .getByRole(
        'heading',
        {
          name: 'Upcoming Obligations',
        },
      )
      .closest('section');

    expect(upcomingSection).not.toBeNull();

    fireEvent.click(
      within(
        upcomingSection as HTMLElement,
      ).getByRole(
        'button',
        {
          name: /GST Return/,
        },
      ),
    );

    expect(openWork).toHaveBeenCalledTimes(2);
    expect(openWork).toHaveBeenLastCalledWith('work-1');

    fireEvent.click(
      screen.getByRole(
        'button',
        {
          name: 'Edit Client',
        },
      ),
    );

    expect(editClient).toHaveBeenCalled();

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes(
              '/client-workspace/',
            ),
        ),
      ).toBe(true);
    });
  });
});
