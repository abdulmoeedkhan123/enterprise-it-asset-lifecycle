"""Unit tests for the synthetic asset CSV validator and generator."""

import tempfile
import unittest
from pathlib import Path

from generate_assets import ROW_COUNT, generate
from validate_assets import validate_rows


def valid_row(asset_id: str = "AST-TEST-01") -> dict[str, str]:
    return {
        "asset_id": asset_id,
        "asset_type": "Laptop",
        "manufacturer": "Example",
        "model": "Business Laptop",
        "serial_ref": "SYN-TEST-01",
        "site": "Remote",
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


class ValidateRowsTests(unittest.TestCase):
    def test_accepts_valid_row(self) -> None:
        self.assertEqual(validate_rows([valid_row()]), [])

    def test_rejects_duplicate_asset_ids(self) -> None:
        self.assertTrue(
            any(
                "duplicate asset_id" in error
                for error in validate_rows([valid_row(), valid_row()])
            )
        )

    def test_rejects_unknown_lifecycle_status(self) -> None:
        row = valid_row()
        row["lifecycle_status"] = "In Use"
        self.assertTrue(
            any("unsupported lifecycle_status" in error for error in validate_rows([row]))
        )

    def test_rejects_invalid_sanitisation_boolean(self) -> None:
        row = valid_row()
        row["sanitisation_required"] = "yes"
        self.assertTrue(
            any("must be true or false" in error for error in validate_rows([row]))
        )

    def test_rejects_invalid_date(self) -> None:
        row = valid_row()
        row["purchase_date"] = "01/01/2024"
        self.assertTrue(
            any("ISO YYYY-MM-DD" in error for error in validate_rows([row]))
        )

    def test_rejects_warranty_before_purchase(self) -> None:
        row = valid_row()
        row["warranty_end"] = "2023-12-31"
        self.assertTrue(
            any("earlier than purchase_date" in error for error in validate_rows([row]))
        )

    def test_rejects_empty_dataset(self) -> None:
        self.assertEqual(validate_rows([]), ["CSV contains no asset rows."])


class GenerateAssetsTests(unittest.TestCase):
    def test_generation_is_repeatable_and_has_expected_row_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "assets.csv"
            first_count = generate(output)
            first_output = output.read_bytes()
            second_count = generate(output)

            self.assertEqual(first_count, ROW_COUNT)
            self.assertEqual(second_count, ROW_COUNT)
            self.assertEqual(first_output, output.read_bytes())
            self.assertEqual(first_output.count(b"\n") - 1, ROW_COUNT)


if __name__ == "__main__":
    unittest.main()
