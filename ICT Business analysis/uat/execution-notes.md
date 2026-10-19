# UAT Execution Notes

> **Truth in testing:** No production system, real end users, or formal user acceptance session exists for this fictional case study. The 13 scenarios in [`test-cases.csv`](./test-cases.csv) are proposed test scripts and are marked **Not run - proposed scenario**.

## Test scope

- Proposed workflow controls for assignment, return, sanitisation, and disposition.
- Dashboard filters, displayed measures, reporting date, and review prompts.
- Data-minimisation and production-control review points.

## Execution status

| Test group | Status | Evidence |
|---|---|---|
| UAT-01 to UAT-13 | Not run | No implementation or real user test environment is part of this portfolio. |
| Synthetic CSV generator/validator tests | Executed locally | Run `python -m unittest discover -s "ICT Business analysis/analysis" -p 'test_*.py' -v` and `python "ICT Business analysis/analysis/validate_assets.py"`. These automated checks do not constitute UAT. |
| Dashboard prototype smoke checks | Executed as developer checks only | Local HTTP checks, CSV load, KPI/filter/reset behavior, Python unit tests, and server-rendered error behavior are checked. They are not user acceptance evidence. |

## Proposed sign-off gates

Before a real release, the product owner and process owners should review requirement coverage, unresolved defects, data migration/reconciliation, privacy, accessibility, security, auditability, recovery, and operational support. Record named approvers, dates, environment/build, evidence links, and any accepted residual risk in a controlled test record.

The [`illustrative-defect-log.md`](./illustrative-defect-log.md) contains simulated examples, not defects found during an actual test. The portfolio intentionally does not fabricate user names, UAT execution dates, pass rates, actual defect counts, or business sign-off.
