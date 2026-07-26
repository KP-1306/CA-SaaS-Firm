"""Database infrastructure.

Owns the tenant-scoped model base, tenant-aware managers, row-level security
session handling and migration validation.

Not implemented by EWP-000.1A. The tenant isolation mechanisms of AR §7.5 and
the data-access contract of TD §2.2 are owned by a later work package. This
package exists because the frozen structure requires it (EIB §3.1).
"""
