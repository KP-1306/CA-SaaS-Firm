import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';

import {
  QuickCreateMenu,
} from '../src/features/console/quick-create';

import {
  WorkArea,
} from '../src/features/console/work';

import {
  EmployeeOpsArea,
} from '../src/features/console/employee_ops';


function jsonResponse(body: unknown): Response {
  return new Response(
    JSON.stringify(body),
    {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
      },
    },
  );
}


afterEach(() => {
  vi.restoreAllMocks();
});


describe('Phase 5.1A Universal Quick Create', () => {
  it('dispatches only launcher actions and respects assignment visibility', () => {
    const select = vi.fn();

    const { rerender } = render(
      <QuickCreateMenu
        canAssign={false}
        onSelect={select}
      />,
    );

    fireEvent.click(
      screen.getByRole(
        'button',
        { name: '+ Create' },
      ),
    );

    expect(
      screen.getByRole(
        'menuitem',
        { name: /New Client/ },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'menuitem',
        { name: /New Work Item/ },
      ),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole(
        'menuitem',
        { name: /Assign Existing Work/ },
      ),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole(
        'menuitem',
        { name: /New Work Item/ },
      ),
    );

    expect(select).toHaveBeenCalledWith('NEW_WORK');

    rerender(
      <QuickCreateMenu
        canAssign
        onSelect={select}
      />,
    );

    fireEvent.click(
      screen.getByRole(
        'button',
        { name: '+ Create' },
      ),
    );

    expect(
      screen.getByRole(
        'menuitem',
        { name: /Assign Existing Work/ },
      ),
    ).toBeInTheDocument();
  });


  it('opens the existing New Work Item workspace', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse([])),
    );

    render(
      <WorkArea
        initialQuickAction="create"
      />,
    );

    expect(
      await screen.findByRole(
        'heading',
        { name: 'New Work Item' },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'button',
        { name: 'Save' },
      ),
    ).toBeInTheDocument();
  });


  it('uses existing Work Documents after selecting Work for upload', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (
          url.includes('/work-items/')
          && !url.includes('/health/')
          && !url.includes('/work-items/doc-work/')
        ) {
          return jsonResponse([
            {
              id: 'doc-work',
              title: 'Document Upload Work',
              client_id: 'client-1',
              status: 'IN_PROGRESS',
              can_edit: true,
              can_upload_internal: true,
            },
          ]);
        }

        if (
          url.includes('/work-items/doc-work/health/')
        ) {
          return jsonResponse({});
        }

        return jsonResponse([]);
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    render(
      <WorkArea
        initialQuickAction="documents"
      />,
    );

    expect(
      await screen.findByText(
        'Select a Work Item to upload a client document.',
      ),
    ).toBeInTheDocument();

    fireEvent.click(
      await screen.findByText(
        'Document Upload Work',
      ),
    );

    expect(
      await screen.findByRole(
        'heading',
        { name: 'Document Upload Work' },
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes(
              '/document-requests/',
            ),
        ),
      ).toBe(true);
    });
  });


  it('opens the existing Assignment section instead of duplicating assignment', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse([])),
    );

    render(
      <EmployeeOpsArea
        initialSection="assignment"
      />,
    );

    expect(
      await screen.findByText('Work item'),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'button',
        { name: 'Get recommendations' },
      ),
    ).toBeInTheDocument();

    expect(
      screen.getByRole(
        'button',
        { name: 'Assignment' },
      ),
    ).toHaveClass('cx-btn');
  });
});
