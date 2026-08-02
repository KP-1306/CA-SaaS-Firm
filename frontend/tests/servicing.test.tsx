import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ServicingArea } from '../src/features/console/servicing';

// The servicing area lists three resources plus reference data; every fetch
// returns an empty list, so the area renders its sub-navigation and the empty
// state without raw-UUID inputs.
vi.stubGlobal(
  'fetch',
  vi.fn(async () =>
    new Response('[]', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  ),
);

describe('servicing area', () => {
  it('renders the three servicing sub-sections', async () => {
    render(<ServicingArea />);
    expect(await screen.findByText('Subscriptions')).toBeInTheDocument();
    expect(screen.getByText('Task Templates')).toBeInTheDocument();
    expect(screen.getByText('Recurring Work')).toBeInTheDocument();
  });

  it('shows an empty state rather than fabricated rows', async () => {
    render(<ServicingArea />);
    expect(await screen.findByText('Nothing here yet.')).toBeInTheDocument();
  });
});
