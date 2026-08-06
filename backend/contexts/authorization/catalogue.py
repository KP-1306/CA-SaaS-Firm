from __future__ import annotations


ROLE_TEMPLATES = (
    {
        "code": "PARTNER",
        "name": "Partner",
        "description": "Firm-wide leadership and approval access.",
    },
    {
        "code": "MANAGER",
        "name": "Manager",
        "description": "Team management, review and work-allocation access.",
    },
    {
        "code": "SENIOR_CONSULTANT",
        "name": "Senior Consultant",
        "description": "Senior delivery and limited review access.",
    },
    {
        "code": "CONSULTANT",
        "name": "Consultant",
        "description": "Standard client and work execution access.",
    },
    {
        "code": "ARTICLE_ASSISTANT",
        "name": "Article Assistant",
        "description": "Supervised work execution access.",
    },
    {
        "code": "ACCOUNTS",
        "name": "Accounts",
        "description": "Billing and financial administration access.",
    },
    {
        "code": "HR",
        "name": "HR",
        "description": "Employee administration access.",
    },
    {
        "code": "RECEPTION",
        "name": "Reception",
        "description": "Basic client coordination access.",
    },
    {
        "code": "READ_ONLY",
        "name": "Read Only",
        "description": "View-only access.",
    },
)


ACCESS_CATALOGUE = (
    ("clients.view", "Client Management", "View Clients"),
    ("clients.create", "Client Management", "Create Clients"),
    ("clients.edit", "Client Management", "Edit Clients"),
    ("clients.delete", "Client Management", "Delete Clients"),
    ("employees.view", "Employee Management", "View Employees"),
    ("employees.manage", "Employee Management", "Manage Employees"),
    ("work.view", "Workflow", "View Work"),
    ("work.create", "Workflow", "Create Work"),
    ("work.assign", "Workflow", "Assign Work"),
    ("work.reassign", "Workflow", "Reassign Work"),
    ("work.submit", "Workflow", "Submit Work for Review"),
    ("work.approve", "Workflow", "Approve Work"),
    ("work.close", "Workflow", "Close Work"),
    ("documents.view", "Documents", "View Documents"),
    ("documents.upload", "Documents", "Upload Documents"),
    ("documents.review", "Documents", "Review Documents"),
    ("documents.approve", "Documents", "Approve Documents"),
    ("quality.review", "Quality", "Perform QA Review"),
    ("quality.manage", "Quality", "Manage QA Configuration"),
    ("reports.view", "Reports", "View Reports"),
    ("reports.export", "Reports", "Export Reports"),
    ("firm.manage", "Administration", "Manage Firm"),
    ("services.manage", "Administration", "Manage Services"),
    ("access.manage", "Administration", "Manage Employee Access"),
    ("audit.view", "Administration", "View Audit History"),
)


ROLE_ACCESS_CODES = {
    "PARTNER": tuple(code for code, _, _ in ACCESS_CATALOGUE),
    "MANAGER": (
        "clients.view",
        "clients.create",
        "clients.edit",
        "employees.view",
        "work.view",
        "work.create",
        "work.assign",
        "work.reassign",
        "work.submit",
        "work.approve",
        "work.close",
        "documents.view",
        "documents.upload",
        "documents.review",
        "documents.approve",
        "quality.review",
        "reports.view",
        "reports.export",
        "audit.view",
    ),
    "SENIOR_CONSULTANT": (
        "clients.view",
        "work.view",
        "work.create",
        "work.submit",
        "documents.view",
        "documents.upload",
        "documents.review",
        "reports.view",
    ),
    "CONSULTANT": (
        "clients.view",
        "work.view",
        "work.create",
        "work.submit",
        "documents.view",
        "documents.upload",
    ),
    "ARTICLE_ASSISTANT": (
        "clients.view",
        "work.view",
        "documents.view",
        "documents.upload",
    ),
    "ACCOUNTS": (
        "clients.view",
        "reports.view",
        "reports.export",
    ),
    "HR": (
        "employees.view",
        "employees.manage",
    ),
    "RECEPTION": (
        "clients.view",
        "clients.create",
        "clients.edit",
    ),
    "READ_ONLY": (
        "clients.view",
        "employees.view",
        "work.view",
        "documents.view",
        "reports.view",
    ),
}
