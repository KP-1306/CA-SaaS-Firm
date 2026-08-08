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
  ActionCentre,
} from '../src/features/console/action-centre';

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
  localStorage.clear();
});

describe('Phase 5.4 Action Centre', () => {
  it('uses personal Work Health for staff', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/branding/')) {
          return response({
            capabilities: {
              can_view_firm_operations: false,
            },
          });
        }

        if (url.includes('/dashboard/employee/')) {
          return response({
            work_health: {
              overdue: 1,
              waiting_on_client: 1,
              waiting_on_reviewer: 0,
              immediate_actions: [
                {
                  work_item_id: 'work-1',
                  title: 'GST Return',
                  status: 'IN_PROGRESS',
                  due_state: 'OVERDUE',
                  days_to_due: -2,
                  current_controller: 'OWNER',
                  waiting_days: 2,
                  next_action: 'Continue work',
                },
                {
                  work_item_id: 'work-2',
                  title: 'ROC Filing',
                  status: 'WAITING_FOR_CLIENT',
                  due_state: 'ON_TRACK',
                  current_controller: 'CLIENT',
                  waiting_days: 4,
                  next_action: 'Await client documents',
                },
              ],
            },
          });
        }

        if (url.includes('/dashboard/executive/')) {
          throw new Error(
            'Staff requested executive dashboard.',
          );
        }

        return response({});
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    const openWork = vi.fn();

    render(
      <ActionCentre onOpenWork={openWork} />,
    );

    expect(
      await screen.findByRole(
        'heading',
        { name: 'Action Centre' },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('My operational view'),
    ).toBeInTheDocument();

    const region = screen.getByRole(
      'region',
      { name: 'Actionable work' },
    );

    expect(
      within(region).getByText('GST Return'),
    ).toBeInTheDocument();

    expect(
      within(region).getByText('ROC Filing'),
    ).toBeInTheDocument();

    const openButtons = within(region).getAllByRole(
      'button',
      { name: 'Open' },
    );

    expect(openButtons.length).toBeGreaterThan(0);

    const firstOpenButton = openButtons[0];

    if (!firstOpenButton) {
      throw new Error(
        'Expected at least one actionable Open button.',
      );
    }

    fireEvent.click(firstOpenButton);

    expect(openWork).toHaveBeenCalledWith('work-1');

    expect(
      fetchMock.mock.calls.some(
        ([input]) =>
          String(input).includes(
            '/dashboard/executive/',
          ),
      ),
    ).toBe(false);
  });

  it('uses authorized firm Work Health for leadership', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/branding/')) {
          return response({
            capabilities: {
              can_view_firm_operations: true,
            },
          });
        }

        if (url.includes('/dashboard/employee/')) {
          return response({
            work_health: {
              immediate_actions: [],
            },
          });
        }

        if (url.includes('/dashboard/executive/')) {
          return response({
            action_centre: {
              rework_required: 1,
            },
            work_health: {
              overdue: 0,
              waiting_on_client: 0,
              waiting_on_reviewer: 1,
              immediate_actions: [
                {
                  work_item_id: 'firm-1',
                  title: 'Home Loan',
                  status: 'READY_FOR_REVIEW',
                  due_state: 'DUE_SOON',
                  days_to_due: 1,
                  current_controller: 'REVIEWER',
                  waiting_days: 1,
                  next_action: 'Review received documents',
                },
              ],
            },
          });
        }

        return response({});
      }),
    );

    render(
      <ActionCentre onOpenWork={vi.fn()} />,
    );

    expect(
      await screen.findByText(
        'Firm operational view',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Home Loan'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole(
        'button',
        { name: /Review \/ QA/ },
      ),
    );

    await waitFor(() => {
      expect(
        screen.getByText('Home Loan'),
      ).toBeInTheDocument();
    });
  });
});
