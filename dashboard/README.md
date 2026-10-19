# Dashboard Prototype

This Python-powered, read-only prototype demonstrates an asset-operations dashboard over the 1,200-row fictional CSV in `../data/assets.csv`. Python handles CSV loading, filtering, metric calculations, and HTML rendering; CSS handles visual styling. There is no browser JavaScript or third-party web framework.

## Run locally

From the repository root:

```bash
python dashboard/server.py
```

Open <http://localhost:8000/dashboard/>. Stop the server with Ctrl+C.

## Included interactions

- Filter the sample by site and lifecycle status using server-rendered forms.
- See record count, assigned count, overdue returns, and active expired-warranty counts for the filtered set.
- Compare lifecycle status and site counts.
- Review rows matching the documented example follow-up rules.
- Use the case-insensitive text search to find an asset ID, site, or custodian reference.
- Receive an explicit error page if the CSV is unavailable or malformed; failed loads do not display success-shaped KPIs.

Run dashboard unit tests from the repository root:

```bash
python -m unittest discover -s dashboard -p 'test_*.py' -v
```

## Scope and limitations

- No login, write actions, persistence, integration, real personal information, or live refresh.
- This is a minimal Python HTTP server bound to localhost for portfolio demonstration, not a production web server or deployment pattern.
- The reporting date is fixed to 19 October 2026; the metric rules are in [`../analysis/metric-definitions.md`](../analysis/metric-definitions.md).
- The prototype does not claim to meet the separate 10,000-row performance target; that target needs measurement in an agreed test environment.
- All CSV rows and resulting counts are synthetic. Review flags are prompts for human investigation, not verified incidents.
- The prototype demonstrates interaction and metric definitions only. It is not a production design or a formal accessibility/security certification.
