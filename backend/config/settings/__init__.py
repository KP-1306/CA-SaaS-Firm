"""Settings package.

Four modules with a strict separation between development convenience and
production safety (EIB §4.13, EWP-000.1A §9):

    base.py         shared configuration, no environment-specific defaults
    development.py  local development only
    test.py         automated test runs; no database connection required
    production.py   fails fast when a mandatory secret is absent
"""
