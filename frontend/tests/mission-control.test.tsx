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
  Dashboard,
} from '../src/features/console/ConsoleApp';

function response(body: unknown): Response {
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

describe('Phase 5.1 Mission Control', () => {
  it('renders personal and firm operational truth for leadership', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/branding/')) {
          return response({
            capabilities: {
              is_executive: true,
              can_view_firm_operations: true,
              role: 'PARTNER',
            },
          });
        }

        if (url.includes('/dashboard/employee/')) {
          return response({
            my_work: {
              assigned_open: 18,
              due_today: 4,
              overdue: 2,
              waiting_for_client: 3,
              ready_for_review: 1,
              rework_required: 0,
              recently_completed: 7,
            },
            workload: {
              status_distribution: {
                IN_PROGRESS: 8,
                WAITING_FOR_CLIENT: 3,
              },
              pending_reviews_assigned: 0,
            },
            work_health: {
              healthy: 12,
              attention_required: 4,
              high_risk: 2,
              due_soon: 3,
              overdue: 2,
              waiting_on_client: 3,
              waiting_on_reviewer: 1,
              immediate_actions: [],
            },
            recent_activity: [],
            upcoming_deadlines: [],
          });
        }

        if (url.includes('/dashboard/executive/')) {
          return response({
            overview: {
              active_clients: 20,
              active_work: 50,
              due_today: 7,
              overdue: 4,
              waiting_for_client: 5,
              ready_for_review: 3,
              rework_required: 1,
              recently_completed: 9,
            },
            operations: {
              by_status: {
                NOT_STARTED: 10,
                IN_PROGRESS: 18,
                WAITING_FOR_CLIENT: 5,
                READY_FOR_REVIEW: 3,
                REWORK_REQUIRED: 1,
                COMPLETED: 24,
              },
            },
            employee_workload: {
              rows: [
                {
                  employee_id: 'e1',
                  employee_name: 'Rahul',
                  open_work: 12,
                  overdue: 1,
                  completed_in_period: 8,
                },
              ],
            },
            client_health: {
              rows: [
                {
                  client_id: 'c1',
                  client_name: 'Alpine Pvt Ltd',
                  open_work: 3,
                  overdue_work: 1,
                  pending_documents: 2,
                },
              ],
            },
            action_centre: {
              unassigned: 1,
              review_backlog: 2,
            },
            work_health: {
              healthy: 42,
              attention_required: 8,
              high_risk: 3,
              due_soon: 7,
              overdue: 2,
              waiting_on_client: 5,
              waiting_on_reviewer: 2,
              immediate_actions: [
                {
                  work_item_id: 'w1',
                  title: 'GST Return',
                  health: 'RED',
                  risk: 'HIGH',
                  due_state: 'OVERDUE',
                  waiting_days: 2,
                  next_action: 'Await client documents',
                },
              ],
            },
            client_activity: [
              {
                id: 'n1',
                client_id: 'c1',
                client_name: 'Alpine Pvt Ltd',
                title: 'GST Return',
                entry: 'Documents received.',
                created_at: '2026-08-08T11:35:00Z',
              },
            ],
            recent_activity: [
              {
                id: 'n1',
                client_name: 'Alpine Pvt Ltd',
                title: 'GST Return',
                entry: 'Submitted for review.',
                created_at: '2026-08-08T11:20:00Z',
              },
            ],
            upcoming_deadlines: [
              {
                work_item_id: 'w1',
                client_name: 'Alpine Pvt Ltd',
                title: 'GST Return',
                due_date: '2026-08-09',
                days_to_due: 1,
                due_state: 'DUE_SOON',
              },
            ],
          });
        }

        return response({});
      }),
    );

    const openWork = vi.fn();

    render(
      <Dashboard
        onOpenWork={openWork}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByText('Mission Control'),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText('My Work Today'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Immediate Actions'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Operational Health'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Work Distribution'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Team Snapshot'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Client Activity'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Timeline'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Deadlines'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Await client documents'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByTestId('mission-action-w1'),
    );

    expect(openWork).toHaveBeenCalledTimes(1);
    expect(openWork).toHaveBeenCalledWith('w1');

    fireEvent.click(
      screen.getByTestId('mission-deadline-w1'),
    );

    expect(openWork).toHaveBeenCalledTimes(2);
    expect(openWork).toHaveBeenLastCalledWith('w1');

    // Row 1 is PERSONAL even for leadership.
    const myWorkToday = screen
      .getByText('My Work Today')
      .closest('.cx-mission-panel');

    expect(myWorkToday).not.toBeNull();

    expect(
      within(myWorkToday as HTMLElement).getByText('18'),
    ).toBeInTheDocument();

    // Canonical firm health is shown separately.
    expect(
      screen.getByText('42'),
    ).toBeInTheDocument();
  });

  it('never requests the executive endpoint for staff', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/branding/')) {
          return response({
            capabilities: {
              is_executive: false,
              can_view_firm_operations: false,
              role: 'STAFF',
            },
          });
        }

        if (url.includes('/dashboard/employee/')) {
          return response({
            my_work: {
              assigned_open: 5,
              due_today: 1,
              overdue: 0,
              waiting_for_client: 1,
              ready_for_review: 0,
              rework_required: 0,
              recently_completed: 2,
            },
            workload: {
              status_distribution: {
                IN_PROGRESS: 4,
                WAITING_FOR_CLIENT: 1,
              },
              pending_reviews_assigned: 0,
            },
            work_health: {
              healthy: 4,
              attention_required: 1,
              high_risk: 0,
              due_soon: 1,
              overdue: 0,
              waiting_on_client: 1,
              waiting_on_reviewer: 0,
              immediate_actions: [],
            },
            recent_activity: [],
            upcoming_deadlines: [],
          });
        }

        return response({});
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByText('Mission Control'),
      ).toBeInTheDocument();
    });

    const requested = fetchMock.mock.calls.map(
      (call) => String(call[0]),
    );

    expect(
      requested.some(
        (url) => url.includes('/dashboard/executive/'),
      ),
    ).toBe(false);

    expect(
      screen.queryByText('Team Snapshot'),
    ).not.toBeInTheDocument();

    expect(
      screen.queryByText('Client Activity'),
    ).not.toBeInTheDocument();
  });

  it('PLATFORM_ADMIN receives firm operational Mission Control', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/branding/')) {
          return response({
            capabilities: {
              is_executive: false,
              can_view_firm_operations: true,
              role: null,
            },
          });
        }

        if (url.includes('/dashboard/employee/')) {
          return response({
            my_work: {
              assigned_open: 0,
              due_today: 0,
              overdue: 0,
              waiting_for_client: 0,
              ready_for_review: 0,
              rework_required: 0,
              recently_completed: 0,
            },
            workload: {
              status_distribution: {},
              pending_reviews_assigned: 0,
            },
            work_health: {
              healthy: 0,
              attention_required: 0,
              high_risk: 0,
              due_soon: 0,
              overdue: 0,
              waiting_on_client: 0,
              waiting_on_reviewer: 0,
              immediate_actions: [],
            },
            recent_activity: [],
            upcoming_deadlines: [],
          });
        }

        if (url.includes('/dashboard/executive/')) {
          return response({
            overview: {
              recently_completed: 3,
            },
            operations: {
              by_status: {
                NOT_STARTED: 2,
                IN_PROGRESS: 7,
                WAITING_FOR_CLIENT: 1,
                READY_FOR_REVIEW: 1,
                REWORK_REQUIRED: 0,
                COMPLETED: 4,
              },
            },
            employee_workload: {
              rows: [
                {
                  employee_id: 'firm-employee-1',
                  employee_name: 'Firm Employee',
                  open_work: 7,
                  overdue: 1,
                  completed_in_period: 4,
                },
              ],
            },
            client_health: {
              rows: [
                {
                  client_id: 'client-1',
                  client_name: 'Operational Client',
                  open_work: 2,
                  overdue_work: 1,
                  pending_documents: 1,
                },
              ],
            },
            action_centre: {},
            work_health: {
              healthy: 6,
              attention_required: 2,
              high_risk: 1,
              due_soon: 2,
              overdue: 1,
              waiting_on_client: 1,
              waiting_on_reviewer: 1,
              immediate_actions: [],
            },
            recent_activity: [],
            client_activity: [],
            upcoming_deadlines: [],
          });
        }

        return response({});
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByText('Firm Employee'),
      ).toBeInTheDocument();
    });

    const requested = fetchMock.mock.calls.map(
      (call) => String(call[0]),
    );

    expect(
      requested.some(
        (url) => url.includes('/dashboard/executive/'),
      ),
    ).toBe(true);

    // My Work Today remains personal.
    const myWorkToday = screen
      .getByText('My Work Today')
      .closest('.cx-mission-panel');

    expect(myWorkToday).not.toBeNull();

    expect(
      within(myWorkToday as HTMLElement).getAllByText('0').length,
    ).toBeGreaterThan(0);

    // Firm operational sections are now visible.
    expect(
      screen.getByText('Team Snapshot'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Client Activity'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Firm Employee'),
    ).toBeInTheDocument();
  });

});
