# Dashboard Metric Definitions

> **Demonstration only:** These definitions are applied to fictional sample data. The reporting cut-off is fixed at **19 October 2026** to make the dashboard reproducible.

| Metric | Definition | Exclusions / notes |
|---|---|---|
| Assets in scope | Number of CSV asset records matching the selected dashboard filters | Not a claim about a real organisation's asset population. |
| Assigned assets | Matching records where `lifecycle_status = Assigned` | Does not include Return Pending. |
| Overdue returns | Matching Return Pending records with a populated `return_due_date` earlier than 2026-10-19 | Due on the cut-off date is not counted overdue until after that date; no holiday calendar is applied. |
| Active assets with expired warranty | Matching records with `warranty_end` earlier than 2026-10-19, excluding `Disposed` and `Lost / Stolen` | “Active” is a portfolio definition for this prototype, not an accounting or warranty policy. |
| Example review flags | Rows that match one of the explicit rules in the dashboard's “Review queue” | These are prompts for human review, not confirmed incidents or policy breaches. |

## Review-queue rules in the prototype

1. **Overdue return:** `Return Pending`, a return due date exists, and it is before the fixed reporting date.
2. **Assignment detail missing:** `Assigned` and `custodian_ref` is blank.
3. **Disposition control needs review:** status is `Ready for Disposal` or `Disposed`, sanitisation is required, and either the result is not `Passed` or the sanitisation evidence reference is blank.

The flags are intentionally conservative examples, not an automated decision or a substitute for validating record context. A real design would confirm event timing, policy, timezone, status transitions, authoritative data, and false-positive handling with users.

## Snapshot observations

At the fixed reporting date, the CSV contains 1,200 synthetic records. Exact counts are generated reproducibly by `analysis/generate_assets.py`; dashboard counts are calculated at runtime and change if the generator rules change. The dashboard's active expired-warranty KPI excludes disposed and lost/stolen records, so it is intentionally different from an all-status warranty-expiry count.

These counts describe only the repository's generated sample. They are not performance results, a baseline, or operational findings.
