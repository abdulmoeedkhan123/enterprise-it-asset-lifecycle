from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from inventory.integrations.intune import IntuneError
from inventory.integrations.intune_sync import run_intune_sync


class Command(BaseCommand):
    help = "Read Intune managed devices from Microsoft Graph and review serial matches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-read-only-authorized",
            action="store_true",
            help="Confirm that this read-only device sync is authorized.",
        )

    def handle(self, *args, **options):
        if not options["confirm_read_only_authorized"]:
            raise CommandError(
                "Intune sync requires --confirm-read-only-authorized. Obtain "
                "organization approval for the Graph DeviceManagementManagedDevices.Read.All "
                "application permission before syncing."
            )
        try:
            run = run_intune_sync()
        except (IntuneError, DatabaseError) as error:
            raise CommandError(f"Intune sync failed: {error}") from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Intune run {run.pk}: received {run.records_received} devices, "
                f"matched {run.devices_matched}, flagged {run.devices_duplicate} "
                f"duplicate serials, left {run.devices_unmatched} unmatched."
            )
        )
