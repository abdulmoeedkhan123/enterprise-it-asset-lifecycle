from __future__ import annotations

import hashlib

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.utils import timezone

from inventory.integrations.adapters import (
    AdapterConfigurationError,
    create_identity_adapter,
)
from inventory.integrations.scim import SCIMError
from inventory.models import (
    Asset,
    IdentityLink,
    IntegrationRun,
    LifecycleStatus,
    ReturnWorkItem,
)


class Command(BaseCommand):
    help = "Read SCIM user status and create return-review work items for inactive mapped users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-read-only-authorized",
            action="store_true",
            help="Confirm that this read-only identity sync is authorized.",
        )

    def handle(self, *args, **options):
        if not options["confirm_read_only_authorized"]:
            raise CommandError(
                "SCIM sync requires --confirm-read-only-authorized. Obtain identity "
                "owner approval and use an approved read-only SCIM credential."
            )

        run = IntegrationRun.objects.create(
            provider="scim",
            status=IntegrationRun.Status.RUNNING,
        )
        try:
            adapter = create_identity_adapter("scim")
            identities = adapter.fetch_identity_statuses()
            matched_count = 0
            created_count = 0
            existing_count = 0
            unmatched_count = 0
            with transaction.atomic():
                for identity in identities:
                    if identity.active:
                        continue
                    mapping = IdentityLink.objects.filter(
                        provider="scim",
                        external_subject_id=identity.subject_id,
                    ).first()
                    if mapping is None:
                        unmatched_count += 1
                        continue

                    matched_count += 1
                    assets = Asset.objects.filter(
                        custodian_ref=mapping.custodian_ref,
                        lifecycle_status=LifecycleStatus.ASSIGNED,
                    )
                    for asset in assets:
                        item_key = hashlib.sha256(
                            f"scim\0{identity.subject_id}\0{asset.pk}".encode("utf-8")
                        ).hexdigest()
                        _item, created = ReturnWorkItem.objects.get_or_create(
                            source_event_id=f"scim-inactive:{item_key}",
                            defaults={
                                "asset": asset,
                                "source_provider": "scim",
                                "custodian_ref": mapping.custodian_ref,
                            },
                        )
                        if created:
                            created_count += 1
                        else:
                            existing_count += 1

            run.status = IntegrationRun.Status.SUCCEEDED
            run.records_received = len(identities)
            run.identities_matched = matched_count
            run.identities_unmatched = unmatched_count
            run.work_items_created = created_count
            run.work_items_existing = existing_count
            run.completed_at = timezone.now()
            run.save(
                update_fields=(
                    "status",
                    "records_received",
                    "identities_matched",
                    "identities_unmatched",
                    "work_items_created",
                    "work_items_existing",
                    "completed_at",
                )
            )
        except (AdapterConfigurationError, SCIMError, DatabaseError) as error:
            run.status = IntegrationRun.Status.FAILED
            run.error_summary = str(error)[:500]
            run.completed_at = timezone.now()
            run.save(update_fields=("status", "error_summary", "completed_at"))
            raise CommandError(f"SCIM sync run {run.pk} failed: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"SCIM run {run.pk}: received {run.records_received} identities, "
                f"matched {matched_count}, created {created_count} return-review items, "
                f"found {existing_count} existing items, and left "
                f"{unmatched_count} inactive identities unmapped."
            )
        )
