# Business Requirements Document (BRD)

> **Document status:** Fictional portfolio artifact for analysis practice; not approved by a real organisation.

## 1. Purpose

Define the business need and outcomes for a controlled end-user IT asset lifecycle across a fictional multi-site organisation. This BRD provides a business-level baseline for the detailed requirements in [`../requirements/requirements.md`](../requirements/requirements.md).

## 2. Background and problem

The scenario assumes asset information is fragmented across spreadsheets and email-based hand-offs. IT, line managers, Finance, and Information Security may not share a consistent view of asset ownership, status, return commitments, warranty, and end-of-life evidence.

This creates a decision and control problem: authorised staff need to find the current status and accountable owner of an asset, identify records requiring follow-up, and confirm required sanitisation and evidence before disposition. These are fictional discovery hypotheses, not findings from interviews, audit, or a real organisation.

## 3. Business outcomes

| ID | Outcome | Proposed measure | Target approach |
|---|---|---|---|
| BO-01 | Improve asset-record completeness | Percentage of active records satisfying the agreed mandatory-field profile | Propose ≥98%; validate baseline, feasibility, and ownership before approval |
| BO-02 | Make return follow-up actionable | Percentage of overdue returns reviewed with accountable owner and next action | Propose weekly review of 100%; agree business calendar and escalation |
| BO-03 | Enforce disposal evidence controls | Required-sanitisation disposals with Passed result and evidence reference before closure | Proposed 100%; confirm policy and evidence types with InfoSec |
| BO-04 | Improve reporting consistency | Measures with approved definitions, filters, and as-of date | All published measures have definitions and owner |
| BO-05 | Understand reconciliation effort | Median time to answer an agreed asset-location query | Establish a real baseline before setting a reduction target |

These are proposed success measures, not measured benefits. No achieved value, return on investment, or financial saving is asserted.

## 4. Business requirements

| ID | Business requirement | Priority |
|---|---|---|
| BR-01 | Provide a consistent, reviewable view of in-scope assets and lifecycle state. | Must |
| BR-02 | Establish accountable ownership for asset assignment, return, and follow-up. | Must |
| BR-03 | Make sanitisation and disposal evidence a controlled prerequisite where policy requires it. | Must |
| BR-04 | Provide operational measures with agreed definitions and an explicit reporting date. | Must |
| BR-05 | Minimise personal and sensitive information and govern its access and retention. | Must |
| BR-06 | Support reconciliation between operational asset records and relevant procurement/finance data. | Should |

## 5. Scope summary

### In scope

- End-user laptops, desktops, phones, tablets, and monitors.
- Receipt, registration, assignment, return, repair, sanitisation, and disposition.
- Minimum register, status definitions, data stewardship, audit events, and evidence references.
- Return and warranty exception reporting plus a read-only dashboard concept.
- Proposed UAT, data validation, and governance decisions needed before implementation.

### Out of scope

- Production platform selection, configuration, implementation, or system integration.
- Procurement sourcing, contract management, depreciation, or accounting policy.
- Endpoint security configuration or detailed sanitisation technology/method selection.
- Live employee details, genuine serials, or real company records.
- Claims of actual cost, compliance, or service improvement.

See the [scope and assumptions register](./scope-assumptions.md) for detailed boundaries and open discovery questions.

## 6. Constraints, dependencies, and assumptions

- The case study uses generated synthetic data and a fixed demonstration report date.
- A real implementation depends on an accountable asset owner, data stewards, and process owners.
- Procurement, HR, identity, endpoint, and finance source-of-truth ownership is unknown.
- Privacy, access control, retention, record evidence, and disposal policy require specialist review.
- Proposed targets require baseline data and business approval.

## 7. Options and recommendation

| Option | Summary | Assessment |
|---|---|---|
| 1. Continue current approach | Keep disconnected records, improve guidance only | Low immediate cost; core reconciliation and control risks remain in the scenario |
| 2. Standardise minimum data and operating controls | Define statuses, ownership, evidence, and exception views using feasible existing tools | Recommended first discovery/design increment; reduces ambiguity but relies on stewardship |
| 3. Introduce dedicated asset platform | Select/configure a platform and integrate authoritative sources | Potentially stronger workflow/audit; requires discovery, procurement, funding, and delivery planning |

**Portfolio recommendation:** Develop Option 2 as a bounded pilot proposal and assess Option 3 only after data profiling, user research, integration feasibility, security/privacy review, and a total-cost assessment. This is a simulated recommendation, not an investment approval.

## 8. Governance and decision rights

The fictional IT Asset Manager is proposed as business owner. Service Desk, Procurement, Finance, Information Security, Privacy/Records, and line-manager representatives are consulted for their relevant policies and hand-offs. Actual decision rights, role separation, and approval thresholds remain to be agreed.

## 9. Acceptance at business level

The business case can proceed to implementation planning only if:

1. Process owners agree status definitions and allowed transitions.
2. Required data, system of record, data owners, and reconciliation process are approved.
3. InfoSec and Records/Privacy approve sanitisation evidence, access, retention, and audit controls.
4. Business owners approve metric definitions and establish baselines for outcome claims.
5. A pilot scope, support model, risk owner, and operational acceptance criteria are agreed.

## 10. Approval record

No real approval is represented. For an actual initiative, record approver names/roles, version, decision date, conditions, and linked evidence in the organisation's controlled repository.
