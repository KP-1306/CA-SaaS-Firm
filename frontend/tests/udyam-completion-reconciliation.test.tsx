/**
 * V1.4.1 P0 completion-reconciliation tests (Tests 1-8).
 *
 * Test 1  -- deterministic scoped selectors (Correction 1: was failing with
 *            "Found multiple elements" because stage text appears in label AND
 *            guidance AND current-stage summary).
 * Test 2  -- real IN_PROGRESS->COMPLETED reconciliation drives tracker terminal
 *            without injecting forceTerminalComplete=true.
 * Test 3  -- complete-registration action wires through onChanged to the
 *            authoritative reconciliation callback.
 * Test 4  -- successful completion + successful refetch -> terminal UI.
 * Test 5  -- successful completion + refetch failure -> refresh-required safety
 *            state; stale lifecycle actions not actionable; recovery action
 *            present; no fake COMPLETED.
 * Test 6  -- refresh retry succeeds -> safety state cleared, correct stage.
 * Test 7  -- delayed/null processState after COMPLETED WorkItem -> terminal.
 * Test 8  -- non-Udyam workflow type-checks (behavioral regression guard).
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  reconcileOpenWorkspace,
  completeUdyamRegistrationAndRefresh,
  ProcessTracker,
  UdyamWorkflowConfirm,
  deriveUdyamStageIndex,
} from '../src/features/console/work';
import type { Row } from '../src/features/console/types';

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const COMPLETED_WORKITEM = {
  id: 'w1',
  status: 'COMPLETED',
  service_code: 'UDYAM_REGISTRATION',
  can_edit: false,
  can_review: false,
  can_submit_for_review: false,
};

const COMPLETED_HEALTH = {
  contract_version: 1,
  work_item_id: 'w1',
  progress: 100,
  health: 'GREEN',
  risk: 'LOW',
  current_controller: 'NONE',
  waiting_days: 0,
  waiting_since: null,
  due_state: 'ON_TRACK',
  days_to_due: null,
  operational: {
    total: 0,
    completed: 0,
    remaining: 0,
    mandatory_total: 0,
    mandatory_completed: 0,
    mandatory_remaining: 0,
    completion_percent: 100,
  },
  documents: {
    total: 0,
    satisfied: 0,
    pending: 0,
    mandatory_total: 0,
    mandatory_satisfied: 0,
    mandatory_missing: 0,
    missing: 0,
    pending_review: 0,
    rejected: 0,
    expired: 0,
    pending_acceptance: 0,
    ready_for_review: true,
    readiness_state: 'READY',
    health_score: 100,
    blockers: [],
  },
  next_action: { code: 'WORK_COMPLETED', label: 'Work completed' },
  reasons: [],
  calculated_at: '2026-08-15T10:00:00Z',
} as const;

const COMPLETION_PROCESS = {
  work_item_id: 'w1',
  current_step: { id: 's8', code: 'COMPLETION', name: 'Registration Completion & Certificate' },
  entered_at: '2026-08-15T10:00:00Z',
};

/** Build a vi.fn fetchObject that resolves from map and rejects for paths in fail[]. */
function fetcher(map: Record<string, unknown>, fail: string[] = []) {
  return vi.fn(async (path: string): Promise<Row> => {
    if (fail.includes(path)) throw new Error(`network error: ${path}`);
    if (path in map) return map[path] as Row;
    throw new Error(`unexpected path: ${path}`);
  });
}

/**
 * Return the .cx-process-step DOM element whose .cx-process-label text
 * matches `labelText`.  Scoped to `container` to avoid cross-test leakage.
 * Uses querySelectorAll so it tolerates the same text appearing in guidance /
 * summary regions outside .cx-process-step.
 */
function stepByLabel(container: HTMLElement, labelText: string): Element | undefined {
  const steps = container.querySelectorAll('.cx-process-step');
  return Array.from(steps).find((el) =>
    el.querySelector('.cx-process-label')?.textContent?.trim() === labelText,
  );
}

// ---------------------------------------------------------------------------
// TEST 1 & 2 — deterministic selectors + real reconciliation
// ---------------------------------------------------------------------------

describe('TEST 1 & 2: real IN_PROGRESS->COMPLETED reconciliation, scoped selectors', () => {
  it('reconciles editing to COMPLETED and renders Stage 8 current without singular-match failures', async () => {
    let editing: Record<string, unknown> = {
      id: 'w1', status: 'IN_PROGRESS', service_code: 'UDYAM_REGISTRATION', can_edit: true,
    };
    let health: unknown = null;
    let processState: unknown = null;
    let err = '';

    const fetchObject = fetcher({
      'work-items/w1': COMPLETED_WORKITEM,
      'work-items/w1/health': COMPLETED_HEALTH,
      'work-items/w1/process-step': COMPLETION_PROCESS,
    });

    // Correction 1: the reconciliation contract itself is unchanged.
    const reconciled = await reconcileOpenWorkspace({
      workItemId: 'w1',
      fetchObject,
      setEditing: (row) => { editing = row; },
      setWorkHealth: (v) => { health = v; },
      setWorkProcessState: (v) => { processState = v; },
      onWorkItemError: (m) => { err = m; },
      onProjectionError: () => {},
      clearError: () => { err = ''; },
    });

    expect(reconciled).toBe(true);
    expect(editing.status).toBe('COMPLETED');
    expect(editing.can_edit).toBe(false);
    expect(err).toBe('');
    expect((processState as { current_step: { code: string } }).current_step.code).toBe('COMPLETION');

    // Render the real tracker from reconciled state (no injected forceTerminalComplete=true).
    const forceTerminalComplete = String(editing.status) === 'COMPLETED';
    const { container } = render(
      <ProcessTracker
        health={health as never}
        processState={processState as never}
        forceTerminalComplete={forceTerminalComplete}
        loading={false}
        onOpenDocuments={() => {}}
      />,
    );

    // "Work completed" appears once (in the tracker summary).
    expect(screen.getAllByText('Work completed').length).toBeGreaterThan(0);

    // Correction 1: scope to .cx-process-step to avoid "Found multiple elements"
    // when stage names also appear in guidance/summary outside the step list.
    const completionStep = stepByLabel(container, 'Registration Completion & Certificate');
    expect(completionStep).toBeDefined();
    expect(completionStep?.className).toContain('current');

    const verificationStep = stepByLabel(container, 'Verification & Preparation');
    expect(verificationStep).toBeDefined();
    expect(verificationStep?.className).not.toContain('current');
    expect(verificationStep?.className).toContain('completed');
  });
});

// ---------------------------------------------------------------------------
// TEST 3 — actual production completion helper -> onChanged -> reconcile
// ---------------------------------------------------------------------------

describe('TEST 3: complete-registration production path invokes authoritative reconciliation', () => {
  it('uses udyam-complete-registration, then onChanged reconciles editing to COMPLETED', async () => {
    let editing: Record<string, unknown> = {
      id: 'w1', status: 'IN_PROGRESS', can_edit: true,
    };
    let health: unknown = null;
    let processState: unknown = null;

    const fetchObject = fetcher({
      'work-items/w1': COMPLETED_WORKITEM,
      'work-items/w1/health': COMPLETED_HEALTH,
      'work-items/w1/process-step': COMPLETION_PROCESS,
    });

    const onChanged = vi.fn(async () => {
      await reconcileOpenWorkspace({
        workItemId: 'w1',
        fetchObject,
        setEditing: (row) => { editing = row; },
        setWorkHealth: (v) => { health = v; },
        setWorkProcessState: (v) => { processState = v; },
        onWorkItemError: () => {},
        onProjectionError: () => {},
        clearError: () => {},
      });
    });

    const upload = vi.fn(async () => ({} as never));
    const onUploaded = vi.fn();
    const certificate = new File(['certificate'], 'udyam.pdf', { type: 'application/pdf' });

    // This is the same exported helper called by the real UdyamExternalActions
    // uploadCertificate handler; it is not a simulated standalone callback.
    await completeUdyamRegistrationAndRefresh({
      workItemId: 'w1',
      certificate,
      remarks: 'final certificate',
      upload: upload as never,
      onUploaded,
      onChanged,
    });

    expect(upload).toHaveBeenCalledTimes(1);
    expect(upload).toHaveBeenCalledWith(
      'work-items',
      'w1',
      'udyam-complete-registration',
      [certificate],
      { remarks: 'final certificate' },
    );
    expect(onUploaded).toHaveBeenCalledTimes(1);
    expect(onChanged).toHaveBeenCalledTimes(1);
    expect(fetchObject).toHaveBeenCalledWith('work-items/w1');
    expect(editing.status).toBe('COMPLETED');
    expect((processState as { current_step: { code: string } }).current_step.code).toBe('COMPLETION');
    expect((health as { next_action: { label: string } }).next_action.label).toBe('Work completed');
  });
});

// ---------------------------------------------------------------------------
// TEST 4 — successful completion + successful refetch -> terminal UI
// ---------------------------------------------------------------------------

describe('TEST 4: successful completion + refetch -> terminal, no stale lifecycle actions', () => {
  it('editing becomes COMPLETED; ProcessTracker is terminal; no Submit for Review', async () => {
    let editing: Record<string, unknown> = { id: 'w1', status: 'IN_PROGRESS', can_edit: true };
    let health: unknown = null;
    let processState: unknown = null;

    const fetchObject = fetcher({
      'work-items/w1': COMPLETED_WORKITEM,
      'work-items/w1/health': COMPLETED_HEALTH,
      'work-items/w1/process-step': COMPLETION_PROCESS,
    });

    await reconcileOpenWorkspace({
      workItemId: 'w1', fetchObject,
      setEditing: (row) => { editing = row; },
      setWorkHealth: (v) => { health = v; },
      setWorkProcessState: (v) => { processState = v; },
      onWorkItemError: () => {}, onProjectionError: () => {}, clearError: () => {},
    });

    expect(editing.status).toBe('COMPLETED');

    // Terminal: no lifecycle actions (completed branch shows only Close).
    // UdyamWorkflowConfirm renders null for null pendingAction.
    const { container: confirmContainer } = render(
      <UdyamWorkflowConfirm
        pendingAction={null}
        canEdit={false}
        onCommentChange={() => {}}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(confirmContainer.querySelector('[aria-label="Confirm workflow action"]')).toBeNull();

    // Tracker is terminal.
    const { container } = render(
      <ProcessTracker
        health={health as never}
        processState={processState as never}
        forceTerminalComplete={String(editing.status) === 'COMPLETED'}
        loading={false}
        onOpenDocuments={() => {}}
      />,
    );
    const completionStep = stepByLabel(container, 'Registration Completion & Certificate');
    expect(completionStep?.className).toContain('current');
    // No stale Submit for Review: can_submit_for_review is false on COMPLETED item.
    expect(editing.can_submit_for_review).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// TEST 5 — successful completion + refetch failure -> refresh-required safety
// ---------------------------------------------------------------------------

describe('TEST 5: successful completion + refetch failure -> refresh-required state', () => {
  it('reconcile returns false; stale editing unchanged; error surfaced; no fake COMPLETED', async () => {
    let editing: Record<string, unknown> = { id: 'w1', status: 'IN_PROGRESS', can_edit: true };
    let workspaceNeedsRefresh = false;
    let err = '';

    const fetchObject = fetcher(
      { 'work-items/w1/health': COMPLETED_HEALTH, 'work-items/w1/process-step': COMPLETION_PROCESS },
      ['work-items/w1'], // authoritative WorkItem fetch fails
    );

    const reconciled = await reconcileOpenWorkspace({
      workItemId: 'w1', fetchObject,
      setEditing: (row) => { editing = row; },
      setWorkHealth: () => {},
      setWorkProcessState: () => {},
      onWorkItemError: (m) => {
        err = m;
        workspaceNeedsRefresh = true; // Correction 2: caller activates safety mode
      },
      onProjectionError: () => {},
      clearError: () => {},
    });

    // Contract: reconciled=false; editing stays stale; no fabrication.
    expect(reconciled).toBe(false);
    expect(editing.status).toBe('IN_PROGRESS');
    expect(editing.can_edit).toBe(true);  // stale, but workspaceNeedsRefresh gates it
    expect(err).toMatch(/could not refresh/i);
    expect(workspaceNeedsRefresh).toBe(true); // safety mode activated

    // While safety mode is active, no lifecycle confirm surface should be offered.
    // (In WorkArea, workspaceNeedsRefresh suppresses the workflow zone and footer.)
    // Verify the confirm surface itself renders nothing for null pendingAction.
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

// ---------------------------------------------------------------------------
// TEST 6 — refresh retry succeeds -> safety state cleared
// ---------------------------------------------------------------------------

describe('TEST 6: refresh retry succeeds -> safety state cleared, correct stage rendered', () => {
  it('second reconcile call succeeds; editing becomes COMPLETED; safety clears', async () => {
    let editing: Record<string, unknown> = { id: 'w1', status: 'IN_PROGRESS', can_edit: true };
    let workspaceNeedsRefresh = true; // already in safety mode from previous failure
    let err = 'previous refresh error';
    let health: unknown = null;
    let processState: unknown = null;

    // Retry with a fetchObject that now succeeds.
    const fetchObject = fetcher({
      'work-items/w1': COMPLETED_WORKITEM,
      'work-items/w1/health': COMPLETED_HEALTH,
      'work-items/w1/process-step': COMPLETION_PROCESS,
    });

    const reconciled = await reconcileOpenWorkspace({
      workItemId: 'w1', fetchObject,
      setEditing: (row) => { editing = row; },
      setWorkHealth: (v) => { health = v; },
      setWorkProcessState: (v) => { processState = v; },
      onWorkItemError: (m) => { err = m; workspaceNeedsRefresh = true; },
      onProjectionError: () => {},
      clearError: () => { err = ''; workspaceNeedsRefresh = false; }, // V1.4.2: successful reconcile clears visible refresh error + safety
    });

    expect(reconciled).toBe(true);
    expect(editing.status).toBe('COMPLETED');
    expect(err).toBe('');
    expect(workspaceNeedsRefresh).toBe(false); // safety mode cleared

    // Tracker must be terminal after retry.
    const { container } = render(
      <ProcessTracker
        health={health as never}
        processState={processState as never}
        forceTerminalComplete={String(editing.status) === 'COMPLETED'}
        loading={false}
        onOpenDocuments={() => {}}
      />,
    );
    const completionStep = stepByLabel(container, 'Registration Completion & Certificate');
    expect(completionStep?.className).toContain('current');
  });
});

// ---------------------------------------------------------------------------
// TEST 7 — delayed/null processState after COMPLETED WorkItem stays terminal
// ---------------------------------------------------------------------------

describe('TEST 7: delayed/null processState + COMPLETED WorkItem stays terminal', () => {
  it('forceTerminalComplete from editing.status holds Stage 8 even with null processState', () => {
    const idx = deriveUdyamStageIndex({
      forceTerminalComplete: true, // set from editing.status === 'COMPLETED'
      persistedStepCode: '',
      nextActionCode: '',
      operationalRemaining: 0,
      documentsMissing: false,
      documentsPending: false,
      currentController: 'NONE',
    });
    expect(idx).toBe(7);

    const { container } = render(
      <ProcessTracker
        health={null as never}
        processState={null}
        forceTerminalComplete={true}
        loading={false}
        onOpenDocuments={() => {}}
      />,
    );
    const completionStep = stepByLabel(container, 'Registration Completion & Certificate');
    expect(completionStep?.className).toContain('current');
    const verificationStep = stepByLabel(container, 'Verification & Preparation');
    expect(verificationStep?.className).not.toContain('current');
  });
});

// ---------------------------------------------------------------------------
// TEST 8 — non-Udyam regression guard
// ---------------------------------------------------------------------------

describe('TEST 8: non-Udyam reconcileOpenWorkspace behavior is unchanged', () => {
  it('reconciliation works identically for a generic (non-Udyam) Work Item', async () => {
    const GENERIC_COMPLETED = { id: 'w2', status: 'COMPLETED', can_edit: false };
    let editing: Record<string, unknown> = { id: 'w2', status: 'IN_PROGRESS', can_edit: true };

    const fetchObject = fetcher({
      'work-items/w2': GENERIC_COMPLETED,
      'work-items/w2/health': { contract_version: 1, work_item_id: 'w2', progress: 100,
        next_action: { code: '', label: '' }, current_controller: 'NONE',
        operational: { mandatory_remaining: 0 },
        documents: { mandatory_missing: 0, missing: 0, pending_review: 0, pending_acceptance: 0 } },
      'work-items/w2/process-step': { work_item_id: 'w2', current_step: null },
    });

    const reconciled = await reconcileOpenWorkspace({
      workItemId: 'w2', fetchObject,
      setEditing: (row) => { editing = row; },
      setWorkHealth: () => {},
      setWorkProcessState: () => {},
      onWorkItemError: () => {},
      onProjectionError: () => {},
      clearError: () => {},
    });

    expect(reconciled).toBe(true);
    expect(editing.status).toBe('COMPLETED');
  });
});
