# Architecture reference

## Frozen documents

These are the source of truth. This repository implements them; it does not
reinterpret them. They are **read-only references** and are superseded only by
a formal Change Request, never edited in place.

| Document | Role |
| --- | --- |
| **BL Rev 3** — Requirement Understanding (frozen baseline) | What the product must do, and why |
| **AR v1.0** — Product Architecture & Domain Model | Bounded contexts, planes, boundaries, ADR-001…020 |
| **TD v1.0** — Technical Design & Engineering Specification | Entities, contracts, invariants, error codes, conformance suite |
| **ERR v1.0** — Engineering Readiness Review | Gap analysis, module readiness, dependency order |
| **TAD v1.0** — Technology Architecture Decision | The frozen technology stack and its justification |
| **EIB v1.0** — Engineering Implementation Blueprint | The engineering constitution |

The document files themselves are held outside this repository. Copy them into
this directory during onboarding, or link to the controlled location.

## Conflict handling

Where documents disagree, or where a document is ambiguous:

1. Do not choose whichever reading you prefer.
2. Do not resolve it silently in code.
3. Record the exact conflict with document names and section references.
4. Stop only the affected work item; continue unaffected work.
5. Raise it for human decision as a Clarification or a Change Request.

## Load-bearing decisions

A short list of decisions whose violation would be an architecture breach
rather than a defect:

| Decision | Source |
| --- | --- |
| Modular monolith — not microservices | AR ADR-001 |
| PostgreSQL row-level security is a load-bearing isolation mechanism | AR §7.5, ADR-002 |
| Two structurally distinct principal types; a portal principal cannot hold internal permissions | AR ADR-003 |
| Portal publication is allow-list, never a filtered internal view | AR ADR-004 |
| Workflow versions are immutable; instances bind at creation | AR ADR-005 |
| Audit is written inside the business transaction | AR ADR-008 |
| One path per operation — bulk and background paths use the same service | AR §3.4 |
| The Django admin is never routed | EIB §7.4 |
