"""Generate the deterministic synthetic asset snapshot used by this portfolio."""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "assets.csv"
REPORT_DATE = date(2026, 10, 19)
ROW_COUNT = 1200
SEED = 20261019
FIELDS = [
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
]
STATUS_WEIGHTS = (
    ("In Stock", 21),
    ("Assigned", 40),
    ("Return Pending", 9),
    ("In Repair", 6),
    ("Sanitisation Pending", 4),
    ("Ready for Disposal", 5),
    ("Disposed", 12),
    ("Lost / Stolen", 3),
)
ASSET_TYPES = ("Laptop", "Desktop", "Monitor", "Phone", "Tablet")
MODELS = {
    "Laptop": "Business Laptop",
    "Desktop": "Business Desktop",
    "Monitor": "Office Monitor",
    "Phone": "Corporate Phone",
    "Tablet": "Business Tablet",
}
MANUFACTURERS = ("Lenovo", "Dell", "HP", "Apple", "Samsung")
SITES = ("Brisbane", "Melbourne", "Remote", "Sydney")
DEPARTMENTS = ("Finance", "HR", "IT", "Operations", "Sales")


def iso(value: date) -> str:
    return value.isoformat()


def generate_row(index: int, rng: random.Random) -> dict[str, str]:
    asset_type = rng.choice(ASSET_TYPES)
    status = rng.choices(
        [name for name, _weight in STATUS_WEIGHTS],
        weights=[weight for _name, weight in STATUS_WEIGHTS],
        k=1,
    )[0]
    purchase_date = REPORT_DATE - timedelta(days=rng.randint(45, 2450))
    warranty_years = rng.choice((1, 2, 3))
    warranty_end = purchase_date + timedelta(days=round(warranty_years * 365.25))
    last_updated = REPORT_DATE - timedelta(days=rng.randint(0, 110))

    custodian = ""
    if status == "Assigned" and rng.random() >= 0.025:
        custodian = f"EMP-{rng.randint(1, 500):04d}"
    elif status in {"Return Pending", "In Repair", "Lost / Stolen"} and rng.random() >= 0.08:
        custodian = f"EMP-{rng.randint(1, 500):04d}"

    return_due_date = ""
    if status == "Return Pending":
        return_due_date = iso(REPORT_DATE + timedelta(days=rng.randint(-45, 40)))

    sanitisation_required = rng.random() < 0.27
    sanitisation_result = ""
    sanitisation_evidence_ref = ""
    if status == "Sanitisation Pending":
        sanitisation_required = True
        sanitisation_result = "Pending"
    elif sanitisation_required and status in {"Ready for Disposal", "Disposed"}:
        sanitisation_result = rng.choices(
            ("Passed", "Failed", "Pending", ""), weights=(65, 12, 8, 15), k=1
        )[0]
        if sanitisation_result == "Passed" and rng.random() >= 0.08:
            sanitisation_evidence_ref = f"EVD-{index:05d}"
    elif sanitisation_required and rng.random() < 0.18:
        sanitisation_result = rng.choice(("Failed", "Pending"))

    disposal_evidence_ref = ""
    if status == "Disposed" and rng.random() >= 0.12:
        disposal_evidence_ref = f"DSP-{index:05d}"

    return {
        "asset_id": f"AST-{index:04d}",
        "asset_type": asset_type,
        "manufacturer": rng.choice(MANUFACTURERS),
        "model": MODELS[asset_type],
        "serial_ref": f"SYN-{index:05d}",
        "site": rng.choice(SITES),
        "department": rng.choice(DEPARTMENTS),
        "custodian_ref": custodian,
        "lifecycle_status": status,
        "purchase_date": iso(purchase_date),
        "warranty_end": iso(warranty_end),
        "return_due_date": return_due_date,
        "sanitisation_required": "true" if sanitisation_required else "false",
        "sanitisation_result": sanitisation_result,
        "sanitisation_evidence_ref": sanitisation_evidence_ref,
        "disposal_evidence_ref": disposal_evidence_ref,
        "last_updated": iso(last_updated),
    }


def generate(path: Path = OUTPUT) -> int:
    """Write ROW_COUNT deterministic synthetic rows to the target CSV."""
    rng = random.Random(SEED)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(generate_row(index, rng) for index in range(1, ROW_COUNT + 1))
    return ROW_COUNT


if __name__ == "__main__":
    print(f"Wrote {generate()} fictional asset records to {OUTPUT}")
