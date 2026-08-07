

import {
  render,
  screen,
} from '@testing-library/react';

import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  WorkHealthCard,
  isWorkHealthSnapshot,
  workHealthTone,
} from '../src/features/console/work';

import {
  getObject,
} from '../src/features/console/api';


const SNAPSHOT = {
  contract_version: 1,
  work_item_id: 'work-1',
  progress: 68,
  health: 'AMBER' as const,
  risk: 'MEDIUM' as const,
  current_controller: 'CLIENT' as const,
  waiting_days: 8,
  waiting_since: '2026-08-01T10:00:00Z',
  due_state: 'DUE_SOON' as const,
  days_to_due: 2,

  operational: {
    total: 7,
    completed: 5,
    remaining: 2,
    mandatory_total: 4,
    mandatory_completed: 3,
    mandatory_remaining: 1,
    completion_percent: 71,
  },

  documents: {
    total: 8,
    satisfied: 5,
    pending: 3,
    mandatory_total: 6,
    mandatory_satisfied: 4,
    mandatory_missing: 2,
    missing: 2,
    pending_review: 1,
    rejected: 0,
    expired: 0,
    pending_acceptance: 1,
    ready_for_review: false,
    readiness_state: 'WAITING_FOR_CLIENT',
    health_score: 63,
    blockers: [],
  },

  next_action: {
    code: 'AWAIT_CLIENT_DOCUMENTS',
    label: 'Await client documents',
  },

  reasons: [
    '2 mandatory document dependencies remain.',
    'Work has been waiting for 8 days.',
  ],

  calculated_at: '2026-08-07T10:00:00Z',
};


describe('Phase 4A.2 Work Health UI', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('maps health states to visual tones', () => {
    expect(workHealthTone('GREEN')).toBe('stable');
    expect(workHealthTone('AMBER')).toBe('watch');
    expect(workHealthTone('RED')).toBe('risk');
  });

  it('renders the certified health snapshot', () => {
    render(
      <WorkHealthCard health={SNAPSHOT} />,
    );

    expect(
      screen.getByLabelText('Work health'),
    ).toHaveAttribute(
      'data-health',
      'AMBER',
    );

    expect(
      screen.getByText('68%'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Medium risk'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Client'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('8 days'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Due in 2 days'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Await client documents',
      ),
    ).toBeInTheDocument();
  });

  it('renders loading safely', () => {
    render(
      <WorkHealthCard
        health={null}
        loading
      />,
    );

    expect(
      screen.getByText(
        'Calculating operational health…',
      ),
    ).toBeInTheDocument();
  });

  it('renders unavailable safely', () => {
    render(
      <WorkHealthCard
        health={null}
        error="Health endpoint unavailable."
      />,
    );

    expect(
      screen.getByText('Health unavailable'),
    ).toBeInTheDocument();
  });

  it('uses the certified health endpoint', async () => {
    const fetchMock =
      vi.fn(
        async () =>
          new Response(
            JSON.stringify(SNAPSHOT),
            {
              status: 200,
              headers: {
                'Content-Type':
                  'application/json',
              },
            },
          ),
      );

    vi.stubGlobal(
      'fetch',
      fetchMock,
    );

    const result =
      await getObject(
        'work-items/work-1/health',
      );

    expect(result.progress).toBe(68);

    expect(
      fetchMock,
    ).toHaveBeenCalledTimes(1);

        const call =
      fetchMock.mock.calls[0] as unknown as [
        string,
        RequestInit,
      ];

    const [url, init] = call;

    expect(url).toBe(
      '/api/v1/work-items/work-1/health/',
    );

    expect(
      (init as RequestInit).credentials,
    ).toBe('include');
  });

  it(
    'rejects incomplete health payloads safely',
    () => {
      expect(
        isWorkHealthSnapshot({}),
      ).toBe(false);

      expect(
        isWorkHealthSnapshot(SNAPSHOT),
      ).toBe(true);
    },
  );
});
