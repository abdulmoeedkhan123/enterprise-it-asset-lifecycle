# Requirements and User Stories

> **Status:** Portfolio analysis artifacts for a fictional scenario. These requirements have not been approved by a real organisation.

## Requirement conventions

- `BR` identifies a business requirement; `FR` a functional requirement; `NFR` a non-functional requirement.
- Priority uses MoSCoW: **Must**, **Should**, or **Could** for the first proposed increment.
- Acceptance criteria are traceable in [`../uat/acceptance-criteria.md`](../uat/acceptance-criteria.md).
- “Asset” means an in-scope end-user device represented by a unique asset record.

## Business requirements

| ID | Requirement | Priority | Rationale |
|---|---|---|---|
| BR-01 | The organisation needs a reliable view of in-scope assets and their lifecycle state. | Must | Supports operational oversight and reconciliation. |
| BR-02 | Asset assignment and return must have clear accountability. | Must | Reduces ambiguity when equipment changes hands. |
| BR-03 | Disposal of devices requiring sanitisation must be supported by approved evidence. | Must | Makes the control point explicit and reviewable. |
| BR-04 | Operational reporting must use agreed definitions and a visible as-of date. | Must | Prevents misleading comparisons and stale numbers. |
| BR-05 | Asset and evidence data must be limited to the minimum needed for the workflow. | Must | Reduces privacy and information-management exposure. |

## Functional requirements

| ID | Requirement | Priority | Acceptance reference |
|---|---|---|---|
| FR-01 | The register shall maintain a unique asset ID and the agreed minimum asset attributes: type, manufacturer/model, site, status, purchase date, warranty end, and last-updated date. | Must | AC-01 |
| FR-02 | The register shall record a custodian reference and assignment date for an assigned asset. | Must | AC-02 |
| FR-03 | The workflow shall record return due date, return receipt, condition, and next action for a return-pending asset. | Must | AC-03 |
| FR-04 | The workflow shall identify overdue returns using an agreed business date and the documented overdue rule. | Must | AC-04 |
| FR-05 | The workflow shall prevent transition to Disposed when sanitisation is required unless a passed result and evidence reference are recorded. | Must | AC-05 |
| FR-06 | The solution shall record lifecycle changes with timestamp, acting role, previous state, new state, and reason. | Should | AC-06 |
| FR-07 | An authorised user shall be able to filter the operational view by site and lifecycle status. | Must | AC-07 |
| FR-08 | The operational view shall display asset count, assigned count, overdue returns, and active expired-warranty count using the published definitions. | Must | AC-08 |
| FR-09 | A user shall be able to identify records requiring follow-up, including missing assignment data and incomplete disposal control information. | Should | AC-09 |
| FR-10 | The report shall display its reporting date and data-refresh context. | Must | AC-10 |
| FR-11 | A user shall be able to search the visible sample by asset ID, site, or custodian reference. | Should | AC-11 |
| FR-12 | If the data source cannot be loaded or has invalid structure, the dashboard shall show an explicit error and not present success-shaped KPI values. | Must | AC-12 |
| FR-13 | Dashboard controls shall be keyboard operable, labelled, and provide visible focus and useful empty-result feedback. | Must | AC-13 |

## Business rules

| ID | Rule |
|---|---|
| RULE-01 | Each asset has a unique, non-recycled asset ID. |
| RULE-02 | An asset cannot become Assigned without a custodian reference, assignment date, site, and acknowledgement. |
| RULE-03 | Return Pending requires a due date and accountable follow-up owner. |
| RULE-04 | A return is overdue only after its due date under the agreed business calendar; the prototype uses date-only comparison. |
| RULE-05 | When sanitisation is required, transition to Disposed is blocked unless result is Passed and sanitisation evidence is recorded. |
| RULE-06 | Disposition records retain approval and disposal evidence references. |
| RULE-07 | Lifecycle state changes create an auditable event with actor, timestamp, previous/new state, and reason. |
| RULE-08 | Reported measures publish definition, scope, as-of date, exclusions, and refresh context. |
| RULE-09 | A dashboard review flag is an investigation prompt and is not by itself proof of a policy breach. |
| RULE-10 | Use the minimum custodian identifier necessary; govern access and retention under approved policy. |

## Non-functional requirements

| ID | Requirement | Priority | Proposed verification |
|---|---|---|---|
| NFR-01 | The reporting view should load within 3 seconds for a 10,000-row dataset on the agreed standard workstation and network. | Should | Measure against a defined test environment; the 1,200-row prototype is not a 10,000-row performance test. |
| NFR-02 | The experience shall support keyboard navigation, visible focus, semantic labels, and readable contrast. | Must | Accessibility review against WCAG 2.2 AA as a target; formal conformance is not claimed. |
| NFR-03 | Access to identifiable asset/custodian data shall be role-based and auditable. | Must | Security design and access-control test before production; not implemented in prototype. |
| NFR-04 | The system shall retain lifecycle and evidence events according to an approved records schedule. | Must | Records-management review and retention test before production. |
| NFR-05 | The reporting view shall define how a reporting date, timezone, and stale data are handled. | Must | Verify published metric and refresh rules. |
| NFR-06 | The solution shall support export or integration only through approved, access-controlled channels. | Should | Interface/security review; no export or integration is implemented here. |

## User stories

### US-01: Record an assignment

As a **service desk analyst**, I want to assign an asset to a custodian and record the assignment, so that responsibility and location can be reviewed later.

**Acceptance:** An assigned record has a unique asset ID, custodian reference, assignment date, site, and status; incomplete mandatory information is rejected with a clear message.

### US-02: Follow up a return

As an **asset manager**, I want a list of overdue returns with due date and owner, so that I can coordinate follow-up rather than reconcile emails manually.

**Acceptance:** The overdue rule is reproducible for the report date, and each returned row exposes asset ID, due date, site, and recorded custodian reference.

### US-03: Control disposition

As an **information security reviewer**, I want sanitisation and evidence checks before disposition, so that a device requiring sanitisation is not marked disposed without the required record.

**Acceptance:** A required sanitisation must have a Passed result and evidence reference before status can change to Disposed.

### US-04: Review portfolio health

As an **IT asset manager**, I want to filter a defined dashboard by site and lifecycle status, so that I can focus an operational review on relevant records.

**Acceptance:** All cards, charts, and review rows respect the selected filters and show the report date and metric definitions.

### US-05: Reconcile warranty exposure

As a **finance partner**, I want an agreed count of active assets with an expired warranty, so that follow-up can be prioritised with IT.

**Acceptance:** Disposed and Lost / Stolen records are excluded from this demonstration active-warranty measure; all other inclusions and the as-of date are documented.

## Open questions for a real discovery

1. Which system is authoritative for asset identity, assignment, purchase, warranty, and leaver events?
2. What does “active” mean for finance, IT operations, and warranty reporting?
3. Who can approve a disposal, and which sanitisation methods and evidence types are acceptable?
4. What escalation interval and business calendar define overdue returns?
5. What are the access, retention, and privacy requirements for custodian and evidence data?
6. Which target platform, integration patterns, and service-level objectives are feasible?
