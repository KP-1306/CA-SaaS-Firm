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
  GlobalSearch,
} from '../src/features/console/GlobalSearch';


function ok(body: unknown): Response {
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
  localStorage.clear();
});


describe('Phase 5.5 Global Search', () => {
  it('searches document requests and uploaded files', async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/clients/')) return ok([]);
        if (url.includes('/employees/')) return ok([]);
        if (url.includes('/work-items/')) return ok([]);
        if (url.includes('/services/')) return ok([]);

        if (url.includes('/document-requests/')) {
          return ok([
            {
              id: 'request-1',
              name: 'Northstar Bank Statement',
              work_item_id: 'work-11',
              client_name: 'Northstar Manufacturing',
              status: 'REQUESTED',
            },
          ]);
        }

        if (url.includes('/document-attachments/')) {
          return ok([
            {
              id: 'attachment-1',
              original_name: 'northstar-bank-statement.pdf',
              work_item_id: 'work-11',
              content_type: 'application/pdf',
              source: 'CLIENT',
            },
          ]);
        }

        return ok([]);
      },
    );

    vi.stubGlobal('fetch', fetchMock);

    const navigate = vi.fn();

    render(
      <GlobalSearch onNavigate={navigate} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText(
        'Search clients, employees, work, services or documents',
      ),
      {
        target: {
          value: 'Northstar',
        },
      },
    );

    expect(
      await screen.findByText('Documents'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('Northstar Bank Statement'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('northstar-bank-statement.pdf'),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([input]) =>
            String(input).includes('/document-requests/?'),
        ),
      ).toBe(true);

      expect(
        fetchMock.mock.calls.some(
          ([input]) =>
            String(input).includes('/document-attachments/?'),
        ),
      ).toBe(true);
    });
  });


  it('passes work identity for direct document opening', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.includes('/clients/')) return ok([]);
        if (url.includes('/employees/')) return ok([]);
        if (url.includes('/work-items/')) return ok([]);
        if (url.includes('/services/')) return ok([]);
        if (url.includes('/document-requests/')) return ok([]);

        if (url.includes('/document-attachments/')) {
          return ok([
            {
              id: 'attachment-77',
              original_name: 'client-pan.pdf',
              work_item_id: 'work-77',
              content_type: 'application/pdf',
            },
          ]);
        }

        return ok([]);
      }),
    );

    const navigate = vi.fn();

    render(
      <GlobalSearch onNavigate={navigate} />,
    );

    fireEvent.change(
      screen.getByPlaceholderText(
        'Search clients, employees, work, services or documents',
      ),
      {
        target: {
          value: 'client-pan',
        },
      },
    );

    fireEvent.click(
      await screen.findByText('client-pan.pdf'),
    );

    expect(navigate).toHaveBeenCalledWith(
      'documents',
      'attachment-77',
      'work-77',
    );
  });
});
