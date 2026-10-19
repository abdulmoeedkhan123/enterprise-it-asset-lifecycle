# Acceptance Criteria and Traceability

> **Test context:** These are proposed acceptance criteria for the fictional workflow and a read-only dashboard prototype. They are not sign-off for a production system.

## Given / When / Then criteria

### AC-01 - Minimum asset record and unique identity (FR-01)

- **Given** an asset receipt is being recorded,
- **When** the record is saved,
- **Then** it has a unique asset ID, asset type, site, lifecycle status, purchase date, warranty end, and last-updated date,
- **And** a duplicate ID or missing mandatory field is rejected with a clear correction message.

### AC-02 - Assignment accountability (FR-02)

- **Given** an In Stock asset is approved for assignment,
- **When** the service desk assigns it,
- **Then** the custodian reference, site, assignment date, and acknowledgement are recorded before status becomes Assigned.

### AC-03 - Return initiation (FR-03)

- **Given** an assigned asset must be returned,
- **When** the return is initiated,
- **Then** Return Pending, the due date, accountable owner, and follow-up action are recorded.

### AC-04 - Overdue identification (FR-04)

- **Given** an asset is Return Pending and the agreed reporting date is 2026-10-19,
- **When** its due date is before 2026-10-19,
- **Then** it is flagged overdue in the operational view,
- **And** a return due on 2026-10-19 is not counted overdue by this date-only demonstration rule.

### AC-05 - Sanitisation disposition gate (FR-05)

- **Given** an asset requires sanitisation,
- **When** a user attempts to move it to Disposed,
- **Then** the transition is allowed only when the result is Passed and a sanitisation evidence reference is recorded,
- **And** otherwise the transition is blocked and an actionable reason is displayed.

### AC-06 - Lifecycle event audit (FR-06)

- **Given** an authorised user changes lifecycle status,
- **When** the transition is saved,
- **Then** an event records timestamp, acting role, previous state, new state, and reason.

### AC-07 - Site and status filters (FR-07)

- **Given** the dashboard has loaded the sample snapshot,
- **When** a user selects a site or status,
- **Then** the KPI cards, charts, review rows, and visible record count reflect the same combined filters.

### AC-08 - KPI calculation and publication (FR-08, FR-10)

- **Given** the dashboard uses the synthetic CSV and the fixed 2026-10-19 reporting date,
- **When** it renders the indicators,
- **Then** Assets in View, Assigned, Overdue Returns, and Active Expired Warranty use the definitions in `analysis/metric-definitions.md`,
- **And** the report date and simulated-data notice are visible.

### AC-09 - Example follow-up flags (FR-09)

- **Given** a row satisfies a documented review-queue rule,
- **When** the dashboard is filtered to include that row,
- **Then** the asset ID, site, status, and review prompt are visible,
- **And** the flag is presented as a prompt for human review, not a confirmed incident.

### AC-10 - Minimum data and privacy (BR-05, NFR-03)

- **Given** the sample asset data is displayed,
- **When** a user reviews or exports the sample,
- **Then** it contains synthetic IDs and no real names, email addresses, phone numbers, or street addresses.
- **Production verification required:** role-based access, audit logging, retention, and privacy controls are not implemented in this prototype.

### AC-11 - Search sample (FR-11)

- **Given** the sample snapshot is loaded,
- **When** a user enters an asset ID, site, or custodian reference,
- **Then** the KPI cards, distributions, review queue, and result count show only matching records,
- **And** the search is case-insensitive.

### AC-12 - Data-load failure is explicit (FR-12)

- **Given** the CSV is unavailable or contains an invalid header or row structure,
- **When** the Python dashboard server attempts to render the page,
- **Then** it shows a visible error and does not display KPI values as though the load succeeded.

### AC-13 - Accessible controls and empty results (FR-13)

- **Given** a user navigates the dashboard without a pointer,
- **When** they use the filters, search, and reset control,
- **Then** controls have programmatic labels, visible keyboard focus, and operable actions,
- **And** a filter combination with no results communicates the empty state without breaking the page.

## Requirements traceability

| Requirement | Acceptance criterion | Proposed verification artifact |
|---|---|---|
| FR-01 | AC-01 | UAT-01; `analysis/validate_assets.py` |
| FR-02 | AC-02 | UAT-02 |
| FR-03 | AC-03 | UAT-03 |
| FR-04 | AC-04 | UAT-04; metric definition and query |
| FR-05 | AC-05 | UAT-05 |
| FR-06 | AC-06 | UAT-06 |
| FR-07 | AC-07 | UAT-07 |
| FR-08, FR-10 | AC-08 | UAT-08; dashboard metric review |
| FR-09 | AC-09 | UAT-09 |
| BR-05, NFR-03 | AC-10 | UAT-10; privacy/security review before production |
| FR-11 | AC-11 | UAT-11; dashboard interaction check |
| FR-12 | AC-12 | UAT-12; controlled missing/invalid sample test |
| FR-13, NFR-02 | AC-13 | UAT-13; keyboard/accessibility review |
