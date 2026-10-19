# Business Case: IT Asset Lifecycle Management

> **Fictional scenario:** This case is a simulated portfolio exercise. The organisation, people, asset records, workflow findings, and targets are invented; they are not evidence from a real client engagement.

## Executive summary

A fictional multi-site organisation relies on disconnected spreadsheets, email, and local team knowledge to manage end-user devices. Staff cannot consistently see the lifecycle state of each device, its accountable custodian, or the evidence required before disposal. The resulting gaps create avoidable effort and make routine operational questions difficult to answer.

This case proposes a controlled asset register and lifecycle workflow, supported by exception-focused reporting. The business analysis defines the problem, scope, requirements, process controls, measures, and acceptance approach. A static dashboard prototype demonstrates how a synthetic snapshot could support investigation; it is not an implemented operational solution.

## Business context

The fictional organisation has 1,200 reproducibly generated sample asset records across Melbourne, Sydney, Brisbane, and remote workers. The sample includes laptops, desktops, monitors, phones, and tablets in states such as In Stock, Assigned, Return Pending, In Repair, Sanitisation Pending, Ready for Disposal, Disposed, and Lost / Stolen.

The 1,200 rows are a generated demonstration dataset, not a verified estimate of an actual organisation's inventory or population. Generation uses a fixed seed and a fixed reporting cut-off so the analysis can be reproduced.

## Problem statement

Asset information and lifecycle hand-offs are assumed to be spread across disconnected records and informal communications. Without consistent ownership, mandatory transition data, and defined evidence controls:

- IT staff may spend time reconciling asset location, status, or custodian details.
- Managers may lack a dependable view of assets requiring return or follow-up.
- Finance and IT may not share a consistent view of active assets or warranty exposure.
- Disposal may proceed without a clear, auditable sanitisation and evidence trail.
- Reporting may depend on manual consolidation and inconsistent definitions.

These are scenario assumptions to be validated in a real discovery engagement, not findings from interviews or an audit.

## Objectives and proposed measures

| Objective | Proposed measure | Scenario target |
|---|---|---|
| Improve inventory completeness | Active asset records with populated asset ID, type, site, status, and custodian where assigned | At least 98% |
| Improve return follow-up | Return-pending assets past due with a recorded owner and next action | 100% reviewed weekly |
| Strengthen disposal controls | Disposal-ready assets requiring sanitisation with a passed result and evidence reference before disposition | 100% before disposal |
| Improve operational visibility | Dashboard metrics use documented definitions and a visible reporting date | All displayed metrics |
| Reduce avoidable reconciliation | Median time to answer a sample asset-location query | Establish baseline, then agree target |

Targets are proposed for discussion only. No baseline, achieved result, savings, or benefit realisation is claimed by this portfolio.

## Options considered

| Option | Summary | Advantages | Trade-offs |
|---|---|---|---|
| 1. Continue current approach | Retain spreadsheets and email with minor guidance | Lowest immediate change | Fragmentation and manual reconciliation remain |
| 2. Standardise controls and reporting | Agree a minimum register, lifecycle statuses, ownership, evidence rules, and exception dashboard | Practical first step; measurable; can build on existing tools | Depends on data stewardship and consistent update practices |
| 3. Implement a dedicated platform | Configure an enterprise asset-management capability and integrations | Potentially stronger workflow, audit, and integration support | Requires platform selection, funding, implementation, and change management |

**Recommended portfolio scenario:** Option 2 as a discovery and design increment, with Option 3 assessed only after data quality, user needs, integration constraints, and total cost are understood. This is an analytical recommendation for the fictional case, not an approved investment decision.

## Scope

### In scope

- End-user devices from procurement/receipt through assignment, return, repair, sanitisation, and disposal.
- Minimum asset-register fields, lifecycle definitions, role responsibilities, and data-quality controls.
- Return due-date and warranty review visibility.
- Disposal evidence and sanitisation control points.
- Read-only operational dashboard concept and acceptance criteria.

### Out of scope

- A live asset-management platform, integrations, identity management, or device-management configuration.
- Procurement sourcing, contract negotiation, depreciation policy, or accounting treatment.
- Mobile-device management, endpoint security, or technical sanitisation implementation.
- Real employee personal data or genuine serial numbers.
- Claims of measured cost savings, risk reduction, or production outcomes.

## Stakeholders and interests

| Stakeholder | Interest / responsibility in the scenario |
|---|---|
| IT Asset Manager | Accountable for asset policy, register quality, and lifecycle oversight |
| Service Desk Analyst | Records assignment, return, repair, and employee hand-offs |
| Employee / Custodian | Confirms receipt, care, and timely return of assigned equipment |
| Line Manager | Confirms leaver/mover events and supports overdue-return escalation |
| Information Security | Defines sanitisation control and evidence expectations |
| Finance | Uses reconciled asset population and approved disposal information |
| Procurement | Supplies purchase and warranty details at receipt |
| Privacy / Records representative | Advises on minimum personal data and retention needs |

## Assumptions, constraints, and dependencies

- A designated asset owner and named data stewards can be assigned.
- Employee references can use a minimised internal identifier rather than unnecessary personal details.
- The organisation will define an approved retention and evidence policy before implementation.
- Existing procurement, HR, identity, and device-management systems may hold relevant data; availability and integration feasibility are unknown.
- The sample report uses a fixed demonstration date of **19 October 2026** so overdue and warranty measures are reproducible.

## Key risks and mitigations

| Risk | Proposed mitigation |
|---|---|
| Low-quality migration data undermines trust | Profile, cleanse, reconcile, and approve records before cutover |
| Users bypass workflow during busy periods | Keep capture fields proportionate; provide role-based guidance and exception feedback |
| Disposal occurs without required evidence | Block or escalate the transition until the defined evidence control is satisfied |
| Dashboard metric differences create disputes | Publish metric definitions, filters, exclusions, and as-of date alongside every view |
| Personal or sensitive data is over-collected | Apply data minimisation, access controls, retention, and privacy review |
| Benefits are asserted without a baseline | Measure current state first; assign benefit owners and review dates |

## Indicative success criteria

The scenario is ready to progress to implementation planning only when process owners agree lifecycle definitions, data ownership, evidence rules, integration feasibility, and baseline measures. Any benefits should be measured after a pilot against an approved baseline; this repository does not claim that such a pilot occurred.
