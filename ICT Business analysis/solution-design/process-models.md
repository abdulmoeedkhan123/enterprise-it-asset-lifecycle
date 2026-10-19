# Proposed Lifecycle Process Models

> **Model status:** These are proposed future-state models for a fictional portfolio scenario. They are not evidence of an implemented or approved workflow.

## 1. AS-IS (assumed scenario)

> **Validation needed:** No real current-state interviews or observations were performed. This model visualises the scenario hypothesis of disconnected records and informal hand-offs; replace it with validated evidence in a real engagement.

```mermaid
flowchart LR
    A[Purchase or device event] --> B[Team updates local spreadsheet]
    B --> C{Which copy is current?}
    C -- Unclear --> D[Email or message another team]
    D --> E[Manually reconcile status, owner or dates]
    E --> F[Update one or more records]
    C -- Assumed --> F
    F --> G{Return, repair or disposal event?}
    G -- Return / repair --> H[Follow up through email and local notes]
    H --> B
    G -- Disposal --> I[Evidence stored separately or referenced manually]
    I --> B
    B --> J[Manually assemble operational view]
    J --> K[Investigate inconsistent or missing values]
```

**Hypothesised friction points:** unclear source of truth, duplicate updates, reliance on individual follow-up, inconsistent definitions, and evidence references separated from lifecycle status. These are assumptions to validate, not confirmed process findings.

## 2. TO-BE: receive and assign an asset

```mermaid
flowchart TD
    A[Procurement confirms receipt] --> B[Asset steward creates or matches unique asset record]
    B --> C{Required fields complete and ID unique?}
    C -- No --> D[Return record for correction]
    D --> B
    C -- Yes --> E[Set status to In Stock]
    E --> F{Assignment approved and custodian known?}
    F -- No --> G[Keep in stock; record owner and location]
    F -- Yes --> H[Record custodian, site, assignment date and acknowledgement]
    H --> I[Set status to Assigned]
    I --> J[Write lifecycle event and update reporting view]
```

**Control points:** Unique ID before assignment; required fields before a status change; custodian acknowledgement; auditable event with actor, timestamp, and reason.

## 3. TO-BE: return and disposition

```mermaid
flowchart TD
    A[Leaver or asset change is notified] --> B[Manager or HR confirms affected custodian]
    B --> C[Service desk identifies assigned assets]
    C --> D[Set Return Pending and record due date]
    D --> E{Returned by due date?}
    E -- No --> F[Create overdue follow-up and notify accountable owner]
    F --> E
    E -- Yes --> G[Record receipt, date and condition]
    G --> H{Repair or reissue?}
    H -- Repair --> I[Set In Repair; record work outcome]
    I --> J{Repair complete?}
    J -- No --> I
    J -- Yes --> K[Quality check and return to In Stock]
    H -- Reissue --> L[Reassign using assignment process]
    H -- Retire --> M{Sanitisation required?}
    M -- Yes --> N[Complete approved sanitisation and record result]
    N --> O{Result Passed and evidence reference present?}
    O -- No --> P[Hold disposition; remediate or escalate]
    P --> N
    O -- Yes --> Q[Authorised approval and disposal evidence]
    M -- No --> Q
    Q --> R[Set Disposed and close lifecycle event]
```

**Control points:** Return due date and escalation owner; receipt and condition capture; sanitisation gate; separate approval/evidence before final disposition.

## 4. TO-BE role hand-offs (conceptual swimlane)

```mermaid
sequenceDiagram
    participant M as Manager or HR
    participant SD as Service Desk
    participant C as Custodian
    participant IS as Information Security
    participant AS as Asset Steward
    M->>SD: Notify leaver or asset change
    SD->>AS: Request assigned asset list
    AS-->>SD: Return asset IDs and custody references
    SD->>C: Confirm return instructions and due date
    C-->>SD: Return equipment and confirm hand-off
    SD->>AS: Record receipt, condition, and next state
    AS->>IS: Request sanitisation approval/evidence when required
    IS-->>AS: Record outcome and evidence reference
    AS->>AS: Validate control gate, approval, and disposition evidence
    AS-->>SD: Confirm lifecycle closure and update report
```

## State-transition guardrails

| From | To | Required information / guardrail |
|---|---|---|
| New record | In Stock | Unique ID, asset type, source, receipt date, site, and owner |
| In Stock | Assigned | Custodian reference, assignment date, site, and acknowledgement |
| Assigned | Return Pending | Return trigger, accountable owner, and due date |
| Return Pending | In Repair | Receipt date and condition |
| Return Pending | In Stock | Receipt, condition, and quality/reissue check |
| In Repair | In Stock | Repair outcome and quality check |
| In Stock / In Repair | Ready for Disposal | Retirement reason and sanitisation requirement decision |
| Ready for Disposal | Disposed | Required sanitisation Passed + evidence, approval, and disposal evidence |
| Any active state | Lost / Stolen | Incident reference, reporting owner, and investigation status |

The exact allowed transitions, approvals, and required attributes would be confirmed during implementation design. The sample CSV is a point-in-time snapshot and does not itself represent a validated transition history.

## Responsibility summary (RACI proposal)

`R` = Responsible, `A` = Accountable, `C` = Consulted, `I` = Informed.

| Activity | Asset Manager | Service Desk | Manager / HR | Custodian | InfoSec | Finance |
|---|---:|---:|---:|---:|---:|---:|
| Define lifecycle policy and statuses | A/R | C | C | I | C | C |
| Capture receipt and assignment | A | R | I | R | I | I |
| Initiate return and follow-up | A | R | R | R | I | I |
| Set sanitisation control | C | I | I | I | A/R | I |
| Approve and evidence disposal | A/R | C | I | I | C | C |
| Reconcile operational and financial views | R | C | I | I | I | A/R |

This is a discussion model, not an agreed governance or segregation-of-duties decision.
