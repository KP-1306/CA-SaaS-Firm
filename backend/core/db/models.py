"""Tenant-owned model foundation.

``TenantModel`` is the abstract base that every tenant-owned entity inherits
(TD Â§2.1, EIB Â§5.6). It carries the seven universal columns and nothing else â€”
soft-delete, organisation scoping and status live in separate contracts.

Two invariants are established here:

* **Identity is time-ordered.** ``id`` defaults to :func:`uuid7`, a UUIDv7
  generator, so primary keys sort by creation time (TD Â§2.1).
* **Every save advances the row version.** ``row_version`` starts at 0 on an
  unsaved instance and increments by exactly one per successful save
  (EIB Â§5.5). This is the substrate for later optimistic-concurrency checks;
  this package establishes the increment only â€” it performs no conflict
  detection (that is a later package).

Tenant isolation itself â€” the RLS session variable and tenant-scoped managers
of AR Â§7.5 / TD Â§2.2 â€” is *not* implemented here. ``tenant_id`` is a plain
indexed UUID column, never a foreign key: referential integrity is enforced on
``(tenant_id, id)`` pairs by later work, and a cross-schema FK would defeat the
isolation model.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import models
from django.db.models.base import ModelBase

from .uuid7 import uuid7


class TenantModel(models.Model):
    """Abstract base for all tenant-owned entities (TD Â§2.1, EIB Â§5.6)."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    tenant_id = models.UUIDField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.UUIDField()
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.UUIDField()
    row_version = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def save(
        self,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Persist the instance, advancing ``row_version`` by one.

        The increment happens in memory before the write, so the first save
        persists 1, the second 2, and so on.

        If ``update_fields`` is supplied it enumerates the exact columns to
        write, so ``row_version`` is added to it â€” otherwise the in-memory
        value would advance while the database column stayed stale.

        ``QuerySet.update()`` bypasses ``save()`` entirely and is therefore
        outside this guarantee (documented, not intercepted, per EWP-000.1B-02).
        """
        self.row_version += 1

        if update_fields is not None:
            update_fields = {*update_fields, "row_version"}

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
