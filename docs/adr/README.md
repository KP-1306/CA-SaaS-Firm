# Architecture Decision Records

ADR-001 to ADR-020 were decided during the architecture stage and are recorded
in **AR v1.0 §16**. They are frozen.

New ADRs are numbered from ADR-021 and are added here when an implementation
decision has architectural consequence. An ADR is required when a decision:

- changes a boundary between bounded contexts;
- changes how a plane is separated;
- changes a security or isolation mechanism;
- introduces or removes an infrastructure dependency;
- would be expensive to reverse once production data exists.

An implementation decision that contradicts a frozen ADR is either a defect
(fix it) or a Change Request (raise it). It is never a new ADR.

## Template

```markdown
# ADR-0NN: <title>

- **Status:** Proposed | Accepted | Superseded by ADR-0NN
- **Date:** YYYY-MM-DD
- **Work package:** EWP-000.NX

## Context
What forces are at play, and which frozen sections apply.

## Decision
What was decided.

## Alternatives considered
What else was evaluated, and why it was rejected.

## Consequences
Positive, negative, and the cost of reversal.
```
