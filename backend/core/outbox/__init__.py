"""Transactional outbox.

Owns domain event capture written in the same transaction as the state change,
and the relay that publishes it (AR ADR-009).

Not implemented by EWP-000.1A. This package exists because the frozen structure
requires it.
"""
