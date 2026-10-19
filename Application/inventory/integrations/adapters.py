from __future__ import annotations

import os
from typing import Callable

from .contracts import IdentityStatus, IdentityStatusAdapter
from .scim import SCIMClient


class AdapterConfigurationError(Exception):
    """Raised when a provider adapter is missing or not configured safely."""


class SCIMIdentityAdapter:
    provider_id = "scim"

    def __init__(self, *, client: SCIMClient | None = None):
        if client is None:
            base_url = os.environ.get("SCIM_BASE_URL", "").strip()
            token = os.environ.get("SCIM_BEARER_TOKEN", "")
            if not base_url:
                raise AdapterConfigurationError("SCIM_BASE_URL is required.")
            if not token:
                raise AdapterConfigurationError("SCIM_BEARER_TOKEN is required.")
            client = SCIMClient(base_url=base_url, bearer_token=token)
        self.client = client

    def fetch_identity_statuses(self) -> list[IdentityStatus]:
        return [
            IdentityStatus(subject_id=user.subject_id, active=user.active)
            for user in self.client.list_users()
        ]


IdentityAdapterFactory = Callable[[], IdentityStatusAdapter]
IDENTITY_ADAPTERS: dict[str, IdentityAdapterFactory] = {
    SCIMIdentityAdapter.provider_id: SCIMIdentityAdapter,
}


def create_identity_adapter(provider_id: str) -> IdentityStatusAdapter:
    factory = IDENTITY_ADAPTERS.get(provider_id)
    if factory is None:
        supported = ", ".join(sorted(IDENTITY_ADAPTERS))
        raise AdapterConfigurationError(
            f"No verified adapter is enabled for {provider_id!r}. "
            f"Currently supported identity adapter(s): {supported}."
        )
    return factory()
