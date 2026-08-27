import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  MUDRA_STAGE_ORDER,
  MudraExternalActions,
  MudraProcessTracker,
  UdyamWorkflowConfirm,
  reconcileStalePendingAction,
} from '../src/features/console/work';
import type { PendingWorkAction, WorkHealthSnapshot } from '../src/features/console/work';

/*
 * Mudra end-to-end frontend tests.
 *
 * Proves: select-then-confirm before any backend mutation, one active
 * pending-operation form at a time in Bank Pending, the terminal
 * rejected/closed panels render instead of an action form, the collapsible
 * panel is presentation-only, and the tracker reflects the authoritative
 * current stage (not a frontend-invented position).
 */

type FetchCall = { url: string; method: string; body: string };

function stubFetch(): { calls: FetchCall[] } {
  const calls: FetchCall[] = [];
  const fn = vi.fn(async (url: string, init: RequestInit) => {
    calls.push({
      url: String(url),
      method: String(init?.method ?? 'GET'),
      body: String(init?.body ?? ''),
    });
    return new Response(JSON.stringify({ id: 'w1' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fn);
  return { calls };
}

function processState(code: string) {
  return {
    work_item_id: 'w1',
    current_step: { id: code, code, name: code },
    entered_at: null,
    entered_by: null,
    note: '',
  };
}

describe('Mudra tracker', () => {
  it('renders all 10 stages and marks the current one', () => {
    render(
      <MudraProcessTracker currentCode="BANK_VERIFICATION" rejected={false} />,
    );
    for (const code of MUDRA_STAGE_ORDER) {
      expect(screen.getByTestId(`mudra-stage-${code}`)).toBeTruthy();
    }
    const current = screen.getByTestId('mudra-stage-BANK_VERIFICATION');
    expect(current.className).toContain('cx-process-step-current');
    // Earlier stages are marked complete.
    const earlier = screen.getByTestId('mudra-stage-APPLICATION');
    expect(earlier.className).toContain('cx-process-step-complete');
  });

  it('shows a Rejected marker and no current-stage highlight when rejected', () => {
    render(
      <MudraProcessTracker currentCode="CREDIT_ELIGIBILITY" rejected={true} />,
    );
    expect(screen.getByTestId('mudra-stage-REJECTED')).toBeTruthy();
    const elig = screen.getByTestId('mudra-stage-CREDIT_ELIGIBILITY');
    expect(elig.className).not.toContain('cx-process-step-current');
  });
});

describe('Mudra APPLICATION - Save / Save & Close (UDYAM-parity persistence UX)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('1: APPLICATION shows exactly Save and Save & Close as its persistence choices', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText('Save')).toBeTruthy();
    expect(screen.getByText('Save & Close')).toBeTruthy();
    // No third, differently-named persistence action.
    expect(screen.queryByText('Save Application & KYC Details')).toBeNull();
    expect(screen.queryByText('Save Application Details')).toBeNull();
  });

  it('2: Save invokes mudra-complete-application, persists the five fields, and stays open', async () => {
    const { calls } = stubFetch();
    const onChanged = vi.fn(async () => {});
    const onCloseWorkspace = vi.fn();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={onChanged}
        onError={() => {}}
        onCloseWorkspace={onCloseWorkspace}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });
    fireEvent.change(screen.getByLabelText('Business activity'), {
      target: { value: 'Retail trading' },
    });
    fireEvent.change(screen.getByLabelText('Application reference'), {
      target: { value: 'REF-1' },
    });
    fireEvent.change(screen.getByLabelText('Application date'), {
      target: { value: '2026-08-20' },
    });

    // No select-then-confirm ceremony: Save calls the backend directly.
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(
        calls.filter((c) => c.url.includes('mudra-complete-application')).length,
      ).toBe(1);
    });
    const call = calls.find((c) => c.url.includes('mudra-complete-application'));
    const body = JSON.parse(call?.body ?? '{}');
    expect(body).toMatchObject({
      requested_loan_amount: '50000',
      loan_purpose: 'Working capital',
      business_activity: 'Retail trading',
      application_reference: 'REF-1',
      application_date: '2026-08-20',
    });
    expect(onChanged).toHaveBeenCalledTimes(1);
    // Stays open: workspace close is never requested by Save.
    expect(onCloseWorkspace).not.toHaveBeenCalled();
  });

  it('3: Save & Close invokes the same endpoint and requests closure only after successful persistence', async () => {
    const { calls } = stubFetch();
    const onChanged = vi.fn(async () => {});
    const onCloseWorkspace = vi.fn();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={onChanged}
        onError={() => {}}
        onCloseWorkspace={onCloseWorkspace}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });

    fireEvent.click(screen.getByText('Save & Close'));
    await waitFor(() => {
      expect(
        calls.filter((c) => c.url.includes('mudra-complete-application')).length,
      ).toBe(1);
    });
    await waitFor(() => {
      expect(onCloseWorkspace).toHaveBeenCalledTimes(1);
    });
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('3b: Save & Close does NOT request closure when persistence fails', async () => {
    const onCloseWorkspace = vi.fn();
    const fn = vi.fn(async () => new Response('server error', { status: 500 }));
    vi.stubGlobal('fetch', fn);
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
        onCloseWorkspace={onCloseWorkspace}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });
    fireEvent.click(screen.getByText('Save & Close'));
    await waitFor(() => {
      expect(fn).toHaveBeenCalled();
    });
    expect(onCloseWorkspace).not.toHaveBeenCalled();
  });

  it('4: neither Save nor Save & Close advances to CREDIT_ELIGIBILITY', async () => {
    // The backend endpoint they call is unchanged and never advances the
    // process position - this proves the frontend never fakes/implies an
    // advance either. Since the mocked onChanged() does not change
    // processState, the panel should still show the same APPLICATION-stage
    // fields after either action, not a different stage's UI.
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByLabelText('Loan purpose')).toBeTruthy();
    });
    expect(screen.queryByLabelText('CIBIL score')).toBeNull();
  });

  it('5: Submit for Review remains separate - Save and Save & Close never call it', async () => {
    // Submit for Review lives in reviewButtons, outside this component, and
    // this component only ever targets one action name.
    const { calls } = stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    expect(
      calls.every((c) => !c.url.includes('submit_for_review')),
    ).toBe(true);
    expect(
      calls.every(
        (c) =>
          !c.url.includes('work-items/') ||
          c.url.includes('mudra-complete-application'),
      ),
    ).toBe(true);
  });

  it('Save and Save & Close are both disabled until the required fields are filled', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(true);
    expect(
      (screen.getByText('Save & Close') as HTMLButtonElement).disabled,
    ).toBe(true);

    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital' },
    });
    expect((screen.getByText('Save') as HTMLButtonElement).disabled).toBe(false);
    expect(
      (screen.getByText('Save & Close') as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('shows an awaiting-review, non-editable view once submitted for review', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          status: 'READY_FOR_REVIEW',
          operational_data: {},
        }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText(/submitted for internal review/i)).toBeTruthy();
    expect(screen.queryByLabelText('Requested loan amount')).toBeNull();
    expect(screen.queryByText('Save')).toBeNull();
    expect(screen.queryByText('Save & Close')).toBeNull();
  });
});

describe('Mudra APPLICATION - value precedence (local edit -> persisted -> empty)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const PERSISTED = {
    requested_loan_amount: '75000',
    loan_purpose: 'Equipment purchase',
    business_activity: 'Manufacturing',
    application_reference: 'REF-9',
    application_date: '2026-08-01',
  };

  it('1: pre-existing operational_data populates all five APPLICATION fields on initial render', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: PERSISTED }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(
      (screen.getByLabelText('Requested loan amount') as HTMLInputElement).value,
    ).toBe('75000');
    expect(
      (screen.getByLabelText('Loan purpose') as HTMLInputElement).value,
    ).toBe('Equipment purchase');
    expect(
      (screen.getByLabelText('Business activity') as HTMLInputElement).value,
    ).toBe('Manufacturing');
    expect(
      (screen.getByLabelText('Application reference') as HTMLInputElement)
        .value,
    ).toBe('REF-9');
    expect(
      (screen.getByLabelText('Application date') as HTMLInputElement).value,
    ).toBe('2026-08-01');
  });

  it('2: a local edit overrides the persisted value; untouched fields keep showing the persisted value', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: PERSISTED }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    const amount = screen.getByLabelText(
      'Requested loan amount',
    ) as HTMLInputElement;
    expect(amount.value).toBe('75000');
    fireEvent.change(amount, { target: { value: '90000' } });
    expect(amount.value).toBe('90000');
    // Untouched field is unaffected and still shows the persisted value.
    expect(
      (screen.getByLabelText('Loan purpose') as HTMLInputElement).value,
    ).toBe('Equipment purchase');
  });

  it('3: Save sends the effective values - the local edit plus untouched persisted fields, never blanking them', async () => {
    const { calls } = stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: PERSISTED }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    // Edit only one of the five fields.
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital top-up' },
    });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(
        calls.filter((c) => c.url.includes('mudra-complete-application')).length,
      ).toBe(1);
    });
    const body = JSON.parse(
      calls.find((c) => c.url.includes('mudra-complete-application'))?.body ??
        '{}',
    );
    expect(body).toMatchObject({
      requested_loan_amount: '75000', // untouched - persisted value preserved
      loan_purpose: 'Working capital top-up', // edited value sent
      business_activity: 'Manufacturing',
      application_reference: 'REF-9',
      application_date: '2026-08-01',
    });
  });

  it('4: after a successful Save and a refreshed workItem, the fields stay populated, not blank', async () => {
    const { calls } = stubFetch();
    const { rerender } = render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: PERSISTED }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Working capital top-up' },
    });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(
        calls.filter((c) => c.url.includes('mudra-complete-application')).length,
      ).toBe(1);
    });
    // Simulate the authoritative refresh: the parent re-renders with the
    // updated workItem reflecting what was just persisted. run() has already
    // cleared local drafts (setForm({})) at this point.
    rerender(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            ...PERSISTED,
            loan_purpose: 'Working capital top-up',
          },
        }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(
      (screen.getByLabelText('Requested loan amount') as HTMLInputElement)
        .value,
    ).toBe('75000');
    expect(
      (screen.getByLabelText('Loan purpose') as HTMLInputElement).value,
    ).toBe('Working capital top-up');
  });

  it('5: Save & Close persists, and reopening with the returned persisted data displays the saved values', async () => {
    const onCloseWorkspace = vi.fn();
    stubFetch();
    const { unmount } = render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
        onCloseWorkspace={onCloseWorkspace}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '60000' },
    });
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'New equipment' },
    });
    fireEvent.click(screen.getByText('Save & Close'));
    await waitFor(() => {
      expect(onCloseWorkspace).toHaveBeenCalledTimes(1);
    });
    unmount();

    // Reopening: a fresh mount with the workItem now carrying the values
    // the backend actually persisted.
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            requested_loan_amount: '60000',
            loan_purpose: 'New equipment',
          },
        }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(
      (screen.getByLabelText('Requested loan amount') as HTMLInputElement)
        .value,
    ).toBe('60000');
    expect(
      (screen.getByLabelText('Loan purpose') as HTMLInputElement).value,
    ).toBe('New equipment');
  });

  it('6: failed persistence does not close the workspace and does not erase the current local draft', async () => {
    const onCloseWorkspace = vi.fn();
    const onError = vi.fn();
    const fn = vi.fn(async () => new Response('server error', { status: 500 }));
    vi.stubGlobal('fetch', fn);
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: { requested_loan_amount: '75000' } }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={onError}
        onCloseWorkspace={onCloseWorkspace}
      />,
    );
    fireEvent.change(screen.getByLabelText('Loan purpose'), {
      target: { value: 'Draft not yet saved' },
    });
    fireEvent.click(screen.getByText('Save & Close'));
    await waitFor(() => {
      expect(onError).toHaveBeenCalled();
    });
    expect(onCloseWorkspace).not.toHaveBeenCalled();
    // The local draft survives the failure - not cleared, not reverted.
    expect(
      (screen.getByLabelText('Loan purpose') as HTMLInputElement).value,
    ).toBe('Draft not yet saved');
    // The untouched, already-persisted field is also still shown correctly.
    expect(
      (screen.getByLabelText('Requested loan amount') as HTMLInputElement)
        .value,
    ).toBe('75000');
  });
});

describe('Mudra eligibility - Not Eligible requires a reason', () => {
  it('Mark Not Eligible confirm is disabled until a reason is entered', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: { cibil_score: '720' } }}
        processState={processState('CREDIT_ELIGIBILITY')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    const reject = screen.getByText(
      'Mark Not Eligible (reject)',
    ) as HTMLButtonElement;

    // Rejection cannot even be selected until a reason is supplied.
    expect(reject.disabled).toBe(true);
    expect(screen.queryByText('Save & Reject Case')).toBeNull();

    fireEvent.change(screen.getByLabelText('Rejection reason'), {
      target: { value: 'Low CIBIL' },
    });

    expect(reject.disabled).toBe(false);
    fireEvent.click(reject);

    const confirm = screen.getByText(
      'Save & Reject Case',
    ) as HTMLButtonElement;
    expect(confirm.disabled).toBe(false);
  });
});

describe('Mudra Bank Pending - one active form at a time', () => {
  it('shows only the raise form when there is no active task', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('BANK_PENDING')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText('Raise Pending Task')).toBeTruthy();
    expect(screen.queryByText('Complete Re-QC')).toBeNull();
    expect(screen.queryByText('Reassign Pending Task')).toBeNull();
  });

  it('shows reassign/evidence (not raise) while a task is OPEN, and Re-QC only once RECEIVED', () => {
    stubFetch();
    const { rerender } = render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            mudra_pending_task: { status: 'OPEN', reason: 'Need statement' },
          },
        }}
        processState={processState('BANK_PENDING')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText('Reassign Pending Task')).toBeTruthy();
    expect(screen.getByText('Record Received Information')).toBeTruthy();
    expect(screen.queryByText('Raise Pending Task')).toBeNull();
    expect(screen.queryByText('Complete Re-QC')).toBeNull();

    rerender(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            mudra_pending_task: {
              status: 'RECEIVED',
              reason: 'Need statement',
              evidence: 'Statement uploaded',
            },
          },
        }}
        processState={processState('BANK_PENDING')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText('Complete Re-QC')).toBeTruthy();
    expect(screen.queryByText('Reassign Pending Task')).toBeNull();
    expect(screen.queryByText('Raise Pending Task')).toBeNull();
  });
});

describe('Mudra terminal states', () => {
  it('shows the rejected panel instead of any action form', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            mudra_outcome: 'REJECTED',
            rejection_reason: 'Low CIBIL',
          },
        }}
        processState={processState('CREDIT_ELIGIBILITY')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText(/Mudra case rejected/i)).toBeTruthy();
    expect(screen.getByText(/Low CIBIL/)).toBeTruthy();
    expect(screen.queryByText('Mark Eligible')).toBeNull();
  });

  it('shows the closed panel instead of any action form', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          operational_data: {
            mudra_outcome: 'CLOSED',
            disbursed_amount: '50000',
          },
        }}
        processState={processState('CLOSED')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByText(/Mudra case closed/i)).toBeTruthy();
    expect(screen.queryByText('Record Disbursement')).toBeNull();
  });
});

describe('Mudra collapsible panel', () => {
  it('collapsing hides the body and does not call the backend; draft survives', async () => {
    const { calls } = stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', operational_data: {} }}
        processState={processState('APPLICATION')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText('Requested loan amount'), {
      target: { value: '50000' },
    });

    const toggle = screen.getByRole('button', { name: /Collapse Mudra panel/i });
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(toggle);
    expect(screen.queryByLabelText('Requested loan amount')).toBeNull();
    expect(calls.length).toBe(0);

    const expand = screen.getByRole('button', { name: /Expand Mudra panel/i });
    fireEvent.click(expand);
    const input = screen.getByLabelText(
      'Requested loan amount',
    ) as HTMLInputElement;
    expect(input.value).toBe('50000');
  });
});

describe('Mudra/UDYAM reviewer confirmation UX parity (top workflow zone)', () => {
  // WorkArea itself (which wires reviewButtons + UdyamWorkflowConfirm together
  // in the top workflow zone for both UDYAM_REGISTRATION and MUDRA_LOAN) is a
  // large, data-fetching component with no existing render-test harness in
  // this suite. These tests instead exercise UdyamWorkflowConfirm directly -
  // the exact, unmodified, shared component now wired into the Mudra branch
  // of that zone exactly as it already is for Udyam - proving the top-zone
  // select-then-confirm contract Mudra now shares with Udyam. The wiring
  // itself (same component, same props, same call site pattern) is a static
  // source fact recorded in the implementation report.

  it('A: renders nothing until an action is selected, then completes Approve & Continue in place', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const { rerender } = render(
      <UdyamWorkflowConfirm
        pendingAction={null}
        canEdit={true}
        onCommentChange={() => {}}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    // Nothing rendered until an action is selected.
    expect(screen.queryByText(/Approve/i)).toBeNull();

    rerender(
      <UdyamWorkflowConfirm
        pendingAction={{ kind: 'APPROVE', label: 'Approve & continue' }}
        canEdit={true}
        onCommentChange={() => {}}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    // Confirm and Cancel appear together, in the same place the action was
    // selected - no separate justification field for a plain approval.
    const confirmButton = screen.getByText('Save & Approve & continue');
    expect(confirmButton).toBeTruthy();
    expect(screen.getByText('Cancel')).toBeTruthy();

    fireEvent.click(confirmButton);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('B: Return for Rework shows the justification field and confirm together, confirm disabled until a reason is given', () => {
    const onCommentChange = vi.fn();
    const onConfirm = vi.fn();
    const { rerender } = render(
      <UdyamWorkflowConfirm
        pendingAction={{
          kind: 'RETURN_FOR_REWORK',
          label: 'Return for rework',
          comment: '',
        }}
        canEdit={false}
        onCommentChange={onCommentChange}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    );

    const textarea = screen.getByLabelText(/Reviewer return justification/i);
    expect(textarea).toBeTruthy();
    const confirmEmpty = screen.getByText(
      'Confirm Return for rework',
    ) as HTMLButtonElement;
    expect(confirmEmpty.disabled).toBe(true);

    fireEvent.change(textarea, {
      target: { value: 'Missing KYC document.' },
    });
    expect(onCommentChange).toHaveBeenCalledWith('Missing KYC document.');

    rerender(
      <UdyamWorkflowConfirm
        pendingAction={{
          kind: 'RETURN_FOR_REWORK',
          label: 'Return for rework',
          comment: 'Missing KYC document.',
        }}
        canEdit={false}
        onCommentChange={onCommentChange}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    );
    const confirmFilled = screen.getByText(
      'Confirm Return for rework',
    ) as HTMLButtonElement;
    expect(confirmFilled.disabled).toBe(false);
    fireEvent.click(confirmFilled);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe('Mudra post-review workspace reconciliation (browser defect regression)', () => {
  // No production frontend code changed for this correction - the fix lives
  // entirely in the backend (WorkItemViewSet.health()'s Mudra next_action
  // override, and WorkItemSerializer.get_effective_status's widened service
  // gate). This suite proves, at the same component-seam granularity as the
  // rest of this file, that the frontend surfaces those corrected backend
  // values without requiring any change of its own:
  //   - the Mudra stage action panel (MudraExternalActions) remains the
  //     authoritative, visible, usable surface once processState reflects
  //     the post-review CREDIT_ELIGIBILITY position - exactly the state a
  //     real browser reaches after "Approve & Continue";
  //   - it never re-exposes an Application/KYC or Submit-for-Review-style
  //     control at that stage.
  //
  // The full assembled workspace (header effective_status text, the Work
  // Health widget consuming next_action.label, and reviewButtons'
  // internalReviewCompleted suppression together in one render) is NOT
  // executed here: WorkArea has no existing render-test harness in this
  // suite (it requires mocking five separate list endpoints plus drawer-open
  // state), and building one for this correction would be exactly the kind
  // of first-of-its-kind giant mock the governance for this task says to
  // avoid. That remaining integration-test gap is stated explicitly in the
  // implementation report rather than pretended away. The three pieces are
  // instead verified individually: this file covers the Mudra action panel;
  // the backend suite covers effective_status and Work Health directly
  // against the real endpoints; the reviewButtons suppression logic
  // (internalReviewCompleted) and the footer-suppression logic
  // (mudraOwnsPrimaryAction) are unchanged source, confirmed byte-identical
  // to the CURRENT_SOURCE baseline in this same correction.

  it('the Mudra Credit & Eligibility action surface is visible and usable immediately after a real review-approval-shaped state', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          status: 'IN_PROGRESS',
          operational_data: {},
        }}
        processState={processState('CREDIT_ELIGIBILITY')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    // The CIBIL/Credit & Eligibility action surface is present and usable -
    // not a blank panel, not an Application/KYC form, not a terminal panel.
    expect(screen.getByLabelText('CIBIL score')).toBeTruthy();
    expect(screen.getByText('Record CIBIL')).toBeTruthy();
    expect(screen.queryByLabelText('Requested loan amount')).toBeNull();
    expect(screen.queryByText('Save')).toBeNull();
    expect(screen.queryByText('Save & Close')).toBeNull();
    expect(screen.queryByText(/submitted for internal review/i)).toBeNull();
  });

  it('does not present a rejected/closed terminal panel for an ordinary post-review IN_PROGRESS case', () => {
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{
          id: 'w1',
          status: 'IN_PROGRESS',
          operational_data: {},
        }}
        processState={processState('CREDIT_ELIGIBILITY')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.queryByText(/Mudra case rejected/i)).toBeNull();
    expect(screen.queryByText(/Mudra case closed/i)).toBeNull();
  });
});

describe('Assembled workspace regression: stale SUBMIT_FOR_REVIEW cleared by the real production reconciliation function', () => {
  // Exercises reconcileStalePendingAction directly - the exact function
  // refreshOpenWorkWorkspace calls in production to decide whether a
  // selected pendingAction survives an authoritative refresh. This is NOT a
  // re-simulation of the decision: the function under test is the same
  // exported production function the real workspace calls, with the same
  // inputs it would actually receive and the same return value it would
  // actually apply via setPendingAction.

  const pendingSubmitForReview: PendingWorkAction = {
    kind: 'SUBMIT_FOR_REVIEW',
    label: 'Submit for review',
  };

  it('a stale SUBMIT_FOR_REVIEW selection is invalidated by the real reconciliation function after authoritative approval, and the correct post-approval surface renders', () => {
    // Step 1: owner has selected Submit for Review at APPLICATION - the
    // exact pendingAction state a real click on the (separately tested)
    // reviewButtons selector produces. UdyamWorkflowConfirm renders its
    // real confirm surface for it, exactly as production would.
    const onConfirm = vi.fn();
    const { rerender, unmount } = render(
      <UdyamWorkflowConfirm
        pendingAction={pendingSubmitForReview}
        canEdit={true}
        onCommentChange={() => {}}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByText('Save & Submit for review')).toBeTruthy();

    // Step 2: authoritative approval refresh arrives - WorkItem.status
    // remains IN_PROGRESS, WorkProcessState has genuinely advanced to
    // CREDIT_ELIGIBILITY, Work Health recommends the Credit & Eligibility
    // continuation. This is the exact shape reconcileOpenWorkspace's
    // callbacks capture in production. Call the REAL exported production
    // function with it - not a re-derivation of what it "should" do.
    const reconciled = reconcileStalePendingAction({
      pendingAction: pendingSubmitForReview,
      freshRow: { id: 'w1', status: 'IN_PROGRESS', service_id: 'svc-1' },
      freshProcessState: processState('CREDIT_ELIGIBILITY'),
      freshHealthSnapshot: {
        next_action: {
          code: 'CONTINUE_MUDRA_CREDIT_ELIGIBILITY',
          label: 'Complete Credit & Eligibility',
        },
      } as unknown as WorkHealthSnapshot,
      freshServiceCode: 'MUDRA_LOAN',
    });

    // The real production function must invalidate the stale selection.
    expect(reconciled).toBeNull();

    // Step 3: apply the function's actual return value (exactly what
    // refreshOpenWorkWorkspace does via setPendingAction) and prove the
    // stale confirm surface is gone.
    rerender(
      <UdyamWorkflowConfirm
        pendingAction={reconciled}
        canEdit={true}
        onCommentChange={() => {}}
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    );
    expect(screen.queryByText('Save & Submit for review')).toBeNull();
    expect(screen.queryByText(/Submit for review selected/i)).toBeNull();
    expect(onConfirm).not.toHaveBeenCalled();
    unmount();

    // Step 4: the real Credit & Eligibility action surface renders instead -
    // the actual next thing the user should see and use, not merely the
    // absence of the stale one.
    stubFetch();
    render(
      <MudraExternalActions
        workItem={{ id: 'w1', status: 'IN_PROGRESS', operational_data: {} }}
        processState={processState('CREDIT_ELIGIBILITY')}
        onChanged={async () => {}}
        onError={() => {}}
      />,
    );
    expect(screen.getByLabelText('CIBIL score')).toBeTruthy();
    expect(screen.getByText('Record CIBIL')).toBeTruthy();
  });

  it('an unrelated pendingAction (Return for Rework) is returned unchanged by the real reconciliation function', () => {
    const pendingReturn: PendingWorkAction = {
      kind: 'RETURN_FOR_REWORK',
      label: 'Return for rework',
      comment: 'Missing KYC document.',
    };

    const reconciled = reconcileStalePendingAction({
      pendingAction: pendingReturn,
      freshRow: { id: 'w1', status: 'IN_PROGRESS', service_id: 'svc-1' },
      freshProcessState: processState('CREDIT_ELIGIBILITY'),
      freshHealthSnapshot: null,
      freshServiceCode: 'MUDRA_LOAN',
    });

    // The real function's own kind-guard leaves any non-SUBMIT_FOR_REVIEW
    // selection completely untouched, regardless of the fresh state.
    expect(reconciled).toBe(pendingReturn);

    render(
      <UdyamWorkflowConfirm
        pendingAction={reconciled}
        canEdit={false}
        onCommentChange={() => {}}
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );
    expect(screen.getByLabelText(/Reviewer return justification/i)).toBeTruthy();
  });

  it('process-step failure does not incorrectly clear a valid APPLICATION selection, and the pending selection is invalidated once recovery succeeds', () => {
    // INITIAL: the process-step projection failed (reconcileOpenWorkspace's
    // non-fatal projection catch - freshProcessState stays null, exactly as
    // it does in production when that fetch rejects). The WorkItem itself
    // still refreshed successfully (freshRow is present).
    const duringFailure = reconcileStalePendingAction({
      pendingAction: pendingSubmitForReview,
      freshRow: { id: 'w1', status: 'IN_PROGRESS', service_id: 'svc-1' },
      freshProcessState: null,
      freshHealthSnapshot: null,
      freshServiceCode: 'MUDRA_LOAN',
    });

    // A failed/unavailable process-step read must not be treated as proof
    // the case has advanced - the real function must not incorrectly clear
    // a genuinely still-valid APPLICATION-stage selection.
    expect(duringFailure).toBe(pendingSubmitForReview);

    // THEN: a later authoritative refresh succeeds, and the process-step
    // projection now genuinely reports CREDIT_ELIGIBILITY (recovery).
    const afterRecovery = reconcileStalePendingAction({
      pendingAction: duringFailure,
      freshRow: { id: 'w1', status: 'IN_PROGRESS', service_id: 'svc-1' },
      freshProcessState: processState('CREDIT_ELIGIBILITY'),
      freshHealthSnapshot: null,
      freshServiceCode: 'MUDRA_LOAN',
    });

    // The still-stale selection does not survive the successful recovery.
    expect(afterRecovery).toBeNull();
  });

  it('a genuinely valid APPLICATION selection is preserved when process state is unavailable', () => {
    // Confirms the same fail-safe path does not break ordinary APPLICATION
    // behavior: with no process-step data at all (e.g. a case that has
    // never had one recorded, or a load that has not resolved yet), a
    // SUBMIT_FOR_REVIEW selection remains valid and is not cleared.
    const reconciled = reconcileStalePendingAction({
      pendingAction: pendingSubmitForReview,
      freshRow: { id: 'w1', status: 'IN_PROGRESS', service_id: 'svc-1' },
      freshProcessState: null,
      freshHealthSnapshot: null,
      freshServiceCode: 'MUDRA_LOAN',
    });
    expect(reconciled).toBe(pendingSubmitForReview);
  });
});
