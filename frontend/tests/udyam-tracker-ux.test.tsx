/**
 * V1.3 rendered tests â€” 8-stage tracker, terminal projection, and the
 * top-zone workflow confirmation surface (UdyamWorkflowConfirm).
 * Corresponds to Command_7 Â§11 Tests 1-16 (rendered where applicable).
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  ProcessTracker,
  UdyamWorkflowConfirm,
  UDYAM_JOURNEY,
  UDYAM_STAGE_GUIDANCE,
  deriveUdyamStageIndex,
} from '../src/features/console/work';

const STAGE_NAMES = [
  'Client Information & Documents',
  'Verification & Preparation',
  'Internal Review & Approval',
  'Application Reviewed',
  'Submit Application',
  'Application Submitted',
  'Query / OTP / Technical Resolution',
  'Registration Completion & Certificate',
];

function healthFor(opts: { controller?: string; nextAction?: string; opRemaining?: number } = {}) {
  return {
    contract_version: 1, work_item_id: 'w1', progress: 50,
    next_action: { code: opts.nextAction ?? '', label: '' },
    current_controller: opts.controller ?? 'OWNER',
    operational: { mandatory_remaining: opts.opRemaining ?? 1 },
    documents: { mandatory_missing: 0, missing: 0, pending_review: 0, pending_acceptance: 0 },
  } as never;
}

// TEST 1: 8 stages
describe('TEST 1: 8-stage journey renders', () => {
  it('shows all 8 stage labels', () => {
    render(<ProcessTracker health={healthFor()} processState={null}
      forceTerminalComplete={false} loading={false} onOpenDocuments={() => {}} />);
    for (const name of STAGE_NAMES) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    }
  });
  it('journey has exactly 8 entries incl Application Reviewed and Submit Application', () => {
    expect(UDYAM_JOURNEY.length).toBe(8);
    const codes = UDYAM_JOURNEY.map((s) => s.code);
    expect(codes).toContain('APPLICATION_REVIEWED');
    expect(codes).toContain('SUBMIT_APPLICATION');
  });
});

// TEST 2: terminal with stale process snapshot
describe('TEST 2: completed Udyam with processState=null stays terminal', () => {
  it('Stage 8 current, Work completed, Stage 2 not current', () => {
    render(<ProcessTracker health={healthFor({ opRemaining: 0 })} processState={null}
      forceTerminalComplete={true} loading={false} onOpenDocuments={() => {}} />);
    expect(screen.getByText('Work completed')).toBeTruthy();
    const completion = screen.getAllByText('Registration Completion & Certificate')
      .map((element) => element.closest('.cx-process-step'))
      .find((element) => element !== null);
    expect(completion?.className).toContain('current');
    const verification = screen.getAllByText('Verification & Preparation')
      .map((element) => element.closest('.cx-process-step'))
      .find((element) => element !== null);
    expect(verification?.className).not.toContain('current');
    expect(verification?.className).toContain('completed');
  });
  it('deriveUdyamStageIndex forceTerminalComplete=true returns 7', () => {
    expect(deriveUdyamStageIndex({
      forceTerminalComplete: true, persistedStepCode: '', nextActionCode: '',
      operationalRemaining: 0, documentsMissing: false, documentsPending: false,
      currentController: 'OWNER',
    })).toBe(7);
  });
});

// Guidance (all 8) + keyboard
describe('Guidance for all 8 stages, keyboard accessible', () => {
  it('every stage code has guidance', () => {
    for (const s of UDYAM_JOURNEY) {
      expect(UDYAM_STAGE_GUIDANCE[s.code]).toBeTruthy();
    }
  });
  it('renders 8 tooltips, all keyboard-focusable', () => {
    const { container } = render(<ProcessTracker health={healthFor()} processState={null}
      forceTerminalComplete={false} loading={false} onOpenDocuments={() => {}} />);
    expect(container.querySelectorAll('[role="tooltip"]').length).toBe(8);
    expect(container.querySelectorAll('.cx-process-step-guided[tabindex="0"]').length).toBe(8);
  });
});

// TEST 4/5: Submit for Review confirmation is in the top zone
describe('TEST 4/5: Submit for Review completes in the top workflow zone', () => {
  it('renders confirm control and calls onConfirm', () => {
    const onConfirm = vi.fn();
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' }}
        canEdit={true} onCommentChange={() => {}} onConfirm={onConfirm} onCancel={() => {}} />,
    );
    const btn = screen.getByText('Save & Submit for review');
    expect(btn).toBeTruthy();
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
  it('reviewer (cannot edit) sees Confirm label, not Save &', () => {
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'APPROVE', label: 'Approve & continue' }}
        canEdit={false} onCommentChange={() => {}} onConfirm={() => {}} onCancel={() => {}} />,
    );
    expect(screen.getByText('Confirm Approve & continue')).toBeTruthy();
  });
});

// TEST 8/9/10: Return for Rework justification + validation in top zone
describe('TEST 8/9/10: Return for Rework justification and confirm in top zone', () => {
  it('justification textarea renders in the same confirm group', () => {
    const { container } = render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'RETURN_FOR_REWORK', label: 'Return for rework', comment: '' }}
        canEdit={false} onCommentChange={() => {}} onConfirm={() => {}} onCancel={() => {}} />,
    );
    const group = container.querySelector('[aria-label="Confirm workflow action"]');
    expect(group).toBeTruthy();
    expect(group?.querySelector('#udyam-reviewer-return-justification')).toBeTruthy();
  });
  it('TEST 9: confirm disabled while justification blank', () => {
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'RETURN_FOR_REWORK', label: 'Return for rework', comment: '   ' }}
        canEdit={false} onCommentChange={() => {}} onConfirm={() => {}} onCancel={() => {}} />,
    );
    const btn = screen.getByText('Confirm Return for rework') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
  it('TEST 10: confirm enabled and fires with justification present', () => {
    const onConfirm = vi.fn();
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'RETURN_FOR_REWORK', label: 'Return for rework', comment: 'Please fix the PAN.' }}
        canEdit={false} onCommentChange={() => {}} onConfirm={onConfirm} onCancel={() => {}} />,
    );
    const btn = screen.getByText('Confirm Return for rework') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
  it('typing justification calls onCommentChange', () => {
    const onCommentChange = vi.fn();
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'RETURN_FOR_REWORK', label: 'Return for rework', comment: '' }}
        canEdit={false} onCommentChange={onCommentChange} onConfirm={() => {}} onCancel={() => {}} />,
    );
    fireEvent.change(screen.getByLabelText('Reviewer return justification *'), {
      target: { value: 'Fix address' },
    });
    expect(onCommentChange).toHaveBeenCalledWith('Fix address');
  });
});

// Confirm surface hidden when nothing pending
describe('No pending action means no confirm surface', () => {
  it('renders nothing', () => {
    const { container } = render(
      <UdyamWorkflowConfirm
        pendingAction={null} canEdit={true}
        onCommentChange={() => {}} onConfirm={() => {}} onCancel={() => {}} />,
    );
    expect(container.querySelector('[aria-label="Confirm workflow action"]')).toBeNull();
  });
});
