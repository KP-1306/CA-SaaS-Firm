# CA Firm Operations SaaS

Multi-tenant operations platform for Chartered Accountant firms: the system of
record for what work a firm owes its clients, who is doing it, what stage it is
at, what is holding it up, who reviewed it, and what was delivered.

> **Repository state: bootstrap scaffolding only.**
> This repository currently contains the engineering foundation produced by
> **EWP-000.1A**. There is no domain logic, no database schema, no
> authentication and no business functionality yet. See
> [Scope boundaries](#scope-boundaries).

---

## Toolchain

| Tool | Required version | Frozen by |
| --- | --- | --- |
| Python | 3.12.x | TAD §20.1 |
| Django | 5.2 LTS | TAD §20.1 |
| Django REST Framework | 3.15.x | TAD §20.1 |
| Node.js | 20.x or 22.x LTS | TAD §20.1 |
| TypeScript | 5.x | TAD §20.1 |
| React | 18.x | TAD §20.1 |
| Vite | 5.x | TAD §20.1 |
| PostgreSQL | 16 (later EWP) | TAD §5 — architecturally mandated |
| Git | 2.40+ | — |

These are frozen. Substituting any of them requires a Change Request against
the frozen baseline, not a pull request.

---

## Setup

Requires Python 3.12, Node 20+ and network access to package registries.

### Backend

```bash
cd backend
python3.12 -m venv .venv

# Linux / macOS
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements/development.txt
```

### Frontend

```bash
cd frontend
npm ci        # use `npm install` only when intentionally changing dependencies
```

### Environment

```bash
cp .env.example .env
```

Then edit `.env` and supply local values. `.env` is git-ignored and must never
be committed. No database connection is required to run the checks in this
repository at its current state.

---

## Commands

Run from the repository root.

| Command | Purpose |
| --- | --- |
| `make help` | List available targets |
| `make install` | Install backend and frontend dependencies |
| `make check` | Run every check below in sequence |
| `make backend-format` | Check Python formatting (ruff format --check) |
| `make backend-lint` | Lint Python (ruff check) |
| `make backend-types` | Type-check Python (mypy) |
| `make backend-django-check` | Django system check |
| `make backend-test` | Backend tests (pytest) |
| `make frontend-format` | Check frontend formatting (prettier) |
| `make frontend-lint` | Lint frontend (eslint) |
| `make frontend-types` | Type-check frontend (tsc --noEmit) |
| `make frontend-test` | Frontend tests (vitest) |
| `make frontend-build` | Production build (vite build) |
| `make verify-structure` | Verify the tree matches the frozen structure |
| `make secret-scan` | Scan tracked files for secret-like material |

Windows users without `make` can read the target bodies in the `Makefile` and
run the underlying commands directly.

---

## Repository layout

```
cafirm/
├── backend/                    Django 5.2 modular monolith
│   ├── config/                 Project configuration
│   │   ├── settings/           base · development · test · production
│   │   ├── urls.py             Root URL configuration
│   │   ├── urls_internal.py    Internal plane   (/api/v1/)
│   │   ├── urls_portal.py      Portal plane     (/portal/api/v1/)
│   │   └── urls_platform.py    Platform plane   (/platform/api/v1/)
│   ├── core/                   Shared infrastructure — NOT a bounded context
│   │   ├── db/  auth/  audit/  exceptions/  logging/
│   │   ├── pagination/  terminology/  outbox/
│   │   └── health/             Bootstrap health endpoint
│   ├── contexts/               15 bounded contexts (AR §4) — one package each
│   └── tests/                  unit · integration · conformance
├── frontend/                   React 18 + TypeScript 5 + Vite
│   └── src/
│       ├── apps/internal/      Internal plane SPA entry
│       ├── apps/portal/        Portal plane SPA entry
│       ├── shared/             Neutral infrastructure shared by both planes
│       ├── features/           Domain features (empty — later EWPs)
│       └── api/                API clients (empty — later EWPs)
├── infrastructure/             docker · terraform · nginx (skeleton only)
├── docs/                       architecture · api · runbooks · adr
├── scripts/                    Verification and maintenance scripts
└── .github/workflows/          CI (skeleton only — later EWP)
```

### The three planes

The architecture separates three application planes with **no shared handlers**
(AR §2.4, ADR-003, ADR-004). This is a structural boundary, not a runtime check:

| Plane | Backend prefix | Frontend entry | Principal |
| --- | --- | --- | --- |
| Internal | `/api/v1/` | `src/apps/internal` | Firm staff |
| Portal | `/portal/api/v1/` | `src/apps/portal` | Client organisations |
| Platform | `/platform/api/v1/` | — | Vendor operators |

A portal session must never reach an internal handler. The separation begins in
the URL configuration and the frontend entry points.

### The 15 bounded contexts

`platform` · `identity` · `organisation` · `configuration` · `clients` ·
`workflow` · `work` · `generation` · `quality` · `documents` ·
`collaboration` · `audit` · `notifications` · `insight` · `portal`

Contexts communicate through module contracts, never by importing another
context's models or querying its tables (AR §6.5, EIB §4.2). This rule is
enforced by a boundary check owned by a later work package.

---

## Scope boundaries

**Implemented by EWP-000.1A:** repository structure, Django project skeleton,
settings split, three URL planes, empty context packages, frontend dual-entry
skeleton, quality tooling configuration, documentation.

**Deliberately not implemented yet.** Their absence is expected:

| Area | Owning stage |
| --- | --- |
| Database schema, models, migrations | Later EWP |
| Row-level security and tenant isolation | Later EWP |
| Authentication, sessions, MFA, authorisation | Later EWP |
| Audit event capture, transactional outbox | Later EWP |
| Redis, Celery, S3, SES, ClamAV integrations | Later EWP |
| Docker Compose, Terraform, CI workflows | Later EWP |
| All domain behaviour and business screens | Later EWPs |

Empty packages exist where the frozen structure requires them. They contain no
placeholder business logic.

---

## Governance

The frozen documents are the source of truth. This repository implements them;
it does not reinterpret them.

| Document | Role |
| --- | --- |
| BL Rev 3 — Business Requirements | What the product must do |
| AR v1.0 — Product Architecture | Contexts, planes, boundaries, ADRs |
| TD v1.0 — Technical Design | Entities, contracts, invariants, error codes |
| ERR v1.0 — Engineering Readiness Review | Gap analysis and readiness gates |
| TAD v1.0 — Technology Architecture Decision | The frozen stack |
| EIB v1.0 — Engineering Implementation Blueprint | The engineering constitution |

An index is maintained at [`docs/architecture/README.md`](docs/architecture/README.md).

**If code and a frozen document disagree, the document wins.** Record the
conflict with exact section references and raise it — do not resolve it
silently in code.

See [CONTRIBUTING.md](CONTRIBUTING.md) for review requirements and
[SECURITY.md](SECURITY.md) for security rules.
