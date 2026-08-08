import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  render,
  screen,
} from '@testing-library/react';

import {
  TimelinePanel,
} from '../src/features/console/work';


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


describe('Phase 5.3 Work Timeline', () => {
  it('renders one chronological story from existing durable events', async () => {
    const events = [
      {
        id: 'work-created-work-1',
        event_type: 'WORK_CREATED',
        title: 'Work created',
        entry: 'GST Return',
        created_at: '2026-08-08T09:00:00Z',
        actor_name: 'Rahul',
        from_status: '',
        to_status: 'NOT_STARTED',
      },
      {
        id: 'assignment-1',
        event_type: 'REASSIGNED',
        title: 'Work reassigned',
        entry: 'Owner: Priya',
        created_at: '2026-08-08T09:10:00Z',
        actor_name: 'Manager',
      },
      {
        id: 'document-request-1',
        event_type: 'DOCUMENT_REQUESTED',
        title: 'Document requested',
        entry: 'Bank Statement',
        created_at: '2026-08-08T09:20:00Z',
      },
      {
        id: 'attachment-upload-1',
        event_type: 'DOCUMENT_RECEIVED',
        title: 'Document received from client',
        entry: 'Bank Statement',
        created_at: '2026-08-08T09:30:00Z',
      },
      {
        id: 'note-submit',
        event_type: 'SUBMITTED_FOR_REVIEW',
        title: 'Submitted for review',
        entry: 'Submitted for review.',
        created_at: '2026-08-08T09:40:00Z',
        from_status: 'IN_PROGRESS',
        to_status: 'READY_FOR_REVIEW',
      },
      {
        id: 'note-complete',
        event_type: 'REVIEW_APPROVED',
        title: 'Review approved and completed',
        entry: 'Approved and completed.',
        created_at: '2026-08-08T10:00:00Z',
        from_status: 'READY_FOR_REVIEW',
        to_status: 'COMPLETED',
      },
    ];

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (
          url.includes(
            '/work-items/work-1/history/',
          )
        ) {
          return jsonResponse(events);
        }

        return jsonResponse([]);
      }),
    );

    const { container } = render(
      <TimelinePanel workItemId="work-1" />,
    );

    expect(
      await screen.findByRole(
        'region',
        { name: 'Work Timeline' },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Work created'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Work reassigned'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Document requested'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Document received from client',
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Submitted for review'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Review approved and completed',
      ),
    ).toBeInTheDocument();

    const text = container.textContent ?? '';

    expect(
      text.indexOf('Work created'),
    ).toBeLessThan(
      text.indexOf('Work reassigned'),
    );

    expect(
      text.indexOf('Work reassigned'),
    ).toBeLessThan(
      text.indexOf('Document requested'),
    );

    expect(
      text.indexOf('Document requested'),
    ).toBeLessThan(
      text.indexOf('Submitted for review'),
    );

    expect(
      text.indexOf('Submitted for review'),
    ).toBeLessThan(
      text.indexOf(
        'Review approved and completed',
      ),
    );
  });
});
