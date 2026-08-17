import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { WorkArea } from '../src/features/console/work';
import { lockMessage } from '../src/features/console/types';

// A work item controlled by the reviewer in READY_FOR_REVIEW (owner locked).
const LOCKED_ITEM = {
  id: 'w1', title: 'Locked Work', status: 'READY_FOR_REVIEW',
  client_id: 'c1', client_name: 'Acme', owner_name: 'O', reviewer_name: 'R',
  is_locked: true, can_edit: false, can_submit_for_review: false,
  can_review: false, can_upload_internal: false,
  current_controller: 'REVIEWER', current_controller_name: 'R',
};

const EDITABLE_ITEM = {
  id: 'w2', title: 'Editable Work', status: 'IN_PROGRESS',
  client_id: 'c1', client_name: 'Acme',
  is_locked: false, can_edit: true, can_submit_for_review: true,
  can_review: false, can_upload_internal: true,
  current_controller: 'OWNER', current_controller_name: 'O',
};

function mockFetchReturning(rows: unknown[]): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      // Every collection endpoint consumed by WorkArea must return an array.
      // Only the work-items collection receives the test rows; lookup collections are empty.
      const isCollection = /\/api\/v1\/(clients|verticals|domains|services|employees|work-items)\/(?:\?.*)?$/.test(url);
      const isWorkItemsCollection = /\/api\/v1\/work-items\/(?:\?.*)?$/.test(url);
      const body = isWorkItemsCollection ? rows : isCollection ? [] : {};
      return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }),
  );
}

describe('C4 lockMessage', () => {
  it('describes reviewer control in READY_FOR_REVIEW', () => {
    expect(lockMessage('READY_FOR_REVIEW', 'Alice')).toContain('Alice');
  });
  it('describes terminal read-only for COMPLETED and CANCELLED', () => {
    expect(lockMessage('COMPLETED', '')).toMatch(/completed/i);
    expect(lockMessage('CANCELLED', '')).toMatch(/cancelled/i);
  });
  it('describes waiting-for-client lock', () => {
    expect(lockMessage('WAITING_FOR_CLIENT', '')).toMatch(/client/i);
  });
});

describe('C4 WorkArea flag-driven UI', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('shows a lock banner and offers no actionable Save when can_edit is false', async () => {
    mockFetchReturning([LOCKED_ITEM]);
    render(<WorkArea />);
    const table = await screen.findByRole('table');
    const row = within(table).getByText('Locked Work');
    fireEvent.click(row);
    await waitFor(() => expect(screen.getByText(/submitted for review/i)).toBeInTheDocument());
    // A user with can_edit=false must not have an actionable Save control.
    // The working UI renders only a Close control in the footer for a locked
    // record, so there is no Save button in the document (it is not merely
    // disabled).  This reflects the intended locked-user contract.
    expect(screen.queryByRole('button', { name: /^Save$/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Save & Close$/ })).not.toBeInTheDocument();
    // Close remains available.
    expect(screen.getByRole('button', { name: /^Close$/ })).toBeInTheDocument();
  });

  it('does not show a lock banner for an editable owner item', async () => {
    mockFetchReturning([EDITABLE_ITEM]);
    render(<WorkArea />);
    const row = await screen.findByText('Editable Work');
    fireEvent.click(row);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Editable Work' })).toBeInTheDocument());
    expect(screen.queryByText(/submitted for review and controlled/i)).not.toBeInTheDocument();
  });
});
