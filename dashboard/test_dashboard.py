"""Tests for Python dashboard filtering, metrics, escaping, and error rendering."""

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from server import REPORT_DATE, filter_assets, has_expired_active_warranty, is_overdue_return
from server import load_assets, render_dashboard, render_error, review_prompt


def asset(**overrides: str) -> dict[str, str]:
    record = {
        "asset_id": "AST-TEST-01",
        "asset_type": "Laptop",
        "manufacturer": "Example",
        "model": "Business Laptop",
        "serial_ref": "SYN-TEST-01",
        "site": "Sydney",
        "department": "IT",
        "custodian_ref": "EMP-TEST-01",
        "lifecycle_status": "Assigned",
        "purchase_date": "2024-01-01",
        "warranty_end": "2027-01-01",
        "return_due_date": "",
        "sanitisation_required": "false",
        "sanitisation_result": "",
        "sanitisation_evidence_ref": "",
        "disposal_evidence_ref": "",
        "last_updated": "2026-10-01",
    }
    record.update(overrides)
    return record


class DashboardTests(unittest.TestCase):
    def test_filters_combine_and_search_without_case_sensitivity(self) -> None:
        records = [
            asset(),
            asset(asset_id="AST-TEST-02", site="Melbourne", custodian_ref="EMP-TEST-02"),
        ]
        result = filter_assets(records, site="Sydney", status="Assigned", search="emp-test-01")
        self.assertEqual([record["asset_id"] for record in result], ["AST-TEST-01"])

    def test_overdue_return_uses_strict_date_cutoff(self) -> None:
        overdue = asset(
            lifecycle_status="Return Pending",
            return_due_date=(REPORT_DATE - timedelta(days=1)).isoformat(),
        )
        due_today = asset(
            lifecycle_status="Return Pending",
            return_due_date=REPORT_DATE.isoformat(),
        )
        self.assertTrue(is_overdue_return(overdue))
        self.assertFalse(is_overdue_return(due_today))

    def test_disposed_assets_are_excluded_from_active_expired_warranty(self) -> None:
        expired_assigned = asset(warranty_end=(REPORT_DATE - timedelta(days=1)).isoformat())
        expired_disposed = asset(
            lifecycle_status="Disposed",
            warranty_end=(REPORT_DATE - timedelta(days=1)).isoformat(),
        )
        self.assertTrue(has_expired_active_warranty(expired_assigned))
        self.assertFalse(has_expired_active_warranty(expired_disposed))

    def test_disposition_review_requires_pass_and_evidence(self) -> None:
        record = asset(
            lifecycle_status="Ready for Disposal",
            sanitisation_required="true",
            sanitisation_result="Passed",
            sanitisation_evidence_ref="",
        )
        self.assertEqual(
            review_prompt(record), "Review sanitisation result and evidence"
        )
        record["sanitisation_evidence_ref"] = "EVD-TEST-01"
        self.assertEqual(review_prompt(record), "")

    def test_dashboard_escapes_search_and_shows_zero_result_state(self) -> None:
        page = render_dashboard([asset()], search='<script>alert("x")</script>')
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Showing 0 of 1 sample records", page)
        self.assertIn("No sample review flags match", page)

    def test_error_page_does_not_show_dashboard_kpis(self) -> None:
        page = render_error("CSV unavailable")
        self.assertIn("Sample data could not be loaded", page)
        self.assertNotIn("kpi-value", page)

    def test_load_rejects_missing_required_column(self) -> None:
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "assets.csv"
            csv_path.write_text("asset_id,site\nAST-1,Sydney\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required columns"):
                load_assets(csv_path)

    def test_load_rejects_short_row(self) -> None:
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "assets.csv"
            csv_path.write_text(
                "asset_id,site,custodian_ref,lifecycle_status,warranty_end,"
                "return_due_date,sanitisation_required,sanitisation_result,"
                "sanitisation_evidence_ref\nAST-1,Sydney\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "invalid number of fields"):
                load_assets(csv_path)


if __name__ == "__main__":
    unittest.main()
