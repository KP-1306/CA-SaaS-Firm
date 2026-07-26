"""Audit infrastructure.

Owns append-only audit event capture, written inside the same transaction as
the business change it records (AR ADR-008).

Not implemented by EWP-000.1A. This package exists because the frozen structure
requires it.
"""
