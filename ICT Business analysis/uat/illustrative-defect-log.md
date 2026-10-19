# Illustrative Defect Log Examples

> **Important:** The examples below are invented training examples to demonstrate defect documentation. They were **not found** in a real system or through execution of this portfolio's proposed UAT. Their status is illustrative, not actual.

| Example ID | Example severity | Example summary | Example expected / actual | Example disposition | Reality status |
|---|---|---|---|---|---|
| SIM-DEF-01 | High | Disposal action enabled while required sanitisation evidence is missing | Expected: transition blocked. Example actual: action remains enabled. | Example recommendation: block transition and add an actionable message; retest control paths. | Fictional, not executed |
| SIM-DEF-02 | Medium | KPI total does not update after site filter changes | Expected: all cards reflect combined filter. Example actual: one card retains prior total. | Example recommendation: use one shared filtered result set; add filter regression check. | Fictional, not executed |
| SIM-DEF-03 | Low | Empty search result is not explained to user | Expected: explicit no-results message. Example actual: blank table without explanation. | Example recommendation: show an empty state and retain filter context. | Fictional, not executed |

## Example triage fields

In a real defect system record: actual defect ID, title, environment/build, requirement and test case, steps, expected/actual result, evidence, severity/priority with rationale, reporter, owner, status, workaround, target fix, retest evidence, and closure approver.
