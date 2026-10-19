"""Validate the structure and basic field rules of the synthetic asset CSV."""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path


DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "assets.csv"
REQUIRED_COLUMNS = {
    "asset_id",
    "asset_type",
    "manufacturer",
    "model",
    "serial_ref",
    "site",
    "department",
    "custodian_ref",
    "lifecycle_status",
    "purchase_date",
    "warranty_end",
    "return_due_date",
    "sanitisation_required",
    "sanitisation_result",
    "sanitisation_evidence_ref",
    "disposal_evidence_ref",
    "last_updated",
}
ALLOWED_STATUSES = {
    "In Stock",
    "Assigned",
    "Return Pending",
    "In Repair",
    "Sanitisation Pending",
    "Ready for Disposal",
    "Disposed",
    "Lost / Stolen",
}
DATE_COLUMNS = ("purchase_date", "warranty_end", "return_due_date", "last_updated")


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    """Return structural and basic field-rule errors for asset records."""
    errors: list[str] = []
    seen_ids: set[str] = set()

    if not rows:
        return ["CSV contains no asset rows."]

    for row_number, row in enumerate(rows, start=2):
        asset_id = row.get("asset_id", "").strip()
        if not asset_id:
            errors.append(f"Row {row_number}: asset_id is required.")
        elif asset_id in seen_ids:
            errors.append(f"Row {row_number}: duplicate asset_id {asset_id}.")
        seen_ids.add(asset_id)

        for column in ("asset_type", "site", "department", "lifecycle_status"):
            if not row.get(column, "").strip():
                errors.append(f"Row {row_number}: {column} is required.")

        if row.get("lifecycle_status") not in ALLOWED_STATUSES:
            errors.append(
                f"Row {row_number}: unsupported lifecycle_status "
                f"{row.get('lifecycle_status')!r}."
            )

        if row.get("sanitisation_required") not in {"true", "false"}:
            errors.append(
                f"Row {row_number}: sanitisation_required must be true or false."
            )

        parsed_dates: dict[str, date] = {}
        for column in DATE_COLUMNS:
            value = row.get(column, "").strip()
            if not value and column == "return_due_date":
                continue
            if not value:
                errors.append(f"Row {row_number}: {column} is required.")
                continue
            try:
                parsed_dates[column] = date.fromisoformat(value)
            except ValueError:
                errors.append(
                    f"Row {row_number}: {column} must use ISO YYYY-MM-DD format."
                )

        purchase_date = parsed_dates.get("purchase_date")
        warranty_end = parsed_dates.get("warranty_end")
        if purchase_date and warranty_end and warranty_end < purchase_date:
            errors.append(
                f"Row {row_number}: warranty_end is earlier than purchase_date."
            )

    return errors


def validate_file(path: Path) -> tuple[int, list[str]]:
    """Read a CSV, verify its required header, and validate its rows."""
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            headers = set(reader.fieldnames or [])
            missing_columns = sorted(REQUIRED_COLUMNS - headers)
            if missing_columns:
                return 0, [
                    "CSV is missing required columns: " + ", ".join(missing_columns)
                ]
            rows = list(reader)
    except OSError as error:
        return 0, [f"Could not read {path}: {error}"]

    return len(rows), validate_rows(rows)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    row_count, errors = validate_file(path)
    if errors:
        print(f"FAIL: {len(errors)} issue(s) found in {path} ({row_count} rows).")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"PASS: {path} contains {row_count} rows with the required columns "
        "and valid basic field rules."
    )
    print("This validates the sample file only, not its real-world accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
