(() => {
  "use strict";

  const REPORT_DATE = "2026-10-19";
  const EXCLUDED_ACTIVE_STATUSES = new Set(["Disposed", "Lost / Stolen"]);
  const elements = {
    loadState: document.querySelector("#load-state"),
    statusDot: document.querySelector(".status-dot"),
    siteFilter: document.querySelector("#site-filter"),
    statusFilter: document.querySelector("#status-filter"),
    searchFilter: document.querySelector("#search-filter"),
    filterSummary: document.querySelector("#filter-summary"),
    kpiGrid: document.querySelector("#kpi-grid"),
    statusChart: document.querySelector("#status-chart"),
    siteChart: document.querySelector("#site-chart"),
    reviewTable: document.querySelector("#review-table"),
    reviewCount: document.querySelector("#review-count"),
    emptyReview: document.querySelector("#empty-review"),
  };

  let assets = [];

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;

    for (let index = 0; index < text.length; index += 1) {
      const character = text[index];
      if (quoted) {
        if (character === '"' && text[index + 1] === '"') {
          cell += '"';
          index += 1;
        } else if (character === '"') {
          quoted = false;
        } else {
          cell += character;
        }
      } else if (character === '"' && cell.length === 0) {
        quoted = true;
      } else if (character === ",") {
        row.push(cell);
        cell = "";
      } else if (character === "\n") {
        row.push(cell.replace(/\r$/, ""));
        if (row.some((value) => value.length > 0)) rows.push(row);
        row = [];
        cell = "";
      } else {
        cell += character;
      }
    }

    if (quoted) throw new Error("The CSV contains an unclosed quoted field.");
    if (cell.length > 0 || row.length > 0) {
      row.push(cell.replace(/\r$/, ""));
      if (row.some((value) => value.length > 0)) rows.push(row);
    }
    if (rows.length < 2) throw new Error("The CSV has no asset records.");

    const headers = rows[0];
    const requiredHeaders = [
      "asset_id",
      "site",
      "custodian_ref",
      "lifecycle_status",
      "warranty_end",
      "return_due_date",
      "sanitisation_required",
      "sanitisation_result",
      "sanitisation_evidence_ref",
    ];
    const missingHeaders = requiredHeaders.filter((header) => !headers.includes(header));
    if (missingHeaders.length > 0) {
      throw new Error(`The CSV is missing required columns: ${missingHeaders.join(", ")}.`);
    }

    return rows.slice(1).map((values) => {
      if (values.length !== headers.length) {
        throw new Error("The CSV contains a row with an unexpected number of fields.");
      }
      return Object.fromEntries(headers.map((header, index) => [header, values[index]]));
    });
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function uniqueSorted(values) {
    return [...new Set(values)].sort((left, right) => left.localeCompare(right));
  }

  function setOptions(select, values, defaultLabel) {
    select.replaceChildren(new Option(defaultLabel, ""));
    for (const value of values) select.add(new Option(value, value));
  }

  function filteredAssets() {
    const site = elements.siteFilter.value;
    const status = elements.statusFilter.value;
    const search = elements.searchFilter.value.trim().toLowerCase();
    return assets.filter((asset) => {
      const matchesSite = !site || asset.site === site;
      const matchesStatus = !status || asset.lifecycle_status === status;
      const matchesSearch = !search || [
        asset.asset_id,
        asset.site,
        asset.custodian_ref,
      ].some((value) => value.toLowerCase().includes(search));
      return matchesSite && matchesStatus && matchesSearch;
    });
  }

  function isOverdueReturn(asset) {
    return asset.lifecycle_status === "Return Pending"
      && Boolean(asset.return_due_date)
      && asset.return_due_date < REPORT_DATE;
  }

  function activeWarrantyExpired(asset) {
    return !EXCLUDED_ACTIVE_STATUSES.has(asset.lifecycle_status)
      && asset.warranty_end < REPORT_DATE;
  }

  function reviewPrompt(asset) {
    if (isOverdueReturn(asset)) return "Return is past due";
    if (asset.lifecycle_status === "Assigned" && !asset.custodian_ref.trim()) {
      return "Assigned record has no custodian reference";
    }
    const atDisposition = ["Ready for Disposal", "Disposed"].includes(asset.lifecycle_status);
    const sanitisationIncomplete = asset.sanitisation_required === "true"
      && (asset.sanitisation_result !== "Passed" || !asset.sanitisation_evidence_ref.trim());
    if (atDisposition && sanitisationIncomplete) {
      return "Review sanitisation result and evidence";
    }
    return "";
  }

  function renderKpis(records) {
    const values = [
      { label: "Assets in view", value: records.length, note: "Matching the selected filters" },
      { label: "Assigned", value: records.filter((asset) => asset.lifecycle_status === "Assigned").length, note: "Status is Assigned" },
      { label: "Overdue returns", value: records.filter(isOverdueReturn).length, note: "Return due before 19 Oct 2026", warning: true },
      { label: "Active expired warranty", value: records.filter(activeWarrantyExpired).length, note: "Excludes disposed and lost/stolen", alert: true },
    ];
    elements.kpiGrid.innerHTML = values.map((item) => `
      <article class="kpi-card${item.warning ? " warning" : ""}${item.alert ? " alert" : ""}">
        <span class="kpi-label">${escapeHtml(item.label)}</span>
        <strong class="kpi-value">${item.value.toLocaleString()}</strong>
        <span class="kpi-note">${escapeHtml(item.note)}</span>
      </article>`).join("");
  }

  function renderBars(container, records, field) {
    const counts = new Map();
    for (const asset of records) counts.set(asset[field], (counts.get(asset[field]) || 0) + 1);
    const entries = [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
    if (entries.length === 0) {
      container.innerHTML = '<p class="empty-chart">No records match these filters.</p>';
      return;
    }
    const maximum = Math.max(...entries.map((entry) => entry[1]));
    container.innerHTML = entries.map(([label, count]) => `
      <div class="bar-row">
        <span class="bar-label" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        <span class="bar-track" aria-hidden="true"><span class="bar-fill" style="display:block;width:${(count / maximum) * 100}%"></span></span>
        <span class="bar-value">${count}</span>
      </div>`).join("");
  }

  function renderReviewQueue(records) {
    const flagged = records
      .map((asset) => ({ asset, prompt: reviewPrompt(asset) }))
      .filter((item) => item.prompt)
      .sort((left, right) => left.asset.asset_id.localeCompare(right.asset.asset_id));

    elements.reviewCount.textContent = `${flagged.length} ${flagged.length === 1 ? "item" : "items"}`;
    elements.emptyReview.hidden = flagged.length !== 0;
    elements.reviewTable.innerHTML = flagged.slice(0, 25).map(({ asset, prompt }) => `
      <tr>
        <td>${escapeHtml(asset.asset_id)}</td>
        <td>${escapeHtml(asset.site)}</td>
        <td>${escapeHtml(asset.lifecycle_status)}</td>
        <td><span class="flag">${escapeHtml(prompt)}</span></td>
      </tr>`).join("");
    if (flagged.length > 25) {
      elements.reviewTable.insertAdjacentHTML("beforeend", `<tr><td colspan="4">Showing 25 of ${flagged.length} flagged sample rows.</td></tr>`);
    }
  }

  function render() {
    const records = filteredAssets();
    renderKpis(records);
    renderBars(elements.statusChart, records, "lifecycle_status");
    renderBars(elements.siteChart, records, "site");
    renderReviewQueue(records);
    elements.filterSummary.textContent = `Showing ${records.length} of ${assets.length} sample records`;
  }

  async function start() {
    try {
      const response = await fetch("../data/assets.csv");
      if (!response.ok) throw new Error(`Could not load the sample CSV (HTTP ${response.status}).`);
      assets = parseCsv(await response.text());
      setOptions(elements.siteFilter, uniqueSorted(assets.map((asset) => asset.site)), "All sites");
      setOptions(elements.statusFilter, uniqueSorted(assets.map((asset) => asset.lifecycle_status)), "All statuses");
      for (const control of [elements.siteFilter, elements.statusFilter]) {
        control.addEventListener("change", render);
      }
      elements.searchFilter.addEventListener("input", render);
      document.querySelector("#reset-filters").addEventListener("click", () => {
        elements.siteFilter.value = "";
        elements.statusFilter.value = "";
        elements.searchFilter.value = "";
        render();
      });
      elements.loadState.textContent = `Sample loaded: ${assets.length} fictional records`;
      render();
    } catch (error) {
      elements.statusDot.classList.add("error");
      elements.loadState.textContent = "Sample data could not be loaded";
      elements.kpiGrid.innerHTML = `<p role="alert">${escapeHtml(error.message)} Start the local web server from the repository root; see the dashboard README.</p>`;
      elements.statusChart.innerHTML = "";
      elements.siteChart.innerHTML = "";
      elements.reviewTable.innerHTML = "";
      elements.reviewCount.textContent = "Unavailable";
    }
  }

  start();
})();
