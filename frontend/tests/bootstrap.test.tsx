/**
 * Frontend bootstrap tests.
 *
 * Verify that both plane entry points render and that the plane separation is
 * visible in the structure. They assert on scaffolding, not behaviour, because
 * no behaviour exists yet.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App as InternalApp } from '../src/apps/internal/App';
import { App as PortalApp } from '../src/apps/portal/App';
import { PLANES, planeLabel } from '../src/shared/plane';

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
  it('renders its bootstrap screen', () => {
    render(<InternalApp />);
    expect(screen.getByRole('heading', { name: 'CA Firm Operations' })).toBeInTheDocument();
    expect(screen.getByText('Internal')).toBeInTheDocument();
    expect(screen.getByText('Bootstrap OK')).toBeInTheDocument();
  });
});

describe('portal plane', () => {
  it('renders its bootstrap screen', () => {
    render(<PortalApp />);
    expect(screen.getByRole('heading', { name: 'CA Firm Operations' })).toBeInTheDocument();
    expect(screen.getByText('Client Portal')).toBeInTheDocument();
  });

  it('does not render internal-plane labelling', () => {
    render(<PortalApp />);
    expect(screen.queryByText('Internal')).not.toBeInTheDocument();
  });
});
