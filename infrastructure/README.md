# Infrastructure

**Skeleton only.** EWP-000.1A creates the directory structure required by the
frozen repository layout. It implements no infrastructure.

| Directory | Contents | Owning stage |
| --- | --- | --- |
| `docker/` | Docker Compose for local development; production image | Later EWP |
| `terraform/modules/` | Reusable modules: RDS, Redis, S3, EKS | Later EWP |
| `terraform/environments/` | `prod-single` (single firm), `prod-multi` (future) | Later EWP |
| `nginx/` | Reverse proxy and TLS termination | Later EWP |

## Phase 1 deployment shape

The first implementation serves a **single CA firm**. The deployment is
Docker Compose on one adequately specified instance — not Kubernetes (EIB §2.2).
One firm does not justify cluster management, and a small team cannot operate
it well.

The application code is identical either way. Migrating to a cluster when a
second firm onboards is a deployment change, not an application change.
