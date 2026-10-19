from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IdentityStatus:
    subject_id: str
    active: bool


class IdentityStatusAdapter(Protocol):
    provider_id: str

    def fetch_identity_statuses(self) -> list[IdentityStatus]:
        """Fetch the minimum identity status data required by the workflow."""
