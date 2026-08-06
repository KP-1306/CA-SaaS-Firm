/**
 * Frontend plane and operational-console smoke tests.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { App as InternalApp } from '../src/apps/internal/App';
import { App as PortalApp } from '../src/apps/portal/App';
import { PLANES, planeLabel } from '../src/shared/plane';

vi.stubGlobal(
  'fetch',
  vi.fn(async () =>
    new Response('[]', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  ),
);

describe('plane identity', () => {
  it('defines exactly the internal and portal planes', () => {
    expect([...PLANES]).toEqual(['internal', 'portal']);
  });

  it('labels each plane distinctly', () => {
    expect(planeLabel('internal')).toBe('Internal');
    expect(planeLabel('portal')).toBe('Client Portal');
    expect(planeLabel('internal')).not.toBe(planeLabel('portal'));
  });
});

describe('internal plane', () => {
  it('renders the operational console', async () => {
    render(<InternalApp />);

    expect(
      await screen.findByRole('heading', { name: 'Dashboard' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clients' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Work' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Services' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
    });
  });
});

describe('portal plane', () => {
  it('renders its bootstrap screen', () => {
    render(<PortalApp />);
    expect(screen.getByRole('heading', { name: 'Vridhi Consultants' })).toBeInTheDocument();
    expect(screen.getByText('Client Portal')).toBeInTheDocument();
  });

  it('does not render internal-plane labelling', () => {
    render(<PortalApp />);
    expect(screen.queryByText('Internal')).not.toBeInTheDocument();
  });
});
