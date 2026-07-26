# API clients

Typed clients for the backend REST API, one module per resource group.

Internal-plane and portal-plane clients must remain separate: they address
different URL prefixes, carry different session cookies and must not share
authentication state (AR §2.4).

Empty by design. Owned by later work packages.
