"""Bootstrap health endpoint.

Proves that the Django application starts and can serve a request. It exposes
no business information, requires no database access and discloses no
environment, dependency or configuration detail (EWP-000.1A §12).

This is not an observability framework. Readiness probes, dependency checks and
metrics are owned by the observability work package.
"""
