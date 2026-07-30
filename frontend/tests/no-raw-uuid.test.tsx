import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CatalogueArea } from '../src/features/console/catalogue';

vi.stubGlobal(
  'fetch',
  vi.fn(async () => new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } })),
);

describe('catalogue forms', () => {
  it('never renders an input named for a raw id field', () => {
    const { container } = render(<CatalogueArea />);
    // No text input should be bound to *_id in the catalogue workflow.
    const labels = Array.from(container.querySelectorAll('label')).map((l) => l.textContent ?? '');
    expect(labels.some((t) => /_id\b/.test(t))).toBe(false);
  });
});
