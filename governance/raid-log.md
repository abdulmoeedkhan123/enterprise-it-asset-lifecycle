# RAID Log

> **Illustrative simulation:** Risks, assumptions, issues, and dependencies below are scenario examples for portfolio discussion, not a live project log. Owners are role placeholders. Ratings use a simple 1-5 likelihood and impact scale and need calibration.

## Risks

| ID | Risk | Likelihood | Impact | Response / control | Proposed owner | Status |
|---|---|---:|---:|---|---|---|
| R-01 | Duplicate or stale source records undermine trust in the register. | 4 | 4 | Profile and reconcile identifiers; assign steward; establish exception process before migration. | Asset Manager | Open - illustrative |
| R-02 | Disposal is recorded without complete sanitisation evidence. | 3 | 5 | Enforce transition gate, independent approval where policy requires, and evidence audit. | InfoSec / Asset Manager | Open - illustrative |
| R-03 | Users continue side spreadsheets, creating parallel versions of truth. | 3 | 4 | Co-design workflow, minimise capture effort, train roles, measure adoption and duplicates. | Service Desk lead | Open - illustrative |
| R-04 | Employee information is exposed beyond operational need. | 2 | 5 | Minimise attributes, apply role access, retention, audit, and privacy review. | Privacy / Security | Open - illustrative |
| R-05 | Warranty/overdue metrics differ across teams due to inconsistent rules. | 3 | 3 | Publish data contract, cut-off, exclusions, business calendar, and metric owner. | Product owner | Open - illustrative |

## Assumptions

| ID | Assumption | Validation | Owner |
|---|---|---|---|
| A-01 | A minimum register can be standardised before platform selection. | Sponsor and architecture workshop | Sponsor |
| A-02 | A minimised custodian reference is available from an approved source. | HR/privacy mapping | Privacy / HR |
| A-03 | Required sanitisation evidence can be referenced without storing unnecessary sensitive content in the register. | InfoSec / Records review | InfoSec |

## Issues

| ID | Issue | Impact | Action | Owner | Status |
|---|---|---|---|---|---|
| I-01 | No source-system authority or integration feasibility has been confirmed in this portfolio exercise. | Prevents validated migration/integration design. | Treat each source as a discovery hypothesis; request profiling and system-owner review in a real engagement. | BA / architecture | Open - simulation |
| I-02 | Synthetic CSV is a snapshot and has no lifecycle event history. | Cannot calculate cycle time or prove audit trail. | Model event history as a requirement; use event-level test data in implementation. | Data / process owner | Open - simulation |

## Dependencies

| ID | Dependency | Needed for | Owner | Status |
|---|---|---|---|---|
| D-01 | Approved asset and disposal policy | Status definitions and controls | Asset Manager | Unconfirmed |
| D-02 | InfoSec sanitisation standard and evidence rules | Disposition control | InfoSec | Unconfirmed |
| D-03 | Privacy, access and records-retention decisions | Data model and role design | Privacy / Records | Unconfirmed |
| D-04 | Procurement, HR, endpoint and finance source ownership | Reconciliation and integration design | Business system owners | Unconfirmed |

## Rating guidance

Illustrative score = likelihood × impact, with 1-4 Low, 5-9 Medium, 10-16 High, and 17-25 Critical for prioritisation discussion only. A real RAID review should include due date, trigger, residual exposure, action status, and escalation path.
