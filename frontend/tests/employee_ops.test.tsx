import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { EmployeeOpsArea } from '../src/features/console/employee_ops';

// Every fetch returns an empty list, so the area renders its sub-navigation and
// empty states without raw-UUID inputs.
vi.stubGlobal(
  'fetch',
  vi.fn(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })),
);

describe('employee operations area', () => {
  it('renders the section navigation', async () => {
    render(<EmployeeOpsArea />);
    expect(await screen.findByText('Employee Directory')).toBeInTheDocument();
    expect(screen.getByText('Organisation')).toBeInTheDocument();
    expect(screen.getByText('Expertise')).toBeInTheDocument();
    expect(screen.getByText('Capacity')).toBeInTheDocument();
    expect(screen.getByText('Reviewer Hierarchy')).toBeInTheDocument();
  });

  it('shows an empty state rather than fabricated rows', async () => {
    render(<EmployeeOpsArea />);
    expect(await screen.findByText('No employees yet.')).toBeInTheDocument();
  });

  it('never renders a raw *_id text input in the directory form', async () => {
    const { container } = render(<EmployeeOpsArea />);
    await screen.findByText('No employees yet.');
    // Selectors resolve names; there must be no bare "*_id" labels shown as text inputs.
    const labels = Array.from(container.querySelectorAll('label')).map((l) => l.textContent ?? '');
    expect(labels.some((t) => /_id\b/.test(t))).toBe(false);
  });
});
