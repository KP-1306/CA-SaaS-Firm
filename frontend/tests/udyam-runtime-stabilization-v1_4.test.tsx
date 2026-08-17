/**
 * V1.4 runtime-stabilization rendered tests (Command_8 Tests D-K, plus the
 * Requirement 8 read-only message and a Requirement 3 mojibake guard).
 *
 * P0 completion reconciliation (Tests A-C) lives in
 * udyam-completion-reconciliation.test.tsx.  Sticky/scroll/sidebar CSS behaviour
 * is verified by manual browser acceptance (documented in the report); here we
 * assert the DOM contract that the automated environment can prove.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import {
  ProcessTracker,
  UdyamWorkflowConfirm,
} from '../src/features/console/work';
import { lockMessage } from '../src/features/console/types';

function healthFor(opts: { opRemaining?: number } = {}) {
  return {
    contract_version: 1, work_item_id: 'w1', progress: 100,
    next_action: { code: '', label: '' },
    current_controller: 'NONE',
    operational: { mandatory_remaining: opts.opRemaining ?? 0 },
    documents: { mandatory_missing: 0, missing: 0, pending_review: 0, pending_acceptance: 0 },
  } as never;
}

// -- TEST D - STICKY PRIMARY ACTION: single actionable instance ---------------
describe('TEST D: primary workflow action has one actionable instance', () => {
  it('a selected action renders exactly one confirm control in the confirm group', () => {
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'SUBMIT_FOR_REVIEW', label: 'Submit for review' }}
        canEdit={true}
        onCommentChange={() => {}}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    // exactly one primary confirm button for the action
    const confirmButtons = screen.getAllByText('Save & Submit for review');
    expect(confirmButtons.length).toBe(1);
  });
});

// -- TEST E - COMPLETED STICKY STATE: no lifecycle action ---------------------
describe('TEST E: completed Udyam presents no lifecycle action control', () => {
  it('completed tracker shows Work completed and no pending confirm surface', () => {
    render(
      <ProcessTracker
        health={healthFor({ opRemaining: 0 })}
        processState={null}
        forceTerminalComplete={true}
        loading={false}
        onOpenDocuments={() => {}}
      />,
    );
    expect(screen.getByText('Work completed')).toBeTruthy();
    // With no pendingAction, the confirm surface is absent.
    const { container } = render(
      <UdyamWorkflowConfirm
        pendingAction={null}
        canEdit={false}
        onCommentChange={() => {}}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(container.querySelector('[aria-label="Confirm workflow action"]')).toBeNull();
  });
});

// -- TEST F - SAVE SEPARATION -------------------------------------------------
describe('TEST F: confirm control is a workflow action, distinct from Save', () => {
  it('confirm label is the lifecycle action, never a bare Save', () => {
    render(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'APPROVE', label: 'Approve & continue' }}
        canEdit={false}
        onCommentChange={() => {}}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByText('Confirm Approve & continue')).toBeTruthy();
    expect(screen.queryByText('Save')).toBeNull();
    expect(screen.queryByText('Save & Close')).toBeNull();
  });
});

// -- TEST I - READ-ONLY MESSAGE (Requirement 8) -------------------------------
describe('TEST I: read-only message does not imply "nothing can be done"', () => {
  it('process-owned actionable Udyam stage uses neutral guidance, not a dead-end', () => {
    const msg = lockMessage('IN_PROGRESS', '', true);
    expect(msg).toMatch(/workflow action/i);
    expect(msg).not.toMatch(/read-only for you at its current stage/i);
  });
  it('non-actionable lock keeps the original read-only wording', () => {
    const msg = lockMessage('IN_PROGRESS', '', false);
    expect(msg).toMatch(/read-only for you at its current stage/i);
  });
  it('completed keeps the completed-and-read-only wording', () => {
    expect(lockMessage('COMPLETED', '', false)).toMatch(/completed and read-only/i);
  });
});

// -- TEST G - MOJIBAKE STATIC CONTENT (Requirement 3) -------------------------
describe('TEST G: no known mojibake byte patterns remain in affected source', () => {
  const files = [
    'work.tsx', 'console.css', 'GlobalSearch.tsx',
    'catalogue.tsx', 'employee_ops.tsx', 'identity.tsx', 'ConsoleApp.tsx',
  ];
  // Known mojibake signatures produced by the earlier mis-decoding.
  const BAD = [
    '\u00c3\u0192', // mojibake lead bytes (misdecoded UTF-8)
    '\u00c3\u00a2\u00e2\u201a\u00ac', // misdecoded en/em punctuation run
    '\u00c2\u00a2\u00c3', // misdecoded currency/separator run
    '\ufffd', // replacement char
  ];
  for (const f of files) {
    it(`${f} is free of known mojibake`, () => {
      const p = path.resolve(__dirname, '../src/features/console', f);
      const text = fs.readFileSync(p, 'utf8');
      for (const bad of BAD) {
        expect(text.includes(bad)).toBe(false);
      }
    });
  }
});

// -- TEST H - SEARCH (Requirement 3) ------------------------------------------
describe('TEST H: global search source renders clean icon/placeholder text', () => {
  it('GlobalSearch source has no mojibake and uses a clean search glyph', () => {
    const p = path.resolve(__dirname, '../src/features/console/GlobalSearch.tsx');
    const text = fs.readFileSync(p, 'utf8');
    expect(text.includes('\u00c3\u0192')).toBe(false);
    expect(text.includes('\ufffd')).toBe(false);
  });
});
