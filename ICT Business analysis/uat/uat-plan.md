# User Acceptance Test Plan

> **Test status:** This is a proposed plan for a fictional case study. No real system or users are available here; the 13 scenarios in [`test-cases.csv`](./test-cases.csv) are all marked **Not run - proposed scenario**.

## Purpose and objectives

Validate that a future implementation meets agreed lifecycle, data-quality, control, reporting, usability, and privacy requirements before pilot/release. The static portfolio dashboard can be smoke-tested for demonstration behavior, but cannot prove backend workflow, access control, audit retention, or operational readiness.

## Scope

- Asset identity and mandatory data validation.
- Assignment, return, overdue follow-up, audit events, and sanitisation/disposition control.
- Dashboard filter/search behavior, measures, reporting context, error handling, and empty states.
- Data minimisation and production access-control design review.

## Roles

| Role | Proposed responsibility |
|---|---|
| Business/product owner | Accepts business outcomes and outstanding risks |
| Process owner / SME | Confirms process behavior and operational fit |
| UAT coordinator | Prepares environment, test data, execution record, and defect triage |
| Tester / representative user | Executes agreed scenarios and captures evidence |
| Technical owner | Supports environment, defect analysis, access and release readiness |
| Security/privacy/records reviewers | Review relevant controls and evidence requirements |

## Entry criteria

- Approved scope, requirements, business rules, and UAT-ready build/environment.
- Approved test data and access roles; no unapproved production personal data.
- Metric definitions, report date/timezone, and expected output reconciled.
- Testers briefed; evidence and defect-recording location available.
- Critical dependencies and known limitations documented.

## Exit and sign-off criteria

- All agreed Must acceptance criteria executed with evidence.
- No open critical/high severity defects unless explicitly accepted by an accountable owner.
- Lower-severity defects have owners, target dates, and documented workarounds or acceptance.
- Privacy, security, accessibility, operational support, and data reconciliation approvals are recorded as required.
- Business owner signs off with environment/build, execution dates, limitations, and residual risks.

No sign-off is asserted in this portfolio.

## Execution and defect handling

For each case, record tester role, environment/build, preconditions, actual result, pass/fail/blocked, evidence link, defect ID, and execution timestamp. Triage defects by impact, likelihood, affected users/data, workaround, and release risk. Retest the fix and run regression tests on related status transitions and measures.

See [`execution-notes.md`](./execution-notes.md) for explicit portfolio execution boundaries and [`illustrative-defect-log.md`](./illustrative-defect-log.md) for simulated defect-record examples.
