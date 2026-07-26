"""UUIDv7 generation for tenant-owned identifiers.

Time-ordered UUIDv7 primary keys are mandated for tenant-owned entities
(TD §2.1): the leading timestamp gives natural insertion ordering and reduces
index fragmentation versus random UUIDv4. The generator is a thin, stable
wrapper over the approved ``uuid6`` package (EIB §15.2) so that every model
references one project-owned import path as its field default.

The wrapper is a *callable* used as ``default=uuid7`` — never ``default=uuid7()``
— so Django calls it per row and can serialise the reference in migrations.
"""

from __future__ import annotations

from uuid import UUID

import uuid6


def uuid7() -> UUID:
    """Return a fresh time-ordered UUID version 7.

    Suitable as a Django field default: ``id = models.UUIDField(default=uuid7)``.
    Returns a standard-library :class:`uuid.UUID` whose ``version`` is 7.
    """
    return uuid6.uuid7()
