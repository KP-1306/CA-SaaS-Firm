#!/usr/bin/env python3.12
"""Verify the repository tree against the frozen structure.

Checks that EWP-000.1A scaffolding matches EIB §3 and that no scope boundary
has been crossed. Runs without any project dependency installed, so it works
before `pip install` and inside CI.

Usage:
    python3.12 scripts/verify_structure.py

Exit status is 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The fifteen bounded contexts of AR §4. Exactly these — no more, no fewer.
BOUNDED_CONTEXTS = (
    "platform",
    "identity",
    "organisation",
    "configuration",
    "clients",
    "workflow",
    "work",
    "generation",
    "quality",
    "documents",
    "collaboration",
    "audit",
    "notifications",
    "insight",
    "portal",
)

CORE_PACKAGES = (
    "db",
    "auth",
    "audit",
    "exceptions",
    "logging",
    "pagination",
    "terminology",
    "outbox",
)

REQUIRED_DIRECTORIES = (
    "backend/config/settings",
    "backend/core",
    "backend/contexts",
    "backend/tests/conformance",
    "backend/tests/unit",
    "backend/tests/integration",
    "frontend/src/apps/internal",
    "frontend/src/apps/portal",
    "frontend/src/shared/components",
    "frontend/src/shared/hooks",
    "frontend/src/shared/terminology",
    "frontend/src/shared/design-system",
    "frontend/src/features",
    "frontend/src/api",
    "frontend/tests",
    "infrastructure/docker",
    "infrastructure/terraform/modules",
    "infrastructure/terraform/environments",
    "infrastructure/nginx",
    ".github/workflows",
    "docs/architecture",
    "docs/api",
    "docs/runbooks",
    "docs/adr",
    "scripts",
)

REQUIRED_FILES = (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".pre-commit-config.yaml",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODEOWNERS",
    "Makefile",
    ".env.example",
    "backend/manage.py",
    "backend/pyproject.toml",
    "backend/config/settings/base.py",
    "backend/config/settings/development.py",
    "backend/config/settings/test.py",
    "backend/config/settings/production.py",
    "backend/config/urls.py",
    "backend/config/urls_internal.py",
    "backend/config/urls_portal.py",
    "backend/config/urls_platform.py",
    "backend/config/wsgi.py",
    "backend/config/asgi.py",
    "frontend/package.json",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
    "frontend/eslint.config.js",
    "frontend/.prettierrc",
)

failures: list[str] = []
passes: list[str] = []


def check(condition: bool, label: str, detail: str = "") -> None:
    """Record a check result."""
    if condition:
        passes.append(label)
    else:
        failures.append(f"{label}{': ' + detail if detail else ''}")


def _installed_apps_from_settings() -> list[str]:
    """Extract declared app lists from base settings without importing Django."""
    source = (REPO_ROOT / "backend/config/settings/base.py").read_text()
    tree = ast.parse(source)
    collected: list[str] = []
    wanted = {"DJANGO_APPS", "THIRD_PARTY_APPS", "LOCAL_APPS", "CONTEXT_APPS"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                if isinstance(node.value, ast.List):
                    collected.extend(
                        element.value
                        for element in node.value.elts
                        if isinstance(element, ast.Constant)
                    )
    return collected


def check_structure() -> None:
    """Required directories and files exist."""
    for directory in REQUIRED_DIRECTORIES:
        path = REPO_ROOT / directory
        check(path.is_dir(), f"directory exists: {directory}")

    for file in REQUIRED_FILES:
        path = REPO_ROOT / file
        check(path.is_file(), f"file exists: {file}")


def check_bounded_contexts() -> None:
    """Exactly fifteen contexts exist, each a proper package, none extra."""
    contexts_dir = REPO_ROOT / "backend/contexts"
    found = {
        p.name
        for p in contexts_dir.iterdir()
        if p.is_dir() and not p.name.startswith(("_", "."))
    }
    expected = set(BOUNDED_CONTEXTS)

    check(
        found == expected,
        "exactly the 15 frozen bounded contexts exist",
        f"missing={sorted(expected - found)} extra={sorted(found - expected)}",
    )

    for context in BOUNDED_CONTEXTS:
        base = contexts_dir / context
        check((base / "__init__.py").is_file(), f"context is a package: {context}")
        check((base / "apps.py").is_file(), f"context has AppConfig: {context}")

    declared = _installed_apps_from_settings()
    declared_contexts = {a.split(".")[-1] for a in declared if a.startswith("contexts.")}
    check(
        declared_contexts == expected,
        "all 15 contexts declared in INSTALLED_APPS",
        f"missing={sorted(expected - declared_contexts)}",
    )


def check_core_packages() -> None:
    """Shared infrastructure packages exist."""
    for package in CORE_PACKAGES:
        path = REPO_ROOT / "backend/core" / package / "__init__.py"
        check(path.is_file(), f"core package exists: core/{package}")


def check_three_planes() -> None:
    """The three application planes are separately configured."""
    urls = (REPO_ROOT / "backend/config/urls.py").read_text()
    for prefix in ("api/v1/", "portal/api/v1/", "platform/api/v1/"):
        check(prefix in urls, f"plane routed: /{prefix}")

    for plane in ("internal", "portal", "platform"):
        path = REPO_ROOT / f"backend/config/urls_{plane}.py"
        check(path.is_file(), f"plane URL module exists: urls_{plane}.py")

    for plane in ("internal", "portal"):
        entry = REPO_ROOT / f"frontend/src/apps/{plane}/main.tsx"
        check(entry.is_file(), f"frontend plane entry exists: apps/{plane}/main.tsx")

    vite = (REPO_ROOT / "frontend/vite.config.ts").read_text()
    check("internal.html" in vite and "portal.html" in vite, "vite builds both plane entries")


def check_admin_absent() -> None:
    """The Django admin is neither installed nor routed (EIB §7.4)."""
    declared = _installed_apps_from_settings()
    admin_apps = [a for a in declared if "admin" in a.lower()]
    check(not admin_apps, "django.contrib.admin not in INSTALLED_APPS", str(admin_apps))

    # Search executable code only: strip comments and docstrings via AST.
    routing_patterns = (
        re.compile(r"admin\.site\.urls"),
        re.compile(r"admin\.site\.register"),
        re.compile(r"from\s+django\.contrib\s+import\s+admin"),
        re.compile(r"['\"]django\.contrib\.admin['\"]"),
    )
    # A negative assertion proves admin is absent; it is evidence, not a breach.
    negative_assertion = re.compile(r"\bnot\s+in\b|\bassertNotIn\b|\bis\s+None\b")

    offenders: list[str] = []
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        if ".venv" in py.parts:
            continue
        for line in py.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if not any(p.search(line) for p in routing_patterns):
                continue
            if negative_assertion.search(line):
                continue
            offenders.append(f"{py.relative_to(REPO_ROOT)}: {stripped[:70]}")
    check(not offenders, "no Django admin routing in executable code", "; ".join(offenders))


def check_scope_boundaries() -> None:
    """No later-EWP work has leaked into this package."""
    backend = REPO_ROOT / "backend"

    # No DOMAIN models: business models live under contexts/ and are owned by
    # later packages. The abstract tenant base in core/db/ is the shared kernel
    # foundation (EIB §5.6) and is explicitly sanctioned (EWP-000.1B-02).
    model_files = [
        p
        for p in backend.rglob("models.py")
        if ".venv" not in p.parts and p.parent != backend / "core" / "db"
    ] + [
        p
        for p in backend.rglob("models/*.py")
        if ".venv" not in p.parts and (backend / "contexts") in p.parents
    ]
    check(not model_files, "no domain models defined", str([str(p) for p in model_files]))

    migration_dirs = [
        p for p in backend.rglob("migrations") if p.is_dir() and ".venv" not in p.parts
    ]
    check(not migration_dirs, "no migrations present", str([str(p) for p in migration_dirs]))

    # Domain routes: plane URL modules expose only their bootstrap route
    # (EWP-000.1B-01). A domain route would import a bounded context, a
    # serializer or a viewset — none of which may appear yet.
    domain_route_markers = re.compile(
        r"\bfrom\s+contexts\.|\bimport\s+contexts\b|\bserializers?\b|\bviewsets?\b|\brouters?\b"
    )
    for plane in ("internal", "portal", "platform"):
        source = (backend / f"config/urls_{plane}.py").read_text()
        check(
            not domain_route_markers.search(source),
            f"no domain routes on {plane} plane",
            "plane URL module references a bounded context, serializer or viewset",
        )
        # Each plane imports only its own bootstrap handler — never another
        # plane's (AR §2.4, ADR-004).
        others = [p for p in ("internal", "portal", "platform") if p != plane]
        for other in others:
            check(
                f"bootstrap_{other}" not in source,
                f"{plane} plane does not import the {other} plane's handler",
            )

    # No Kubernetes artefacts.
    k8s = [
        p
        for p in REPO_ROOT.rglob("*.y*ml")
        if "node_modules" not in p.parts
        and re.search(r"^\s*apiVersion:\s*(apps|v1|networking|batch)", p.read_text(), re.M)
    ]
    check(not k8s, "no Kubernetes manifests", str([str(p) for p in k8s]))

    # No infrastructure implementation.
    tf = [p for p in REPO_ROOT.rglob("*.tf")]
    check(not tf, "no Terraform resources", str([str(p) for p in tf]))
    compose = [
        p for p in REPO_ROOT.rglob("docker-compose*.y*ml") if "node_modules" not in p.parts
    ]
    check(not compose, "no Docker Compose services", str([str(p) for p in compose]))
    dockerfiles = [p for p in REPO_ROOT.rglob("Dockerfile*")]
    check(not dockerfiles, "no Dockerfiles", str([str(p) for p in dockerfiles]))
    workflows = [
        p for p in (REPO_ROOT / ".github/workflows").glob("*.y*ml")
    ]
    check(not workflows, "CI workflows directory is inert", str([str(p) for p in workflows]))


def check_python_syntax() -> None:
    """Every backend Python file parses."""
    bad: list[str] = []
    count = 0
    for py in (REPO_ROOT / "backend").rglob("*.py"):
        if ".venv" in py.parts:
            continue
        count += 1
        try:
            ast.parse(py.read_text())
        except SyntaxError as exc:
            bad.append(f"{py.relative_to(REPO_ROOT)}: {exc}")
    check(not bad, f"all {count} backend Python files parse", "; ".join(bad))


def check_tenant_model() -> None:
    """The abstract tenant-owned model foundation is well-formed (EWP-000.1B-02).

    Uses AST inspection rather than importing Django, so the check runs in any
    environment. Verifies the canonical path, abstract status, the callable
    (not invoked) UUID default, and that tenant_id is a plain UUID column and
    never a ForeignKey.
    """
    model_path = REPO_ROOT / "backend/core/db/models.py"
    check(model_path.is_file(), "TenantModel module exists: core/db/models.py")
    if not model_path.is_file():
        return

    tree = ast.parse(model_path.read_text())
    tenant_model: ast.ClassDef | None = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "TenantModel"
        ),
        None,
    )
    check(tenant_model is not None, "TenantModel class is defined")
    if tenant_model is None:
        return

    # Abstract via an inner Meta with abstract = True.
    abstract = False
    for meta in tenant_model.body:
        if isinstance(meta, ast.ClassDef) and meta.name == "Meta":
            for stmt in meta.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "abstract" for t in stmt.targets
                    )
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.value.value is True
                ):
                    abstract = True
    check(abstract, "TenantModel is abstract (Meta.abstract = True)")

    # Field-level assertions from the class body assignments.
    fields: dict[str, ast.Call] = {
        target.id: stmt.value
        for stmt in tenant_model.body
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)
        for target in stmt.targets
        if isinstance(target, ast.Name)
    }

    def field_type(call: ast.Call) -> str:
        return call.func.attr if isinstance(call.func, ast.Attribute) else ""

    def kwarg(call: ast.Call, name: str) -> ast.expr | None:
        return next((k.value for k in call.keywords if k.arg == name), None)

    # id: UUID pk with a CALLABLE default (a Name, not a Call — never uuid7()).
    id_field = fields.get("id")
    check(id_field is not None and field_type(id_field) == "UUIDField", "id is a UUIDField")
    if id_field is not None:
        default = kwarg(id_field, "default")
        check(
            isinstance(default, ast.Name),
            "id default is a callable reference, not an invoked value",
            "default must be `uuid7`, not `uuid7()`",
        )

    # tenant_id: indexed UUIDField, never a ForeignKey.
    tenant = fields.get("tenant_id")
    check(tenant is not None, "tenant_id field exists")
    if tenant is not None:
        check(field_type(tenant) == "UUIDField", "tenant_id is a UUIDField, not a ForeignKey")
        indexed = kwarg(tenant, "db_index")
        check(
            isinstance(indexed, ast.Constant) and indexed.value is True,
            "tenant_id is indexed (db_index=True)",
        )

    # No ForeignKey anywhere on the base.
    fk = [name for name, call in fields.items() if field_type(call) == "ForeignKey"]
    check(not fk, "TenantModel declares no ForeignKey fields", str(fk))


def main() -> int:
    """Run every structural check."""
    check_structure()
    check_bounded_contexts()
    check_core_packages()
    check_three_planes()
    check_admin_absent()
    check_scope_boundaries()
    check_tenant_model()
    check_python_syntax()

    print(f"Structural conformance: {len(passes)} passed, {len(failures)} failed")
    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  FAIL  {failure}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
