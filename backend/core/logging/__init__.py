"""Logging infrastructure.

Owns structured logging and the sensitive-field redaction that keeps client
business data out of external log transport (TD §16.2, EIB §4.11).

Not implemented by EWP-000.1A; bootstrap logging is configured directly in
config.settings.base. This package exists because the frozen structure
requires it.
"""
