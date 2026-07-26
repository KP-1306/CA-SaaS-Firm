"""Bounded contexts.

The fifteen contexts of AR §4. Each is a Django application package.

Contexts communicate through module contracts, never by importing another
context's models or querying its tables (AR §6.1 rule 2, EIB §4.2). Violating
that rule is how a modular monolith becomes unmaintainable, so it is enforced
by a boundary check rather than left to discipline.

Every context package currently contains only its AppConfig and a scope note.
Domain models, services and routes are owned by later work packages.
"""
