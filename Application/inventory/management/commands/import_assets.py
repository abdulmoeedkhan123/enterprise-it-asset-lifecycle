from __future__ import annotations

import csv
import hashlib
from datetime import date
from io import StringIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from inventory.models import Asset, ImportRun, LifecycleEvent, LifecycleStatus
from inventory.reporting import profile_asset_rows


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


class Command(BaseCommand):
    help = "Idempotently import an approved-format asset CSV and record an import run."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, type=Path)
        parser.add_argument(
            "--confirm-authorized-source",
            action="store_true",
            help="Confirm that you are authorized to import this source and data.",
        )

    def handle(self, *args, **options):
        source_path: Path = options["input"]
        if not options["confirm_authorized_source"]:
            raise CommandError(
                "Import requires --confirm-authorized-source. Confirm source ownership, "
                "authorization, privacy, access, and retention requirements before "
                "loading any data. Use only synthetic data for this portfolio exercise."
            )
        if not source_path.is_file():
            raise CommandError(f"Input file does not exist: {source_path}")

        try:
            file_bytes = source_path.read_bytes()
            source_hash = hashlib.sha256(file_bytes).hexdigest()
            reader = csv.DictReader(
                StringIO(file_bytes.decode("utf-8-sig"), newline="")
            )
            fieldnames = reader.fieldnames or []
            duplicate_headers = sorted(
                {field for field in fieldnames if fieldnames.count(field) > 1}
            )
            missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
            rows = list(reader)
        except (OSError, UnicodeError, csv.Error) as error:
            raise CommandError(f"Could not read asset CSV: {error}") from error

        if duplicate_headers:
            summary = "Input contains duplicate columns: " + ", ".join(duplicate_headers)
            self._record_failed_run(
                source_path,
                source_hash,
                rows_seen=len(rows),
                rows_rejected=len(rows),
                error_summary=summary,
            )
            raise CommandError(summary)
        if missing:
            summary = "Input is missing required columns: " + ", ".join(missing)
            self._record_failed_run(
                source_path,
                source_hash,
                rows_seen=len(rows),
                rows_rejected=len(rows),
                error_summary=summary,
            )
            raise CommandError(
                "Input is missing required columns: " + ", ".join(missing)
            )
        if not rows:
            self._record_failed_run(
                source_path,
                source_hash,
                rows_seen=0,
                rows_rejected=0,
                error_summary="Input CSV contains no data rows.",
            )
            raise CommandError("Input CSV contains no data rows.")
        if any(
            None in row or any(value is None for value in row.values())
            for row in rows
        ):
            self._record_failed_run(
                source_path,
                source_hash,
                rows_seen=len(rows),
                rows_rejected=len(rows),
                error_summary="Input CSV has a row with an invalid number of fields.",
            )
            raise CommandError("Input CSV has a row with an invalid number of fields.")

        rows = [{field: value.strip() for field, value in row.items()} for row in rows]
        quality_summary = profile_asset_rows(rows, as_of=timezone.localdate())
        validation_errors = self._validate_rows(rows)
        if validation_errors:
            summary = "\n".join(validation_errors[:20])
            self._record_failed_run(
                source_path,
                source_hash,
                rows_seen=len(rows),
                rows_rejected=len(rows),
                error_summary=summary[:4000],
                quality_summary=quality_summary,
            )
            raise CommandError(
                f"Input validation failed with {len(validation_errors)} issue(s):\n{summary}"
            )

        run = ImportRun.objects.create(
            source_name=source_path.name,
            source_sha256=source_hash,
            status=ImportRun.Status.RUNNING,
        )
        created_count = updated_count = unchanged_count = 0
        try:
            with transaction.atomic():
                for row in rows:
                    values = self._convert_row(row)
                    asset = Asset.objects.filter(asset_id=values["asset_id"]).first()
                    if asset is None:
                        asset = Asset(**values)
                        asset.save()
                        LifecycleEvent.objects.create(
                            asset=asset,
                            event_type=LifecycleEvent.EventType.IMPORTED,
                            to_status=asset.lifecycle_status,
                            reason="Created from synthetic CSV import",
                            details={"import_run_id": run.pk, "source": source_path.name},
                        )
                        created_count += 1
                        continue

                    changed_fields = [
                        field
                        for field, value in values.items()
                        if getattr(asset, field) != value
                    ]
                    if not changed_fields:
                        unchanged_count += 1
                        continue

                    old_status = asset.lifecycle_status
                    for field in changed_fields:
                        setattr(asset, field, values[field])
                    asset.save(update_fields=changed_fields + ["updated_at"])
                    LifecycleEvent.objects.create(
                        asset=asset,
                        event_type=LifecycleEvent.EventType.IMPORTED,
                        from_status=old_status,
                        to_status=asset.lifecycle_status,
                        reason="Updated from synthetic CSV import",
                        details={
                            "import_run_id": run.pk,
                            "source": source_path.name,
                            "changed_fields": changed_fields,
                        },
                    )
                    updated_count += 1
        except (DatabaseError, ValidationError, ValueError) as error:
            run.status = ImportRun.Status.FAILED
            run.rows_seen = len(rows)
            run.rows_rejected = len(rows)
            run.quality_summary = quality_summary
            run.error_summary = str(error)[:4000]
            run.completed_at = timezone.now()
            run.save(
                update_fields=(
                    "status",
                    "rows_seen",
                    "rows_rejected",
                    "quality_summary",
                    "error_summary",
                    "completed_at",
                )
            )
            raise CommandError(f"Import run {run.pk} failed: {error}") from error

        run.status = ImportRun.Status.SUCCEEDED
        run.rows_seen = len(rows)
        run.rows_created = created_count
        run.rows_updated = updated_count
        run.rows_unchanged = unchanged_count
        run.rows_rejected = 0
        run.quality_summary = quality_summary
        run.completed_at = timezone.now()
        run.save(
            update_fields=(
                "status",
                "rows_seen",
                "rows_created",
                "rows_updated",
                "rows_unchanged",
                "rows_rejected",
                "quality_summary",
                "completed_at",
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Import run {run.pk}: {created_count} created, "
                f"{updated_count} updated, {unchanged_count} unchanged, "
                f"{run.rows_rejected} rejected."
            )
        )

    @staticmethod
    def _record_failed_run(
        source_path: Path,
        source_hash: str,
        *,
        rows_seen: int,
        rows_rejected: int,
        error_summary: str,
        quality_summary: dict | None = None,
    ) -> None:
        ImportRun.objects.create(
            source_name=source_path.name,
            source_sha256=source_hash,
            status=ImportRun.Status.FAILED,
            rows_seen=rows_seen,
            rows_rejected=rows_rejected,
            quality_summary=quality_summary or {},
            error_summary=error_summary[:4000],
            completed_at=timezone.now(),
        )

    @staticmethod
    def _validate_rows(rows: list[dict[str, str]]) -> list[str]:
        errors: list[str] = []
        seen_ids: set[str] = set()
        valid_statuses = {value for value, _label in LifecycleStatus.choices}
        for row_number, row in enumerate(rows, start=2):
            initial_error_count = len(errors)
            asset_id = row.get("asset_id", "").strip()
            if not asset_id:
                errors.append(f"Row {row_number}: asset_id is required.")
            elif asset_id in seen_ids:
                errors.append(f"Row {row_number}: duplicate asset_id {asset_id}.")
            seen_ids.add(asset_id)
            if row.get("lifecycle_status") not in valid_statuses:
                errors.append(f"Row {row_number}: unsupported lifecycle status.")
            if row.get("sanitisation_required") not in {"true", "false"}:
                errors.append(f"Row {row_number}: sanitisation_required must be true or false.")
            if row.get("sanitisation_result", "") not in {"", "Passed", "Failed", "Pending"}:
                errors.append(f"Row {row_number}: unsupported sanitisation result.")
            for column in ("asset_type", "manufacturer", "model", "site", "department"):
                if not row.get(column, "").strip():
                    errors.append(f"Row {row_number}: {column} is required.")
            for column in ("purchase_date", "warranty_end", "last_updated"):
                try:
                    date.fromisoformat(row.get(column) or "")
                except (TypeError, ValueError):
                    errors.append(f"Row {row_number}: {column} must use ISO YYYY-MM-DD.")
            if row.get("return_due_date"):
                try:
                    date.fromisoformat(row["return_due_date"] or "")
                except (TypeError, ValueError):
                    errors.append(
                        f"Row {row_number}: return_due_date must use ISO YYYY-MM-DD."
                    )
            if len(errors) == initial_error_count:
                asset = Asset(**Command._convert_row(row))
                try:
                    # Keep source-quality exceptions available for profiling and review.
                    asset.clean_fields()
                except ValidationError as error:
                    for field, messages in error.message_dict.items():
                        errors.extend(
                            f"Row {row_number}: {field}: {message}"
                            for message in messages
                        )
        return errors

    @staticmethod
    def _convert_row(row: dict[str, str]) -> dict:
        try:
            return {
                "asset_id": row["asset_id"],
                "asset_type": row["asset_type"],
                "manufacturer": row["manufacturer"],
                "model": row["model"],
                "serial_ref": row["serial_ref"],
                "site": row["site"],
                "department": row["department"],
                "custodian_ref": row["custodian_ref"],
                "lifecycle_status": row["lifecycle_status"],
                "purchase_date": date.fromisoformat(row["purchase_date"]),
                "warranty_end": date.fromisoformat(row["warranty_end"]),
                "return_due_date": (
                    date.fromisoformat(row["return_due_date"])
                    if row["return_due_date"]
                    else None
                ),
                "sanitisation_required": row["sanitisation_required"] == "true",
                "sanitisation_result": row["sanitisation_result"],
                "sanitisation_evidence_ref": row["sanitisation_evidence_ref"],
                "disposal_evidence_ref": row["disposal_evidence_ref"],
                "source_last_updated": date.fromisoformat(row["last_updated"]),
            }
        except (KeyError, ValueError) as error:
            raise CommandError(f"Could not convert asset row {row.get('asset_id')}: {error}") from error
