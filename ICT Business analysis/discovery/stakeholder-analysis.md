# Stakeholder Analysis

> **Fictional portfolio model:** Roles are scenario personas. No real stakeholders have been interviewed or assigned accountability.

## Stakeholder register

| Stakeholder / persona | Interest | Influence | Information need | Engagement approach |
|---|---|---:|---|---|
| IT Asset Manager / proposed product owner | Asset control, policy, lifecycle reporting | High | Scope, exceptions, ownership, control compliance | Confirm policy, decisions, metric ownership, and prioritisation |
| Service Desk lead and analysts | Feasible intake, assignment, repair, return hand-offs | High | Required fields, queue work, status transitions, rework | Workflow walkthroughs, field validation, prototype review |
| Procurement | Receipt and purchase/warranty data | Medium | Receipt event, supplier references, warranty source | Map source fields and receipt hand-off |
| Finance / fixed-asset representative | Reconciliation and financial population | High | Asset identity, lifecycle boundary, reconciliation cadence | Agree population definitions and reconciliation controls |
| Information Security | Sanitisation, evidence, incident links | High | Gate conditions, evidence type, approval, exceptions | Validate policy and disposition scenarios |
| Privacy / Records representative | Data minimisation, access, retention | High | Custodian identifiers, evidence retention, audit scope | Privacy and records review before design approval |
| Line managers / HR liaison | Leaver and mover notifications, return follow-up | Medium | Affected assets, ownership, dates, escalation | Validate trigger, responsibilities, and communications |
| Employees / custodians | Assignment acknowledgement and return | Medium | What equipment, due date, return method, support contact | Usability feedback and plain-language guidance |
| Senior sponsor | Outcome, risk, funding, delivery option | High | Business case, baseline, costs, risks, decision gates | Decision briefing at discovery and pilot gates |

## Power-interest view

|  | Lower interest | Higher interest |
|---|---|---|
| **Higher influence** | Keep satisfied: sponsor between gates; Privacy/Records on policy decisions | Manage closely: asset owner, Service Desk lead, Finance, InfoSec |
| **Lower influence** | Monitor: adjacent support groups, pending confirmation | Keep informed / consult: custodians, line managers, Procurement |

This is a starting hypothesis. Confirm stakeholder availability, influence, and representation during real discovery.

## Workshop and interview plan

| Session | Participants | Questions / output |
|---|---|---|
| Current-state walkthrough | Asset Manager, Service Desk, Procurement | Trigger-to-close workflow, systems, manual hand-offs, exceptions |
| Data and reconciliation review | Finance, Asset Manager, Procurement | System of record, identity matching, mandatory fields, reconciliation rules |
| Control and disposal review | InfoSec, Privacy/Records, Asset Manager | Sanitisation standard, evidence, approval, retention, exception handling |
| Return/JML hand-off | HR liaison, line managers, Service Desk | Notification timing, ownership, due date, escalation and employee communications |
| Dashboard validation | Operations, Finance, sponsor | Decision questions, metric definitions, filters, data freshness |

## Decision and communication model

Keep a decision log with decision ID, question, options, decision owner, consulted roles, date, rationale, downstream requirement/process changes, and review trigger. Escalate unresolved privacy, security, financial-boundary, and policy decisions before implementation planning.
