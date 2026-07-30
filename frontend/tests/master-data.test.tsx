import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { MasterDataApp } from '../src/features/master-data/MasterDataApp';

vi.stubGlobal(
  'fetch',
  vi.fn(async () =>
    new Response('[]', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  ),
);

describe('master data', () => {
  it('renders the locked Layer 2 modules', () => {
    render(<MasterDataApp />);

    expect(screen.getAllByText('Clients').length).toBeGreaterThan(0);
    expect(screen.queryByText('Work Catalogue', { exact: false })).not.toBeInTheDocument();
    expect(screen.getByText('Verticals')).toBeInTheDocument();
    expect(screen.getByText('Employees')).toBeInTheDocument();
  });
});
