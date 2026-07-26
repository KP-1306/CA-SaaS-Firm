# CI/CD workflows

**Inert directory.** EWP-000.1A creates the location only; no workflow is
defined yet (EWP-000.1A §5).

The pipeline specified by EIB §16.2 will gate every pull request on:

| Stage | Gate |
| --- | --- |
| Lint (ruff, eslint) | Blocks merge |
| Type check (mypy, tsc) | Blocks merge |
| Boundary enforcement | Blocks merge |
| Migration validation (tenant scoping + RLS policy present) | Blocks merge |
| Unit tests | Blocks merge |
| CF-ISO isolation suite | **Release gate** |
| CF-AUTHZ permission suite | **Release gate** |
| CF-WFL workflow suite | Blocks merge |
| Secret scan | Blocks merge |

Owned by a later work package.
