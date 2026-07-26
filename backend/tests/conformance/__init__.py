"""Conformance suite (TD §17).

The operative definition of "functionally equivalent": two implementations are
equivalent if and only if both pass this suite.

Families:
    cf_iso    isolation — cross-tenant and cross-organisation   (release gate)
    cf_authz  authorisation — permission matrix and scopes      (release gate)
    cf_wfl    workflow state machine                            (release gate)
    cf_sla    working-time, due dates, SLA attribution
    cf_gen    generation, duplicate detection, chunking

Empty until the work packages that implement the mechanisms under test.
Populating a family before its mechanism exists would produce tests that pass
vacuously, which is worse than no test.
"""
