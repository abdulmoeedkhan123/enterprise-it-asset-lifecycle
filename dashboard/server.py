"""Serve the Python-rendered, read-only asset lifecycle dashboard."""

from __future__ import annotations

import csv
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "assets.csv"
STYLES_PATH = Path(__file__).with_name("styles.css")
HOST = "127.0.0.1"
PORT = 8000
REPORT_DATE = date(2026, 10, 19)
REQUIRED_COLUMNS = {
    "asset_id",
    "site",
    "custodian_ref",
    "lifecycle_status",
    "warranty_end",
    "return_due_date",
    "sanitisation_required",
    "sanitisation_result",
    "sanitisation_evidence_ref",
}
EXCLUDED_ACTIVE_STATUSES = {"Disposed", "Lost / Stolen"}


def load_assets(path: Path = DATA_PATH) -> list[dict[str, str]]:
    """Load the sample CSV and reject missing required headers or malformed rows."""
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                "The sample CSV is missing required columns: "
                + ", ".join(sorted(missing_columns))
                + "."
            )
        rows = list(reader)

    if not rows:
        raise ValueError("The sample CSV contains no asset records.")
    if any(
        None in row or any(row.get(column) is None for column in REQUIRED_COLUMNS)
        for row in rows
    ):
        raise ValueError("The sample CSV contains a row with an invalid number of fields.")
    return rows


def filter_assets(
    assets: list[dict[str, str]], site: str = "", status: str = "", search: str = ""
) -> list[dict[str, str]]:
    """Apply the dashboard's site, status, and text-search filters."""
    normalized_search = search.strip().casefold()
    return [
        asset
        for asset in assets
        if (not site or asset["site"] == site)
        and (not status or asset["lifecycle_status"] == status)
        and (
            not normalized_search
            or any(
                normalized_search in asset[field].casefold()
                for field in ("asset_id", "site", "custodian_ref")
            )
        )
    ]


def is_overdue_return(asset: dict[str, str]) -> bool:
    """Apply the documented fixed, date-only overdue rule."""
    due_date = asset["return_due_date"]
    return (
        asset["lifecycle_status"] == "Return Pending"
        and bool(due_date)
        and date.fromisoformat(due_date) < REPORT_DATE
    )


def has_expired_active_warranty(asset: dict[str, str]) -> bool:
    """Count expired warranties except for disposed and lost/stolen records."""
    return (
        asset["lifecycle_status"] not in EXCLUDED_ACTIVE_STATUSES
        and date.fromisoformat(asset["warranty_end"]) < REPORT_DATE
    )


def review_prompt(asset: dict[str, str]) -> str:
    """Return a human-review prompt, or an empty string if no rule matches."""
    if is_overdue_return(asset):
        return "Return is past due"
    if asset["lifecycle_status"] == "Assigned" and not asset["custodian_ref"].strip():
        return "Assigned record has no custodian reference"
    at_disposition = asset["lifecycle_status"] in {"Ready for Disposal", "Disposed"}
    sanitisation_incomplete = asset["sanitisation_required"] == "true" and (
        asset["sanitisation_result"] != "Passed"
        or not asset["sanitisation_evidence_ref"].strip()
    )
    if at_disposition and sanitisation_incomplete:
        return "Review sanitisation result and evidence"
    return ""


def render_options(values: list[str], selected: str, empty_label: str) -> str:
    """Render escaped options for one server-side filter."""
    options = [f'<option value="">{escape(empty_label)}</option>']
    options.extend(
        f'<option value="{escape(value, quote=True)}"'
        f'{" selected" if value == selected else ""}>{escape(value)}</option>'
        for value in values
    )
    return "\n".join(options)


def render_bars(assets: list[dict[str, str]], field: str) -> str:
    """Render a sorted count distribution as accessible-labelled CSS bars."""
    counts: dict[str, int] = {}
    for asset in assets:
        label = asset[field]
        counts[label] = counts.get(label, 0) + 1
    if not counts:
        return '<p class="empty-chart">No records match these filters.</p>'

    maximum = max(counts.values())
    rows = []
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        width = count / maximum * 100
        rows.append(
            '<div class="bar-row">'
            f'<span class="bar-label" title="{escape(label, quote=True)}">{escape(label)}</span>'
            f'<span class="bar-track" aria-hidden="true"><span class="bar-fill" '
            f'style="display:block;width:{width:.2f}%"></span></span>'
            f'<span class="bar-value">{count}</span></div>'
        )
    return "\n".join(rows)


def render_dashboard(
    all_assets: list[dict[str, str]], site: str = "", status: str = "", search: str = ""
) -> str:
    """Render a complete dashboard page using only Python and escaped CSV values."""
    assets = filter_assets(all_assets, site, status, search)
    overdue_count = sum(is_overdue_return(asset) for asset in assets)
    expired_count = sum(has_expired_active_warranty(asset) for asset in assets)
    assigned_count = sum(asset["lifecycle_status"] == "Assigned" for asset in assets)
    flagged = [
        (asset, prompt)
        for asset in assets
        if (prompt := review_prompt(asset))
    ]
    flagged.sort(key=lambda item: item[0]["asset_id"])
    review_rows = "\n".join(
        "<tr>"
        f"<td>{escape(asset['asset_id'])}</td>"
        f"<td>{escape(asset['site'])}</td>"
        f"<td>{escape(asset['lifecycle_status'])}</td>"
        f'<td><span class="flag">{escape(prompt)}</span></td>'
        "</tr>"
        for asset, prompt in flagged[:25]
    )
    if not review_rows:
        review_rows = '<tr><td colspan="4">No flagged rows match the selected filters.</td></tr>'
    if len(flagged) > 25:
        review_rows += (
            f'<tr><td colspan="4">Showing 25 of {len(flagged)} flagged sample rows.</td></tr>'
        )
    empty_state = (
        '<p class="empty-state">No sample review flags match the current filters.</p>'
        if not flagged
        else ""
    )
    search_value = escape(search, quote=True)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Python-rendered dashboard for a fictional IT asset lifecycle scenario.">
  <title>Asset Operations | Portfolio Prototype</title>
  <link rel="stylesheet" href="/dashboard/styles.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <header class="topbar">
    <a class="brand" href="/dashboard/" aria-label="Asset Operations dashboard home">
      <span class="brand-mark" aria-hidden="true">AO</span>
      <span><strong>Asset Operations</strong><small>Lifecycle overview</small></span>
    </a>
    <div class="topbar-meta">
      <span class="demo-tag">SIMULATED DATA</span>
      <span class="report-date">As of <time datetime="2026-10-19">19 Oct 2026</time></span>
    </div>
  </header>
  <main id="main-content" class="page-shell">
    <section class="intro">
      <div>
        <p class="eyebrow">ICT BUSINESS ANALYST PORTFOLIO / PROJECT 01</p>
        <h1>IT asset lifecycle</h1>
        <p class="lede">A sample operational view for inventory, returns, warranty exposure, and disposition follow-up.</p>
      </div>
      <div class="refresh-state"><span class="status-dot" aria-hidden="true"></span>
        <span role="status">Sample loaded: {len(all_assets):,} fictional records</span></div>
    </section>
    <section class="notice" aria-label="Simulation notice">
      <strong>Portfolio prototype</strong>
      <span>Fictional records and calculated example indicators only. Not a live operational system or verified business outcome.</span>
    </section>
    <section class="filter-panel" aria-label="Dashboard filters">
      <div class="filter-heading">
        <div><p class="eyebrow">OPERATIONS VIEW</p><h2>Asset snapshot</h2></div>
        <a class="text-button" href="/dashboard/">Reset filters</a>
      </div>
      <form class="filters" action="/dashboard/" method="get">
        <label for="site-filter">Site
          <select id="site-filter" name="site">
            {render_options(sorted({asset["site"] for asset in all_assets}), site, "All sites")}
          </select>
        </label>
        <label for="status-filter">Lifecycle status
          <select id="status-filter" name="status">
            {render_options(sorted({asset["lifecycle_status"] for asset in all_assets}), status, "All statuses")}
          </select>
        </label>
        <label class="search-label" for="search-filter">Find an asset
          <input id="search-filter" name="q" type="search" value="{search_value}"
                 placeholder="Asset ID, site, or custodian" autocomplete="off">
        </label>
        <button class="submit-button" type="submit">Apply filters</button>
        <p class="filter-summary" aria-live="polite">Showing {len(assets):,} of {len(all_assets):,} sample records</p>
      </form>
    </section>
    <section aria-labelledby="kpi-heading">
      <div class="section-heading"><div><p class="eyebrow">KEY INDICATORS</p>
        <h2 id="kpi-heading">Current snapshot</h2></div><span class="section-note">Filtered view</span></div>
      <div class="kpi-grid">
        <article class="kpi-card"><span class="kpi-label">Assets in view</span>
          <strong class="kpi-value">{len(assets):,}</strong><span class="kpi-note">Matching the selected filters</span></article>
        <article class="kpi-card"><span class="kpi-label">Assigned</span>
          <strong class="kpi-value">{assigned_count:,}</strong><span class="kpi-note">Status is Assigned</span></article>
        <article class="kpi-card warning"><span class="kpi-label">Overdue returns</span>
          <strong class="kpi-value">{overdue_count:,}</strong><span class="kpi-note">Return due before 19 Oct 2026</span></article>
        <article class="kpi-card alert"><span class="kpi-label">Active expired warranty</span>
          <strong class="kpi-value">{expired_count:,}</strong><span class="kpi-note">Excludes disposed and lost/stolen</span></article>
      </div>
    </section>
    <section class="visual-grid" aria-label="Asset breakdowns">
      <article class="panel"><div class="panel-heading"><div><p class="eyebrow">DISTRIBUTION</p>
        <h2>By lifecycle status</h2></div></div>
        <div class="bar-list">{render_bars(assets, "lifecycle_status")}</div></article>
      <article class="panel"><div class="panel-heading"><div><p class="eyebrow">DISTRIBUTION</p>
        <h2>By site</h2></div></div>
        <div class="bar-list">{render_bars(assets, "site")}</div></article>
    </section>
    <section class="panel review-panel" aria-labelledby="review-heading">
      <div class="panel-heading review-heading"><div><p class="eyebrow">HUMAN REVIEW REQUIRED</p>
        <h2 id="review-heading">Example follow-up queue</h2>
        <p class="panel-description">Rule-based sample flags to support investigation; not confirmed exceptions.</p></div>
        <span class="count-pill">{len(flagged)} {"item" if len(flagged) == 1 else "items"}</span>
      </div>
      <div class="table-wrap"><table>
        <thead><tr><th scope="col">Asset</th><th scope="col">Site</th><th scope="col">Status</th><th scope="col">Review prompt</th></tr></thead>
        <tbody>{review_rows}</tbody>
      </table></div>
      {empty_state}
      <p class="table-footnote">Example flags: overdue return, assigned record without custodian reference, or incomplete sanitisation control information at disposition.</p>
    </section>
    <footer class="page-footer">
      <p>Data: {len(all_assets):,} generated fictional asset records. Reporting date and metric rules are fixed for demonstration.</p>
      <a href="/analysis/metric-definitions.md">View metric definitions</a>
    </footer>
  </main>
</body>
</html>"""


def render_error(message: str) -> str:
    """Render an explicit error page without success-shaped dashboard metrics."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample unavailable | Asset Operations</title><link rel="stylesheet" href="/dashboard/styles.css"></head>
<body><main class="page-shell"><section class="panel" role="alert">
<p class="eyebrow">PORTFOLIO PROTOTYPE</p><h1>Sample data could not be loaded</h1>
<p>{escape(message)}</p><p>Check that the synthetic CSV exists and passes
<code>python analysis/validate_assets.py</code>.</p><a href="/dashboard/">Try again</a>
</section></main></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    """Handle dashboard and stylesheet requests using Python's standard library."""

    def do_GET(self) -> None:
        parsed_url = urlsplit(self.path)
        if parsed_url.path == "/dashboard/styles.css":
            self._serve_styles()
            return
        if parsed_url.path not in {"/", "/dashboard", "/dashboard/"}:
            self.send_error(404, "Not found")
            return

        parameters = parse_qs(parsed_url.query, keep_blank_values=True)
        site = parameters.get("site", [""])[0]
        status = parameters.get("status", [""])[0]
        search = parameters.get("q", [""])[0]
        try:
            page = render_dashboard(load_assets(), site, status, search)
            self._send_html(200, page)
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            self._send_html(500, render_error(str(error)))

    def _serve_styles(self) -> None:
        try:
            stylesheet = STYLES_PATH.read_bytes()
        except OSError:
            self.send_error(500, "Dashboard stylesheet could not be read")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(stylesheet)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(stylesheet)

    def _send_html(self, status: int, page: str) -> None:
        content = page.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard running at http://{HOST}:{PORT}/dashboard/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
