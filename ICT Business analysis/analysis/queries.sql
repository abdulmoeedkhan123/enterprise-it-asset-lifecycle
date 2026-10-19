-- Eight portfolio SQL examples for a CSV imported into a table named assets.
-- All records are synthetic. Cut-off: 2026-10-19. Empty CSV fields are ''.

-- 1. Inventory by lifecycle status.
SELECT lifecycle_status, COUNT(*) AS asset_count
FROM assets
GROUP BY lifecycle_status
ORDER BY asset_count DESC, lifecycle_status;

-- 2. Overdue returns as of the fixed cut-off (date-only; no business calendar).
SELECT asset_id, site, department, custodian_ref, return_due_date
FROM assets
WHERE lifecycle_status = 'Return Pending'
  AND return_due_date <> ''
  AND return_due_date < '2026-10-19'
ORDER BY return_due_date, asset_id;

-- 3. Active assets with expired warranties.
SELECT asset_id, asset_type, site, department, lifecycle_status, warranty_end
FROM assets
WHERE lifecycle_status NOT IN ('Disposed', 'Lost / Stolen')
  AND warranty_end < '2026-10-19'
ORDER BY warranty_end, asset_id;

-- 4. Disposition records requiring sanitisation-control review.
SELECT asset_id, lifecycle_status, sanitisation_result,
       sanitisation_evidence_ref, disposal_evidence_ref
FROM assets
WHERE sanitisation_required = 'true'
  AND lifecycle_status IN ('Ready for Disposal', 'Disposed')
  AND (sanitisation_result <> 'Passed' OR sanitisation_evidence_ref = '')
ORDER BY lifecycle_status, asset_id;

-- 5. Assigned records without a custodian reference.
SELECT asset_id, site, department, last_updated
FROM assets
WHERE lifecycle_status = 'Assigned'
  AND custodian_ref = ''
ORDER BY site, asset_id;

-- 6. Active asset count by site and lifecycle status for reconciliation.
SELECT site, lifecycle_status, COUNT(*) AS asset_count
FROM assets
WHERE lifecycle_status NOT IN ('Disposed', 'Lost / Stolen')
GROUP BY site, lifecycle_status
ORDER BY site, lifecycle_status;

-- 7. Mandatory-field completeness by site.
SELECT site,
       COUNT(*) AS total_assets,
       SUM(CASE WHEN asset_id <> '' THEN 1 ELSE 0 END) AS with_asset_id,
       SUM(CASE WHEN asset_type <> '' THEN 1 ELSE 0 END) AS with_asset_type,
       SUM(CASE WHEN lifecycle_status <> '' THEN 1 ELSE 0 END) AS with_status,
       SUM(CASE WHEN site <> '' THEN 1 ELSE 0 END) AS with_site
FROM assets
GROUP BY site
ORDER BY site;

-- 8. Records not updated in the prior 90 days, using the fixed sample cut-off.
SELECT asset_id, site, lifecycle_status, last_updated,
       CAST(julianday('2026-10-19') - julianday(last_updated) AS INTEGER) AS days_since_update
FROM assets
WHERE last_updated < date('2026-10-19', '-90 days')
ORDER BY last_updated, asset_id;
