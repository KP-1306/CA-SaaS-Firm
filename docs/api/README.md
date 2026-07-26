# API reference

Empty by design. No endpoint exists yet beyond the bootstrap health check.

Once endpoints are implemented, an OpenAPI specification is generated on every
build and committed here. API conventions — cursor pagination, the error
envelope, versioning and status codes — are specified in EIB §6.

## Planes

| Plane | Prefix | Principal |
| --- | --- | --- |
| Internal | `/api/v1/` | Firm staff |
| Portal | `/portal/api/v1/` | Client organisations |
| Platform | `/platform/api/v1/` | Vendor operators |

## Bootstrap endpoint

`GET /health/` returns `{"status": "ok", "service": "ca-firm-operations-api"}`.
No authentication, no database access, no disclosure beyond liveness.
