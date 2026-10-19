# Business Rules

> **Status:** Proposed rules for a simulated case study. Validate against organisational policy and applicable privacy, security, finance, and records obligations before implementation.

| Rule ID | Rule | Rationale / note |
|---|---|---|
| RULE-01 | Every asset record has one unique, non-recycled asset ID. | Enables traceability across lifecycle events. |
| RULE-02 | A record cannot enter Assigned without a custodian reference, assignment date, site, and acknowledgement. | Makes custody accountable. |
| RULE-03 | Return Pending requires a return due date and an accountable follow-up owner. | Supports follow-up and overdue reporting. |
| RULE-04 | A return is overdue only when the agreed business date is later than its due date. | The prototype uses date-only comparison, no holiday calendar. |
| RULE-05 | A device requiring sanitisation cannot transition to Disposed without a Passed result and sanitisation evidence reference. | Proposed preventative control; approval and evidence types need policy confirmation. |
| RULE-06 | Disposed records retain the disposition date, approval reference, and disposal evidence reference. | Enables audit and reconciliation. |
| RULE-07 | Lost / Stolen records require an incident reference and investigation owner in an operational implementation. | Incident handling is not fully represented by the sample schema. |
| RULE-08 | Status changes create an immutable event with actor/role, timestamp, old/new status, and reason. | The CSV is a snapshot and cannot provide this history. |
| RULE-09 | Dashboard measures use the documented as-of date, filter scope, inclusion/exclusion rules, and refresh context. | Reduces ambiguity and metric drift. |
| RULE-10 | Routine reports use minimised custodian references and do not expose unnecessary direct identifiers. | Subject to privacy/security design and access control. |
| RULE-11 | A blank field is distinguishable from “not applicable” and “not yet assessed” in a production data model. | Avoids conflating missing evidence with a valid non-required state. |
| RULE-12 | No sample flag alone establishes a policy breach; a person must review source and context. | Prevents false-positive automation from being treated as a finding. |

## Prototype-specific metric rules

The dashboard's fixed cut-off is **2026-10-19**:

- Overdue return: status is Return Pending, due date is present and earlier than cut-off.
- Active expired warranty: warranty end precedes cut-off and status is neither Disposed nor Lost / Stolen.
- Sanitisation review prompt: status is Ready for Disposal or Disposed, sanitisation is required, and result is not Passed or evidence reference is blank.

See [`../analysis/metric-definitions.md`](../analysis/metric-definitions.md) for the full metric contract.
