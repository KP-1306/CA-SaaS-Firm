import {
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  IdentityAccessAdministration,
  RoleAdministration,
} from '../src/features/console/authorization';


const role = {
  id: 1,
  code: 'CONSULTANT',
  name: 'Consultant',
  description: 'Standard consultant access.',
  is_system: true,
  is_active: true,
  access: [
    {
      id: 1,
      module: 'Client Management',
      code: 'clients.view',
      name: 'View Clients',
      is_active: true,
    },
  ],
};

const access = [
  {
    id: 1,
    module: 'Client Management',
    code: 'clients.view',
    name: 'View Clients',
    is_active: true,
  },
  {
    id: 2,
    module: 'Reports',
    code: 'reports.export',
    name: 'Export Reports',
    is_active: true,
  },
];

const consultant = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  display_name: 'Consultant One',
  email: 'consultant.one@vridhi.example',
};


function response(value: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => value,
    text: async () => JSON.stringify(value),
  } as Response;
}


describe('Phase 3B.3 authorization UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);

        if (url.includes('/authorization/roles/1/clone/')) {
          return response({
            ...role,
            id: 2,
            code: 'CUSTOM_CONSULTANT',
            name: 'Custom Consultant',
            is_system: false,
          }, 201);
        }

        if (
          url.includes('/authorization/roles/1/') &&
          init?.method === 'PATCH'
        ) {
          return response({
            ...role,
            name: 'Updated Consultant',
            is_system: false,
          });
        }

        if (
          url.endsWith('/authorization/roles/') &&
          init?.method === 'POST'
        ) {
          return response({
            id: 3,
            code: 'GST_MANAGER',
            name: 'GST Manager',
            is_system: false,
            is_active: true,
            access: [],
          }, 201);
        }

        if (url.includes('/authorization/users/')) {
          if (init?.method === 'PUT') {
            return response({
              user_account_id: consultant.id,
              role: {
                id: role.id,
                code: role.code,
                name: role.name,
              },
              additional_access_codes: ['reports.export'],
              department_ids: [],
              team_ids: [],
              service_ids: [],
              is_active: true,
              effective_access_codes: [
                'clients.view',
                'reports.export',
              ],
            });
          }

          return response({
            user_account_id: consultant.id,
            role: {
              id: role.id,
              code: role.code,
              name: role.name,
            },
            additional_access_codes: [],
            department_ids: [],
            team_ids: [],
            service_ids: [],
            is_active: true,
            effective_access_codes: ['clients.view'],
          });
        }

        if (url.includes('/authorization/roles/')) {
          return response([role]);
        }

        if (url.includes('/authorization/access/')) {
          return response(access);
        }

        if (url.includes('/identity/consultants/')) {
          return response([consultant]);
        }

        if (
          url.includes('/departments/') ||
          url.includes('/teams/') ||
          url.includes('/services/')
        ) {
          return response([]);
        }

        return response([]);
      }),
    );
  });

  it('keeps consultants and roles inside one Identity and Access area', async () => {
    render(<IdentityAccessAdministration />);

    expect(
      screen.getByRole('button', { name: 'Consultants' }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: 'Roles & Access' }),
    );

    expect(
      await screen.findByRole('heading', { name: 'Roles' }),
    ).toBeInTheDocument();
  });

  it('shows system roles and grouped access capabilities', async () => {
    render(<RoleAdministration />);

    expect(
      await screen.findByText('Consultant'),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: /Consultant/ }),
    );

    expect(
      await screen.findByText('Client Management'),
    ).toBeInTheDocument();

    expect(
      screen.getByText('View Clients'),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'Standard roles are protected. Clone this role to customise it.',
      ),
    ).toBeInTheDocument();
  });

  it('loads and saves consultant effective access', async () => {
    render(<RoleAdministration />);

    const selector = await screen.findByLabelText('Select consultant');

    fireEvent.change(selector, {
      target: { value: consultant.id },
    });

    await screen.findByText('Effective access preview');

    fireEvent.click(
      screen.getByRole('button', { name: 'Save employee access' }),
    );

    await waitFor(() => {
      expect(
        screen.getByText('Employee access saved.'),
      ).toBeInTheDocument();
    });

    const preview = screen
      .getByText('Effective access preview')
      .closest('.cx-effective-access');

    expect(preview).not.toBeNull();
    expect(preview).toHaveTextContent('reports.export');
  });
});
