import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  ConsultantAdministration,
  IdentityGate,
  LoginScreen,
  isProviderAdmin,
} from '../src/features/console/identity';

describe('Phase 3A.3 identity UI', () => {
  it('recognises only provider administrator roles', () => {
    expect(isProviderAdmin({
      account: {},
      membership: { role: 'PLATFORM_ADMIN' },
    })).toBe(true);
    expect(isProviderAdmin({
      account: {},
      membership: { role: 'IMPLEMENTATION_CONSULTANT' },
    })).toBe(false);
  });

  it('submits consultant credentials through the secure login endpoint', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ csrf_token: 'token' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ account: {}, membership: {} }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ));

    vi.stubGlobal('fetch', fetchMock);
    const authenticated = vi.fn(async () => undefined);

    render(<LoginScreen onAuthenticated={authenticated} />);
    fireEvent.change(screen.getByLabelText('Work email'), {
      target: { value: 'admin@vridhi.example' },
    });
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'Password-123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(authenticated).toHaveBeenCalled());
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/auth/login/');
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      credentials: 'include',
    });
  });

  it('shows login when no authenticated session exists', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: 'Invalid or expired session.' }),
          { status: 403, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    render(<IdentityGate><div>Protected console</div></IdentityGate>);
    expect(
      await screen.findByRole('heading', { name: 'Consultant sign in' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Protected console')).not.toBeInTheDocument();
  });

  it('renders consultant administration records', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/identity/consultants/')) {
          return new Response(JSON.stringify([{
            id: 'user-1',
            display_name: 'Consultant One',
            email: 'one@vridhi.example',
            account_status: 'ACTIVE',
            active_session_count: 1,
            membership: { role: 'SUPPORT_CONSULTANT' },
            employee: null,
          }]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }),
    );

    render(<ConsultantAdministration />);
    expect(await screen.findByText('Consultant One')).toBeInTheDocument();
    expect(screen.getByText('one@vridhi.example')).toBeInTheDocument();
  });
});
