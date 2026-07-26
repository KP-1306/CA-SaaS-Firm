# Contributing

This repository implements a frozen architecture. The most important thing a
contributor can do is **implement what is specified, and raise what is not**.

## The governing rule

If your change requires reinterpreting a frozen document, it is not a code
change — it is a Change Request. Stop, record the exact conflict with document
and section references, and raise it. Do not resolve the ambiguity in code.

Frozen documents: BL Rev 3, AR v1.0, TD v1.0, ERR v1.0, TAD v1.0, EIB v1.0.

## Branching

| Branch | Purpose |
| --- | --- |
| `main` | Production. Tagged releases only. Protected. |
| `develop` | Integration. All feature branches merge here. |
| `feature/*` | Feature work, branched from `develop`. |
| `hotfix/*` | Production fixes. Merges to `main` **and** `develop`. |

## Commit messages

```
<type>(<context>): <short description>

<body if needed>

REF: <frozen document section>
```

**Types:** `feat` `fix` `test` `refactor` `docs` `chore` `security`

**Context:** the bounded context or `core` — `work` `identity` `workflow`
`clients` `generation` `quality` `documents` `notifications` `insight`
`portal` `platform` `organisation` `configuration` `collaboration` `audit`
`core`

Example:

```
feat(work): add AssignmentTransition service with guard evaluation

REF: TD §8.4
```

## Pull requests

Every pull request must state which frozen section it implements. A PR that
cannot cite one is probably inventing behaviour.

### Author checklist

- [ ] Cites the frozen document section being implemented
- [ ] Adds tests for new behaviour, including at least one failure case
- [ ] Adds a violation test for every domain invariant the change touches
- [ ] No new dependency without a stated purpose and justification
- [ ] No secrets, credentials or real connection strings
- [ ] All local checks pass (`make check`)

### Reviewer checklist

Reviewing is a required engineering activity, not a formality.

- [ ] Does this bypass a domain invariant?
- [ ] Does every new application service take `ctx: AuthorisationContext` first?
- [ ] Does any cross-context interaction reach into another context's models
      or tables instead of using a module contract?
- [ ] Does any portal view import an internal serialiser?
- [ ] Is audit emitted inside the same transaction as the business change?
- [ ] Are new permissions drawn from the frozen catalogue rather than invented?
- [ ] Does any log statement interpolate a sensitive object directly?
- [ ] For bulk or background paths: do they call the same service function as
      the interactive path?
- [ ] Is the Django admin registered anywhere? It must not be.

Security-relevant changes require a second reviewer. Paths under
`core/auth/`, `core/db/`, `core/audit/`, `contexts/identity/`,
`contexts/portal/` and `config/settings/` are security-relevant by default.

## Working with AI coding assistants

AI assistance is permitted and encouraged for generating code from the
specification. It is not permitted to make architecture decisions.

**AI may:** generate entity skeletons, serialisers, views, tests and migrations
from a cited specification section.

**AI must not, without explicit human review against the specification:**

- touch `core/auth/`, `core/db/`, `core/audit/` or any portal serialiser
- implement domain invariant logic
- generate a state-changing service without audit emission
- generate a migration for a tenant-owned table without tenant scoping
- decide where something belongs in the module structure
- introduce an architectural pattern not present in the frozen documents

Every AI-generated change carries the same review checklist as human-written
code. There is no "trivial code" exemption.

If an assistant proposes something better than what is specified, that is a
Change Request — raise it. Do not merge it silently.

## Local verification

```bash
make check
```

Run this before opening a pull request. It executes formatting, linting, type
checking, tests and the structural conformance check for both backend and
frontend.

## Dependencies

Adding a direct dependency requires, in the PR description:

- package name and pinned version
- what it is used for in this change
- which frozen document justifies it
- scope: runtime, development, test or build

Prefer standard-library or framework-native capability. Do not add a dependency
because it may be useful later.
