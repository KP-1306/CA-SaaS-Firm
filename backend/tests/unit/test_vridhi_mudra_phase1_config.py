"""
Mudra Loan - Phase 1 configuration foundation tests.

Covers the full Phase-1 matrix (Command_17 section 20) plus the mandatory
cross-service regression tests (section 19): the Mudra ServiceProcessStep,
ServiceOperationalField, and document-requirement configuration is seeded
correctly, idempotently, and with a strict EXPLICITLY-MANAGED ownership
boundary that cannot touch another service's process steps.

Phase 1 is CONFIGURATION ONLY: no runtime WorkProcessState, no lifecycle
behaviour, no migration.
"""
from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command

from contexts.configuration.models import (
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    ServiceOperationalField,
    ServiceProcessStep,
    Vertical,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
PRINCIPAL = uuid.UUID("22222222-2222-2222-2222-222222222222")

MUDRA_STEPS = [
    ("APPLICATION", "Application & KYC", 10),
    ("CREDIT_ELIGIBILITY", "Credit & Eligibility", 20),
    ("FILE_PREPARATION", "File Preparation", 30),
    ("BANK_SUBMITTED", "Bank Submitted", 40),
    ("BANK_VERIFICATION", "Bank Verification", 50),
    ("BANK_PENDING", "Bank Pending", 60),
    ("RO_REVIEW", "RO Review", 70),
    ("SANCTIONED", "Sanctioned", 80),
    ("DISBURSEMENT", "Disbursement", 90),
    ("CLOSED", "Closed", 100),
]

ORIGINAL_MUDRA_DOCS = [
    "AADHAAR_CARD", "PAN_CARD", "DOMICILE_CERTIFICATE", "PROJECT_REPORT",
    "AFFIDAVIT", "QUOTATION", "PASSPORT_PHOTO", "ELECTRICITY_BILL",
    "BANK_DETAILS", "UDYAM_CERTIFICATE",
]
NEW_MUDRA_DOCS = [
    "CIBIL_REPORT", "SANCTION_LETTER",
    "SANCTION_CONDITIONS_EVIDENCE", "DISBURSEMENT_EVIDENCE",
]


def _seed():
    call_command(
        "seed_vridhi_loans",
        tenant_id=str(TENANT),
        principal_id=str(PRINCIPAL),
        verbosity=0,
    )


def _domain():
    loans = Vertical.objects.get(tenant_id=TENANT, code="LOANS")
    return Domain.objects.get(
        tenant_id=TENANT, vertical_id=loans.id, code="LOAN_SERVICES",
    )


def _service(code):
    return Service.objects.get(tenant_id=TENANT, domain_id=_domain().id, code=code)


def _steps(code):
    return list(
        ServiceProcessStep.objects.filter(
            tenant_id=TENANT, service_id=_service(code).id, is_active=True,
        ).order_by("display_order", "name", "id")
    )


def _fields(code):
    return list(
        ServiceOperationalField.objects.filter(
            tenant_id=TENANT, service_id=_service(code).id, is_active=True,
        ).order_by("display_order")
    )


def _docs(code):
    svc = _service(code)
    rs = ServiceDocumentRequirementSet.objects.get(tenant_id=TENANT, service_id=svc.id)
    return list(
        ServiceDocumentRequirement.objects.filter(
            tenant_id=TENANT, requirement_set_id=rs.id, is_active=True,
        )
    )


def _make_step(code, step_code, name, order):
    return ServiceProcessStep.objects.create(
        tenant_id=TENANT,
        service_id=_service(code).id,
        code=step_code,
        name=name,
        description="",
        display_order=order,
        is_active=True,
        created_by=PRINCIPAL,
        updated_by=PRINCIPAL,
    )


# 1-2 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_mudra_exists_name_description():
    _seed()
    s = _service("MUDRA_LOAN")
    assert s.name == "Mudra Loan"
    assert s.description == "Mudra loan documentation and processing."


# 3-6 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_exactly_ten_steps_codes_order_names():
    _seed()
    steps = _steps("MUDRA_LOAN")
    assert len(steps) == 10
    assert [s.code for s in steps] == [c for c, _n, _o in MUDRA_STEPS]
    assert [s.display_order for s in steps] == [o for _c, _n, o in MUDRA_STEPS]
    assert [s.name for s in steps] == [n for _c, n, _o in MUDRA_STEPS]


# 7 ------------------------------------------------------------------------
@pytest.mark.django_db
def test_seed_twice_no_duplicate_steps():
    _seed()
    _seed()
    steps = _steps("MUDRA_LOAN")
    assert len(steps) == 10
    assert len({s.code for s in steps}) == 10


# 8 (+ section 19 TEST C) --------------------------------------------------
@pytest.mark.django_db
def test_obsolete_mudra_step_is_deactivated_on_reseed():
    _seed()
    obsolete = _make_step("MUDRA_LOAN", "OLD_MUDRA_STEP", "Old Mudra Step", 999)
    _seed()
    obsolete.refresh_from_db()
    assert obsolete.is_active is False
    active = _steps("MUDRA_LOAN")
    assert len(active) == 10
    assert "OLD_MUDRA_STEP" not in {s.code for s in active}


# 9 + section 19 TEST A — HOME_LOAN foreign step survives -------------------
@pytest.mark.django_db
def test_home_loan_foreign_step_survives_reseed():
    _seed()
    foreign = _make_step("HOME_LOAN", "EXISTING_HOME_LOAN_STEP", "Existing Home Loan Step", 15)
    before = (foreign.name, foreign.display_order, foreign.is_active)
    _seed()
    foreign.refresh_from_db()
    assert (foreign.name, foreign.display_order, foreign.is_active) == before
    assert foreign.is_active is True


# 10 + section 19 TEST B — second non-Mudra service survives ---------------
@pytest.mark.django_db
def test_msme_loan_foreign_step_survives_reseed():
    _seed()
    foreign = _make_step("MSME_LOAN", "EXISTING_MSME_STEP", "Existing MSME Step", 25)
    _seed()
    foreign.refresh_from_db()
    assert foreign.is_active is True
    assert foreign.name == "Existing MSME Step"
    assert foreign.display_order == 25


# extra: no non-Mudra service gets Mudra steps -----------------------------
@pytest.mark.django_db
def test_other_services_have_no_mudra_steps():
    _seed()
    for code in ("MSY_LOAN", "BRE_LOAN", "CAR_LOAN", "HOME_LOAN", "LAP_LOAN",
                 "MSME_LOAN", "LOAN_TAKE_OVER", "OD_LIMIT", "COMMERCIAL_LOAN"):
        assert ServiceProcessStep.objects.filter(
            tenant_id=TENANT, service_id=_service(code).id, is_active=True,
        ).count() == 0, code


# 11 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_exactly_forty_fields():
    _seed()
    assert len(_fields("MUDRA_LOAN")) == 40


# 12-18 --------------------------------------------------------------------
@pytest.mark.django_db
def test_field_groups_present():
    _seed()
    keys = {f.key for f in _fields("MUDRA_LOAN")}
    for required in (
        "requested_loan_amount", "loan_purpose", "business_activity",   # application
        "cibil_score",                                                  # cibil
        "eligibility_result", "rejection_reason",                       # eligibility
        "bank_name", "bank_verification_status",                        # bank
        "sanctioned_amount", "sanction_conditions_status",              # sanction
        "disbursed_amount",                                             # disbursement
        "mudra_outcome",                                                # outcome
    ):
        assert required in keys, required


# 13 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_cibil_score_number_field():
    _seed()
    f = ServiceOperationalField.objects.get(
        tenant_id=TENANT, service_id=_service("MUDRA_LOAN").id, key="cibil_score",
    )
    assert f.is_active and f.field_type == "NUMBER"


# 19-20 --------------------------------------------------------------------
@pytest.mark.django_db
def test_field_keys_unique_and_order_deterministic():
    _seed()
    fields = _fields("MUDRA_LOAN")
    keys = [f.key for f in fields]
    orders = [f.display_order for f in fields]
    assert len(keys) == len(set(keys))
    assert len(orders) == len(set(orders))
    assert orders == sorted(orders)


# required-field semantics: only the three application fields are required --
@pytest.mark.django_db
def test_only_three_fields_generic_required():
    _seed()
    required = {f.key for f in _fields("MUDRA_LOAN") if f.required}
    assert required == {"requested_loan_amount", "loan_purpose", "business_activity"}
    # rejection_reason must NOT be globally required (conditional, later phase).
    rr = ServiceOperationalField.objects.get(
        tenant_id=TENANT, service_id=_service("MUDRA_LOAN").id, key="rejection_reason",
    )
    assert rr.required is False


# 21-24 --------------------------------------------------------------------
@pytest.mark.django_db
def test_documents_retained_added_unique_count():
    _seed()
    codes = [d.code for d in _docs("MUDRA_LOAN")]
    for c in ORIGINAL_MUDRA_DOCS:
        assert c in codes, c
    for c in NEW_MUDRA_DOCS:
        assert c in codes, c
    assert len(codes) == 14
    assert len(codes) == len(set(codes))


# new docs are optional at the generic layer (do not block completion) -----
@pytest.mark.django_db
def test_new_documents_are_optional():
    _seed()
    for d in _docs("MUDRA_LOAN"):
        if d.code in NEW_MUDRA_DOCS:
            assert d.mandatory is False, d.code


# 25 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_reseed_no_duplicate_documents():
    _seed()
    _seed()
    codes = [d.code for d in _docs("MUDRA_LOAN")]
    assert len(codes) == 14
    assert len(codes) == len(set(codes))


# 26-27 non-Mudra field/document configuration unchanged -------------------
@pytest.mark.django_db
def test_other_service_field_and_doc_counts_stable_across_reseed():
    _seed()
    def fingerprint():
        fp = {}
        for code in ("HOME_LOAN", "CAR_LOAN", "MSME_LOAN"):
            fp[code] = (
                len(_fields(code)),
                {f.key for f in _fields(code)},
                len(_docs(code)),
                {d.code for d in _docs(code)},
            )
        return fp
    before = fingerprint()
    _seed()
    assert fingerprint() == before


# 28 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_seed_creates_no_work_process_state():
    _seed()
    from contexts.work.models import WorkProcessState
    assert WorkProcessState.objects.count() == 0


# 29 -----------------------------------------------------------------------
@pytest.mark.django_db
def test_workstatus_unchanged():
    from contexts.work.models import WorkStatus
    assert [s.value for s in WorkStatus] == [
        "NOT_STARTED", "IN_PROGRESS", "WAITING_FOR_CLIENT", "READY_FOR_REVIEW",
        "REWORK_REQUIRED", "COMPLETED", "CANCELLED",
    ]


# idempotency: full Mudra config identical after three runs ----------------
@pytest.mark.django_db
def test_full_idempotency_three_runs():
    def snap():
        return (
            sorted((s.code, s.name, s.display_order) for s in _steps("MUDRA_LOAN")),
            sorted((f.key, f.field_type, f.display_order) for f in _fields("MUDRA_LOAN")),
            sorted(d.code for d in _docs("MUDRA_LOAN")),
        )
    _seed(); a = snap()
    _seed(); b = snap()
    _seed(); c = snap()
    assert a == b == c
    assert len(a[0]) == 10 and len(a[1]) == 40 and len(a[2]) == 14


# ---------------------------------------------------------------------------
# Rollback round-trip (Command_19 section 11): PRE -> snapshot -> apply Mudra
# config -> restore -> equals PRE, over the COMPLETE mutation surface of
# _seed_service (Service, ServiceProcessStep, ServiceOperationalField,
# ServiceDocumentRequirementSet, ServiceDocumentRequirement).
# ---------------------------------------------------------------------------
SERVICE_ATTRS = ["name", "description", "status"]
STEP_ATTRS = ["name", "description", "display_order", "is_active"]
FIELD_ATTRS = ["label", "field_type", "help_text", "placeholder",
               "required", "options", "display_order", "is_active"]
SET_ATTRS = ["name", "status", "description"]
DOC_ATTRS = ["name", "description", "category", "mandatory",
             "display_order", "is_active"]


def _snapshot_mudra():
    svc = _service("MUDRA_LOAN")
    steps = [dict(code=s.code, **{a: getattr(s, a) for a in STEP_ATTRS})
             for s in ServiceProcessStep.objects.filter(tenant_id=TENANT, service_id=svc.id)]
    fields = [dict(key=f.key, **{a: getattr(f, a) for a in FIELD_ATTRS})
              for f in ServiceOperationalField.objects.filter(tenant_id=TENANT, service_id=svc.id)]
    sets = []
    for rs in ServiceDocumentRequirementSet.objects.filter(tenant_id=TENANT, service_id=svc.id):
        docs = [dict(code=d.code, **{a: getattr(d, a) for a in DOC_ATTRS})
                for d in ServiceDocumentRequirement.objects.filter(tenant_id=TENANT, requirement_set_id=rs.id)]
        sets.append(dict(version_number=rs.version_number,
                         **{a: getattr(rs, a) for a in SET_ATTRS}, documents=docs))
    return {"name": svc.name, "description": svc.description, "status": svc.status,
            "process_steps": steps, "operational_fields": fields, "requirement_sets": sets}


def _apply_mudra_only():
    # Mirror apply_mudra_config.py: production _seed_service for MUDRA_LOAN only.
    from contexts.configuration.management.commands.seed_vridhi_loans import (
        SERVICES, _seed_service,
    )
    _seed_service(tenant_id=TENANT, principal_id=PRINCIPAL, domain=_domain(),
                  code="MUDRA_LOAN", definition=SERVICES["MUDRA_LOAN"])


def _restore_mudra(snap):
    svc = _service("MUDRA_LOAN")
    for a in SERVICE_ATTRS:
        setattr(svc, a, snap[a])
    svc.save()
    snap_steps = {s["code"]: s for s in snap["process_steps"]}
    for o in ServiceProcessStep.objects.filter(tenant_id=TENANT, service_id=svc.id):
        s = snap_steps.get(o.code)
        if s is None:
            if o.is_active:
                o.is_active = False; o.save()
        else:
            for a in STEP_ATTRS:
                setattr(o, a, s[a])
            o.save()
    snap_fields = {f["key"]: f for f in snap["operational_fields"]}
    for o in ServiceOperationalField.objects.filter(tenant_id=TENANT, service_id=svc.id):
        s = snap_fields.get(o.key)
        if s is None:
            if o.is_active:
                o.is_active = False; o.save()
        else:
            for a in FIELD_ATTRS:
                setattr(o, a, s[a])
            o.save()
    snap_sets = {rs["version_number"]: rs for rs in snap["requirement_sets"]}
    for rs in ServiceDocumentRequirementSet.objects.filter(tenant_id=TENANT, service_id=svc.id):
        s = snap_sets.get(rs.version_number)
        if s is None:
            rs.status = "RETIRED"; rs.save()
            for d in ServiceDocumentRequirement.objects.filter(tenant_id=TENANT, requirement_set_id=rs.id):
                if d.is_active:
                    d.is_active = False; d.save()
        else:
            for a in SET_ATTRS:
                setattr(rs, a, s[a])
            rs.save()
            snap_docs = {d["code"]: d for d in s["documents"]}
            for d in ServiceDocumentRequirement.objects.filter(tenant_id=TENANT, requirement_set_id=rs.id):
                sd = snap_docs.get(d.code)
                if sd is None:
                    if d.is_active:
                        d.is_active = False; d.save()
                else:
                    for a in DOC_ATTRS:
                        setattr(d, a, sd[a])
                    d.save()


@pytest.mark.django_db
def test_rollback_roundtrip_full_surface():
    # Establish a pre-Phase-1 state with the catalogue present, then inject
    # deliberate pre-existing differences across the whole mutation surface.
    _seed()

    svc = _service("MUDRA_LOAN")
    svc.description = "PRE description"
    svc.status = "INACTIVE"
    svc.save()

    # obsolete Mudra-owned step present before Phase-1 reseed
    ServiceProcessStep.objects.create(
        tenant_id=TENANT, service_id=svc.id, code="PRE_ONLY_STEP",
        name="Pre Only", description="pre", display_order=888, is_active=True,
        created_by=PRINCIPAL, updated_by=PRINCIPAL,
    )
    # existing field with outdated metadata
    fld = ServiceOperationalField.objects.get(tenant_id=TENANT, service_id=svc.id, key="requested_loan_amount")
    fld.label = "PRE LABEL"; fld.display_order = 7; fld.help_text = "pre ht"; fld.save()
    # requirement set + one document with pre values
    rs = ServiceDocumentRequirementSet.objects.get(tenant_id=TENANT, service_id=svc.id, version_number=1)
    rs.name = "PRE SET NAME"; rs.description = "PRE SET DESC"; rs.save()
    doc = ServiceDocumentRequirement.objects.get(tenant_id=TENANT, requirement_set_id=rs.id, code="AADHAAR_CARD")
    doc.mandatory = not doc.mandatory; doc.display_order = 1; doc.save()

    pre = _snapshot_mudra()

    # Apply Phase-1 Mudra config (mirrors the Mudra-only applier), then restore.
    _apply_mudra_only()
    _restore_mudra(pre)

    post = _snapshot_mudra()

    # Service business attributes restored exactly.
    assert (post["name"], post["description"], post["status"]) == (
        pre["name"], pre["description"], pre["status"])

    # Every PRE row restored to its exact pre attributes.
    def index_steps(s): return {r["code"]: r for r in s["process_steps"]}
    def index_fields(s): return {r["key"]: r for r in s["operational_fields"]}
    def index_docs(s):
        return {(rs["version_number"], d["code"]): d
                for rs in s["requirement_sets"] for d in rs["documents"]}

    pre_steps, post_steps = index_steps(pre), index_steps(post)
    for code, r in pre_steps.items():
        assert {a: post_steps[code][a] for a in STEP_ATTRS} == {a: r[a] for a in STEP_ATTRS}
    pre_fields, post_fields = index_fields(pre), index_fields(post)
    for key, r in pre_fields.items():
        assert {a: post_fields[key][a] for a in FIELD_ATTRS} == {a: r[a] for a in FIELD_ATTRS}
    pre_docs, post_docs = index_docs(pre), index_docs(post)
    for ident, r in pre_docs.items():
        assert {a: post_docs[ident][a] for a in DOC_ATTRS} == {a: r[a] for a in DOC_ATTRS}

    # Requirement set business attributes restored.
    pre_sets = {rs["version_number"]: rs for rs in pre["requirement_sets"]}
    post_sets = {rs["version_number"]: rs for rs in post["requirement_sets"]}
    for ver, r in pre_sets.items():
        assert {a: post_sets[ver][a] for a in SET_ATTRS} == {a: r[a] for a in SET_ATTRS}

    # Every Phase-1-introduced row is present but inactive (history preserved).
    for code, r in post_steps.items():
        if code not in pre_steps:
            assert r["is_active"] is False
    for key, r in post_fields.items():
        if key not in pre_fields:
            assert r["is_active"] is False
    for ident, r in post_docs.items():
        if ident not in pre_docs:
            assert r["is_active"] is False


@pytest.mark.django_db
def test_rollback_repairs_description_only_drift():
    # A description-only drift on a process step must be repaired by restore
    # (regression against the Command_19 section 9 conditional bug).
    _seed()
    svc = _service("MUDRA_LOAN")
    step = ServiceProcessStep.objects.filter(
        tenant_id=TENANT, service_id=svc.id, code="APPLICATION").first()
    original_desc = step.description
    pre = _snapshot_mudra()

    # Introduce a description-only change.
    step.description = "DRIFTED DESCRIPTION ONLY"
    step.save()

    _restore_mudra(pre)

    step.refresh_from_db()
    assert step.description == original_desc
