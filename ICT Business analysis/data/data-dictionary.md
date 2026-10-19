# Data Dictionary — Synthetic Asset Snapshot

File: `assets.csv`
Rows: 1,200 synthetic asset records (excluding header).
Generation: Deterministic fictional records for demonstration; generated with a fixed seed by [`../analysis/generate_assets.py`](../analysis/generate_assets.py).
Reporting cut-off: 2026-10-19 (used by example dashboard metrics).
Personal data: No real names, email addresses, phone numbers or street addresses.

| Field | Type | Meaning | Example / rules |
|---|---|---|---|
| asset_id | String | Unique synthetic asset key | AST-0001 |
| asset_type | String | End-user asset category | Laptop, Desktop, Monitor, Phone, Tablet |
| manufacturer | String | Fictional/sample manufacturer label | Lenovo, Dell, HP, Apple, Samsung |
| model | String | Illustrative model family | Business Laptop |
| serial_ref | String | Synthetic serial reference | SYN-00001; not a real serial |
| site | String | Fictional site label | Sydney, Melbourne, Brisbane, Remote |
| department | String | Fictional business unit | Operations, Finance, Sales, IT, HR |
| custodian_ref | String / blank | Synthetic worker reference | EMP-0012; blank for unassigned assets |
| lifecycle_status | String | Current snapshot status | In Stock, Assigned, Return Pending, In Repair, Sanitisation Pending, Ready for Disposal, Disposed, Lost / Stolen |
| purchase_date | Date | Synthetic purchase date | ISO YYYY-MM-DD |
| warranty_end | Date | Synthetic warranty end date | ISO YYYY-MM-DD |
| return_due_date | Date / blank | Due date for return-pending assets | ISO YYYY-MM-DD |
| sanitisation_required | Boolean | Whether the scenario requires sanitisation | true / false |
| sanitisation_result | String / blank | Sample outcome | Passed, Failed, Pending, blank |
| sanitisation_evidence_ref | String / blank | Synthetic evidence pointer | EVD-0001; not a real document |
| disposal_evidence_ref | String / blank | Synthetic disposal evidence pointer | DSP-0001; not a real document |
| last_updated | Date | Synthetic last-update date | ISO YYYY-MM-DD |

## Data quality caveats
- The data is generated for dashboard and SQL practice, not a representative operational sample.
- All identifiers and reference values are synthetic. Manufacturer names are generic labels and do not imply vendor involvement or a real purchase.
- The generator deliberately includes a small number of incomplete records to exercise validation and exception-review behavior.
- Missing evidence values are intentional for exception-analysis practice.
- A snapshot cannot calculate true historical turnaround times; event-level history would be required.
- “Overdue” uses a fixed demonstration reporting date embedded in the dashboard. A production solution should use a configurable business date/timezone and agreed calendar.
