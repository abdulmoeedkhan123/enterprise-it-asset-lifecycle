# Dashboard Prototype

This static, read-only prototype demonstrates an asset-operations dashboard over the 1,200-row fictional CSV in `../data/assets.csv`.

## Run locally

From the repository root:

```bash
python -m http.server 8000
```

Open <http://localhost:8000/dashboard/>. A local web server is required because browsers generally block CSV `fetch` requests from a `file://` page.

## Included interactions

- Filter the sample by site and lifecycle status.
- See record count, assigned count, overdue returns, and active expired-warranty counts for the filtered set.
- Compare lifecycle status and site counts.
- Review rows matching the documented example follow-up rules.
- Use the text search to find an asset ID, site, or custodian reference.

## Scope and limitations

- No login, backend, write actions, persistence, integration, real personal information, or live refresh.
- The reporting date is fixed to 19 October 2026; the metric rules are in [`../analysis/metric-definitions.md`](../analysis/metric-definitions.md).
- The prototype does not claim to meet the separate 10,000-row performance target; that target needs measurement in an agreed test environment.
- All CSV rows and resulting counts are synthetic. Review flags are prompts for human investigation, not verified incidents.
- The prototype demonstrates interaction and metric definitions only. It is not a production design or a formal accessibility/security certification.
