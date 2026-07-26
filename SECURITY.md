# Security Policy

## Reporting a vulnerability

Do **not** open a public issue for a security vulnerability.

Report privately to the security contact defined by the Engineering Lead.
A private reporting channel must be configured before the repository accepts
external contributions — this is owned by a later work package and is not yet
in place.

Expected acknowledgement: 2 working days. Expected triage: 5 working days.

## Data this platform holds

This product stores statutory identifiers, tax working papers and financial
records for Chartered Accountant firms and their clients. A confidentiality
failure is a regulatory event for the firm, not only a software defect.
Security defects are therefore triaged above feature work by default.

## Non-negotiable security rules

These originate in the frozen documents and may not be relaxed by any pull
request. A change that weakens one of them is a Change Request against the
frozen baseline, not a code review comment.

1. **No secrets in the repository.** No keys, passwords, tokens, connection
   strings or cloud credentials. `.env.example` carries variable names and
   descriptive placeholders only.
2. **Production fails safely.** Production settings raise on startup when a
   mandatory secret is absent rather than falling back to an insecure default.
3. **Debug is never enabled in production.**
4. **The Django admin is never routed in production.** It bypasses the tenant
   model and the permission layer.
5. **No wildcard CORS.** Origins are enumerated explicitly.
6. **CSRF protection is never disabled.**
7. **TLS-related production settings are never relaxed to simplify startup.**
8. **Secrets are never printed** to logs, validation output or error responses.
9. **Direct dependencies are pinned** for reproducible installation.

## Boundaries owned by later work packages

EWP-000.1A establishes repository scaffolding only. The following controls are
specified in the frozen documents but are **not implemented yet**, and their
absence in this repository is expected rather than a defect:

| Control | Frozen source | Status |
| --- | --- | --- |
| Tenant isolation / row-level security | AR §7.5, TD §2.2 | Not implemented — later EWP |
| Authentication and session management | AR ADR-003, TD §7.1 | Not implemented — later EWP |
| Authorisation (five-layer model) | TD §7.4 | Not implemented — later EWP |
| Audit event capture | AR ADR-008, TD §3.12 | Not implemented — later EWP |
| Document access control | TD §11.5 | Not implemented — later EWP |
| Secrets Manager integration | EIB §4.13 | Not implemented — later EWP |

Do not assume any of the above is active in this repository at its current state.

## Dependency policy

- Direct dependencies are pinned to exact versions.
- A dependency is added only with a stated purpose and a frozen-document
  justification (EWP §14).
- No install scripts fetched from unverified sources.
- No telemetry that transmits project information externally.
