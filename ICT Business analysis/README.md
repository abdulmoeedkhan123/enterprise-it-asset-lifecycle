# ICT Business Analyst Portfolio

**Project 01 developed: IT Asset Lifecycle Management**

This repository presents A practical, fictional portfolio case study for an ICT Business Analyst role. Project 01 demonstrates business analysis, requirements, process modelling, data analysis, a Python-powered dashboard prototype, testing design, and project governance. Projects 02 and 03 are portfolio roadmap concepts; they are not presented as completed case studies.

> **Simulation notice:** The organisation, scenario, stakeholders, asset records, targets, process findings, test scenarios, and illustrative defects are fictional. Sample results are calculated from generated data and are not evidence of a real client, implemented system, completed user testing, approved business case, or realised benefit.

## Portfolio roadmap

| # | Project | Focus | Status |
|---|---|---|---|
| 01 | [IT Asset Lifecycle Management](./discovery/business-case.md) | Asset visibility, returns, warranty, sanitisation, and disposal controls | **Current case study - detailed in this repository** |
| 02 | Service Request and SLA Improvement | Intake, categorisation, prioritisation, queue visibility, and service measures | Planned |
| 03 | Joiner-Mover-Leaver Access Workflow | Role-based access requests, approval hand-offs, fulfilment, and audit evidence | Planned |

The roadmap concepts are not represented as finished deliverables or professional experience.

## Project 01 deliverables

| Deliverable | Contents |
|---|---|
| Business analysis | [Business case](./discovery/business-case.md), [BRD](./discovery/business-requirements.md), [stakeholder analysis](./discovery/stakeholder-analysis.md), scope, assumptions, and constraints |
| Requirements | [Prioritised catalogue](./requirements/requirements.md), user stories, acceptance criteria, and business rules |
| Process modelling | Proposed AS-IS and TO-BE Mermaid flows, state guardrails, and draft RACI |
| Data analysis | 1,200 generated asset records, [data dictionary](./data/data-dictionary.md), reproducible generator, validator, and eight SQL analyses |
| Dashboard | Interactive site/status/search filters, KPI cards, lifecycle/site distributions, and example review queue |
| Testing | UAT plan, 13 proposed test scenarios, traceability, sample-data tests, and clearly illustrative defect log |
| Project governance | Solution context, delivery roadmap, RAID log, and interview walkthrough |

## Explore Project 01

1. Start with the [fictional business case](./discovery/business-case.md), [BRD](./discovery/business-requirements.md), and [stakeholder analysis](./discovery/stakeholder-analysis.md).
2. Review [requirements and business rules](./requirements/requirements.md) and [AS-IS / TO-BE process models](./solution-design/process-models.md).
3. Open the [dashboard](./dashboard/README.md) and review the [metric definitions](./analysis/metric-definitions.md).
4. Inspect the [data dictionary](./data/data-dictionary.md), [eight SQL analyses](./analysis/queries.sql), and [UAT traceability](./uat/acceptance-criteria.md).
5. Review the [solution context](./governance/solution-context.md), [roadmap](./governance/delivery-roadmap.md), [RAID log](./governance/raid-log.md), and [interview walkthrough](./governance/interview-walkthrough.md).

## Run and validate locally

From the repository root:

```bash
python "ICT Business analysis/dashboard/server.py"
```

Open <http://localhost:8000/dashboard/> in a browser. The Python standard-library server loads the CSV and renders filtered pages; no JavaScript or third-party web framework is required. Stop it with Ctrl+C.

In another terminal, run:

```bash
python "ICT Business analysis/analysis/generate_assets.py"
python -m unittest discover -s "ICT Business analysis/analysis" -p 'test_*.py' -v
python -m unittest discover -s "ICT Business analysis/dashboard" -p 'test_*.py' -v
python "ICT Business analysis/analysis/validate_assets.py"
```

The generator rewrites the dataset deterministically to 1,200 rows. Do not rerun it if you have made intentional manual edits to the generated CSV without first preserving them elsewhere.

## Repository map

| Path | Purpose |
|---|---|
| [`discovery/`](./discovery/) | Business case, BRD, stakeholder analysis, scope, and assumptions |
| [`requirements/`](./requirements/) | Requirements catalogue, user stories, and business rules |
| [`solution-design/`](./solution-design/) | AS-IS / TO-BE process models and state-transition controls |
| [`data/`](./data/) | Reproducible fictional asset snapshot and data dictionary |
| [`analysis/`](./analysis/) | Eight SQL examples, metric definitions, generator, validator, and unit tests |
| [`dashboard/`](./dashboard/) | Browser-based interactive prototype |
| [`uat/`](./uat/) | Acceptance criteria, 13 proposed scenarios, traceability, and illustrative defect log |
| [`governance/`](./governance/) | Solution context, delivery roadmap, RAID, and interview walkthrough |

## Evidence boundaries

- The 1,200 asset rows are deterministic generated examples, not real inventory or personal data.
- Fixed dashboard cut-off: **19 October 2026**. Every dashboard value is recalculated from the synthetic CSV; no real KPI, saving, or outcome is claimed.
- Requirements, business rules, targets, and process models are proposed case-study artifacts, not approved client decisions.
- UAT scenarios are proposed and have not been executed against a real system or by real users. The sample-data validator's automated tests are separate and can be run locally.
- The defect log contains illustrative examples only; it does not report defects discovered in a production implementation.
- The dashboard is a read-only portfolio prototype with no authentication, backend, persistence, integrations, or production security controls.
