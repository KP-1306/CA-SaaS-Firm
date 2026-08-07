import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { EmployeeDashboard, ExecutiveDashboard } from '../src/features/console/dashboards';
import { ExpertisePanel } from '../src/features/console/expertise';
import { AuditViewer } from '../src/features/console/audit';

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Employee dashboard (backend aggregation)', () => {
  it('renders metrics from the aggregation endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/dashboard/employee')) {
        return jsonResponse({
          my_work: { assigned_open: 5, due_today: 1, overdue: 2, waiting_for_client: 0, ready_for_review: 1, rework_required: 0, recently_completed: 3 },
          document_centre: {},
          workload: { open: 5, completed_period: 3, status_distribution: {}, avg_completion_days: null },
        });
      }
      return jsonResponse({});
    }));
    render(<EmployeeDashboard />);
    await waitFor(() => expect(screen.getByText('Assigned (open)')).toBeInTheDocument());
    expect(screen.getByText('5')).toBeInTheDocument();
  });
});

describe('Executive dashboard (backend aggregation)', () => {
  it('renders overview from the aggregation endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/dashboard/executive')) {
        return jsonResponse({
          overview: { active_clients: 4, active_work: 9, due_today: 1, overdue: 2, waiting_for_client: 1, ready_for_review: 1, rework_required: 0, recently_completed: 3 },
          operations: { by_status: {}, ageing: {}, completion_trend: [] },
          employee_workload: { rows: [], unassigned: 0, pending_reviews: 0 },
          client_health: { rows: [] },
          heatmap_priority_status: {},
          action_centre: {},
          work_health: {
            healthy: 5,
            attention_required: 2,
            high_risk: 1,
            due_soon: 2,
            overdue: 1,
            waiting_on_client: 2,
            waiting_on_reviewer: 1,
            longest_waiting_days: 8,
            immediate_actions: [
              {
                id: 'w1',
                title: 'GST Return',
                health: 'RED',
                risk: 'HIGH',
                current_controller: 'CLIENT',
                waiting_days: 8,
                next_action: 'Await client documents',
              },
            ],
          },
        });
      }
      return jsonResponse({});
    }));
    render(<ExecutiveDashboard />);
    await waitFor(() => expect(screen.getByText('Active work')).toBeInTheDocument());
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(
      screen.getByText('Firm Work Health'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Attention required'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('High risk'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Await client documents'),
    ).toBeInTheDocument();
  });
});

describe('Expertise panel', () => {
  it('lists existing normalized expertise records', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/employee-expertise')) {
        return jsonResponse([
          { id: 'e1', employee_id: 'emp1', category: 'GST', category_label: 'GST', proficiency: 'ADVANCED' },
        ]);
      }
      return jsonResponse([]);
    }));
    render(<ExpertisePanel employeeId="emp1" />);
    await waitFor(() => expect(screen.getByText(/GST/i)).toBeInTheDocument());
  });
});

describe('Audit viewer', () => {
  it('renders audit rows from the append-only endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/audit-events')) {
        return jsonResponse([
          { id: 'a1', action: 'STATUS_CHANGE', action_label: 'Status changed', entity_type: 'WorkItem', entity_id: 'w1', summary: 'moved', created_at: '2026-01-01T00:00:00Z' },
        ]);
      }
      return jsonResponse([]);
    }));
    render(<AuditViewer />);
    await waitFor(() => expect(screen.getByText('Status changed')).toBeInTheDocument());
  });
});
