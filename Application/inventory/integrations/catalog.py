from __future__ import annotations

from typing import TypedDict


class IntegrationOption(TypedDict):
    name: str
    category: str
    availability: str
    protocol: str
    workflow: str
    data_direction: str
    notes: str


INTEGRATION_CATALOG: tuple[IntegrationOption, ...] = (
    {
        "name": "CSV asset import",
        "category": "Asset inventory",
        "availability": "Available",
        "protocol": "Versioned CSV schema; manual command",
        "workflow": "Load and reconcile asset inventory",
        "data_direction": "Source file -> application",
        "notes": (
            "Implemented with validation, quality profiling, transactional upsert, "
            "import history, and idempotent replay."
        ),
    },
    {
        "name": "SCIM 2.0 user status",
        "category": "Identity and access",
        "availability": "Available - generic connector",
        "protocol": "HTTPS SCIM GET /Users; bearer token",
        "workflow": "Create an asset-return review when a mapped identity is inactive",
        "data_direction": "Identity provider -> application",
        "notes": (
            "Reads only id and active. Requires a provider SCIM endpoint that supports "
            "the implemented list/pagination contract and a manually reviewed identity "
            "mapping. Provider-specific authentication and filters may need an adapter."
        ),
    },
    {
        "name": "Microsoft Entra ID / Microsoft Graph",
        "category": "Identity and access",
        "availability": "Adapter required",
        "protocol": "Microsoft Graph API; OAuth 2.0",
        "workflow": "Read approved identity lifecycle signals",
        "data_direction": "Read-only source -> application review queue",
        "notes": (
            "Not a direct SCIM connector. Requires a Graph adapter, delegated or "
            "application permission review, consent, pagination, and sandbox tests."
        ),
    },
    {
        "name": "Okta",
        "category": "Identity and access",
        "availability": "Adapter required",
        "protocol": "Okta Users API or verified SCIM endpoint",
        "workflow": "Read approved identity lifecycle signals",
        "data_direction": "Read-only source -> application review queue",
        "notes": (
            "The generic SCIM connector may be reusable only when the tenant exposes "
            "the required SCIM list endpoint and response contract; otherwise implement "
            "and test an Okta API adapter."
        ),
    },
    {
        "name": "Active Directory / LDAP",
        "category": "Identity and access",
        "availability": "Adapter required",
        "protocol": "LDAP/LDAPS or directory export",
        "workflow": "Read approved account status attributes",
        "data_direction": "Read-only source -> application review queue",
        "notes": (
            "Requires directory-specific attribute mapping, TLS configuration, "
            "least-privilege bind access, and an approved directory test environment."
        ),
    },
    {
        "name": "ServiceNow",
        "category": "IT service management",
        "availability": "Adapter required",
        "protocol": "ServiceNow REST API / approved event mechanism",
        "workflow": "Create or reconcile service requests and fulfilment tasks",
        "data_direction": "Not implemented; direction to be agreed per workflow",
        "notes": (
            "Requires a table/API contract, OAuth or managed credential design, "
            "idempotency key, status mapping, and sandbox approval."
        ),
    },
    {
        "name": "Jira Service Management",
        "category": "IT service management",
        "availability": "Adapter required",
        "protocol": "Jira Service Management REST API / webhooks",
        "workflow": "Create or reconcile service requests and approvals",
        "data_direction": "Not implemented; direction to be agreed per workflow",
        "notes": (
            "Requires project/request-type mapping, scoped authentication, webhook "
            "verification, idempotency, and sandbox tests."
        ),
    },
    {
        "name": "Microsoft Intune",
        "category": "Endpoint management",
        "availability": "Implemented - read-only sync",
        "protocol": "Microsoft Graph device-management APIs",
        "workflow": "Enrich inventory with approved managed-device attributes",
        "data_direction": "Read-only source -> application",
        "notes": (
            "Read-only managed-device sync is implemented through Microsoft Graph. "
            "Requires tenant approval for the least-privilege "
            "DeviceManagementManagedDevices.Read.All application permission, app "
            "credentials, and sandbox verification. Matching uses only unique exact "
            "serial references; duplicates and unmatched records need review."
        ),
    },
    {
        "name": "Jamf Pro",
        "category": "Endpoint management",
        "availability": "Adapter required",
        "protocol": "Jamf Pro API",
        "workflow": "Enrich inventory with approved managed-device attributes",
        "data_direction": "Read-only source -> application",
        "notes": (
            "Requires tenant-specific API version and authentication review, device "
            "identifier mapping, and sandbox validation."
        ),
    },
    {
        "name": "Blancco",
        "category": "IT asset disposition",
        "availability": "Blocked pending vendor contract",
        "protocol": "Vendor API not yet confirmed",
        "workflow": "Associate sanitisation or erasure evidence with an asset",
        "data_direction": "Not implemented",
        "notes": (
            "No endpoint, authentication scheme, or payload is assumed. Implement only "
            "after official API documentation, an approved sandbox, and a confirmed "
            "evidence-matching contract are provided."
        ),
    },
    {
        "name": "SFTP / scheduled file exchange",
        "category": "Data exchange",
        "availability": "Adapter required",
        "protocol": "SFTP with agreed CSV schema",
        "workflow": "Batch inventory feeds and reconciliation reports",
        "data_direction": "Not implemented; source and destination must be agreed",
        "notes": (
            "The CSV import currently accepts a local file only. Secure transfer, "
            "scheduling, archival, acknowledgement, and retry handling are not built."
        ),
    },
)
