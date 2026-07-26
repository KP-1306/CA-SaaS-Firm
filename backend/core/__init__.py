"""Shared infrastructure.

`core` is NOT a bounded context. It holds cross-cutting technical concerns that
every context depends on and that depend on no context in return (AR §6.1).

Adding domain behaviour here is an architecture violation: domain logic belongs
to a bounded context under `contexts/`.
"""
