# Interview Walkthrough: Project 01

> **Honest framing:** Present this as a self-directed fictional portfolio case study. Do not imply client access, stakeholder interviews, production delivery, approvals, executed UAT, or realised benefits.

## 90-second walkthrough

“I built a fictional IT Asset Lifecycle Management case study to demonstrate how I approach an ambiguous operational problem as a Business Analyst. I framed a scenario around fragmented asset records and lifecycle hand-offs, then separated assumptions from facts. I defined business outcomes and MoSCoW requirements, modelled assignment and return/disposition controls, and connected the requirements to acceptance criteria and 13 proposed UAT scenarios.

For the data component, I generated a reproducible 1,200-row synthetic asset snapshot and documented the metric definitions and limitations. I wrote eight example SQL analyses, a Python validator, and unit tests. I then built a read-only browser dashboard with site/status/search filters, KPI cards, distributions, and review prompts. All values are calculated from simulated data using a fixed demonstration date; I do not present them as real operational performance.

Finally, I documented solution context, assumptions, dependencies, an indicative roadmap, and a scenario RAID log. If this were a real engagement, my next steps would be stakeholder discovery, source-data profiling, policy/privacy/security validation, baseline measurement, and usability/UAT with representative users before any platform recommendation.”

## Suggested demonstration flow

1. Explain the simulated problem and explicitly label assumptions.
2. Show the BRD outcome measures and how they differ from achieved benefits.
3. Trace a requirement (for example FR-05) through business rule, process gate, acceptance criterion, and UAT case.
4. Open the dashboard, explain the fixed cut-off and filter behavior, then reconcile a measure to its SQL definition.
5. Show one data-quality rule and its unit test.
6. Close with the discovery questions, RAID items, and implementation decision gates.

## Likely questions and answer prompts

### How did you avoid making the sample feel like a real client project?

The repository repeatedly labels the organisation, data, targets, and test artifacts as simulated. I state that no real interviews, implementation, approval, or UAT occurred, and that sample counts are not operational baseline results.

### Why a CSV prototype instead of a full application?

The objective is to demonstrate analysis, metric definition, filtering, and exception-review concepts without pretending platform selection or integration feasibility is known. A real solution choice depends on discovery, security, data, architecture, and cost evidence.

### What would you validate first with stakeholders?

System-of-record ownership, definitions of active/assigned/overdue, return escalation policy, sanitisation/disposal evidence, reconciliation population, minimum data, and the decision each dashboard measure supports.

### How did you validate the dashboard?

Automated checks validate CSV structure and basic field rules; unit tests cover validator behavior. Prototype smoke checks verify serving and interactions. The proposed UAT cases are not real user acceptance evidence; usability, accessibility, and production controls require separate validation.

### What would you improve next?

Add a confirmed AS-IS based on interviews, resolve data-policy questions, define event history and ownership, test with representative users, and establish an evidence-based baseline before making benefits claims.

## STAR-style example (portfolio exercise)

- **Situation:** In the fictional scenario, teams cannot consistently see lifecycle state and ownership across fragmented records.
- **Task:** Demonstrate a traceable analysis from business problem to operational reporting concept.
- **Action:** Created scope and assumptions, requirements, process models, sample-data controls, metric definitions, prototype, and proposed UAT/governance artifacts.
- **Result:** A reproducible work sample that can be reviewed end-to-end. This is a portfolio deliverable, not a measured business result or implemented solution.
