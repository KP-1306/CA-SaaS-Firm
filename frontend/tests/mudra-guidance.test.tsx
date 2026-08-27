import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  MUDRA_STAGE_GUIDANCE,
  MUDRA_STAGE_ORDER,
  MudraProcessTracker,
} from '../src/features/console/work';

describe('Mudra presentation-only stage guidance', () => {
  it('provides complete business guidance for every Mudra process stage', () => {
    expect(MUDRA_STAGE_ORDER).toHaveLength(10);

    for (const code of MUDRA_STAGE_ORDER) {
      const guidance =
        MUDRA_STAGE_GUIDANCE[
          code as keyof typeof MUDRA_STAGE_GUIDANCE
        ];

      expect(guidance).toBeDefined();

      if (!guidance) {
        throw new Error(`Missing Mudra guidance for ${code}`);
      }

      expect(guidance.meaning.trim()).not.toBe('');
      expect(guidance.previous.trim()).not.toBe('');
      expect(guidance.todo.trim()).not.toBe('');
      expect(guidance.required.trim()).not.toBe('');
      expect(guidance.next.trim()).not.toBe('');
      expect(Array.isArray(guidance.actions)).toBe(true);
    }
  });

  it('renders guidance tooltips for all 10 tracker stages without changing stage position', () => {
    const { container } = render(
      <MudraProcessTracker
        currentCode="CREDIT_ELIGIBILITY"
        rejected={false}
      />,
    );

    expect(container.querySelectorAll('[role="tooltip"]')).toHaveLength(10);

    const current = container.querySelector(
      '[data-testid="mudra-stage-CREDIT_ELIGIBILITY"]',
    );

    expect(current?.className).toContain('cx-process-step-current');

    expect(
      container.querySelector('[data-testid="mudra-stage-APPLICATION"]')
        ?.className,
    ).toContain('cx-process-step-complete');

    expect(
      container.querySelector('[data-testid="mudra-stage-FILE_PREPARATION"]')
        ?.className,
    ).not.toContain('cx-process-step-complete');
  });

  it('keeps Closed guidance terminal and action-free', () => {
    const closed = MUDRA_STAGE_GUIDANCE.CLOSED;

    expect(closed.actions).toHaveLength(0);
    expect(closed.next).toMatch(/process complete/i);
  });
});
