from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.utils.dateparse import parse_datetime


GRAPH_API_ROOT = "https://graph.microsoft.com/v1.0"
GRAPH_DEVICES_PATH = "/deviceManagement/managedDevices"
GRAPH_DEVICES_URL_PATH = f"/v1.0{GRAPH_DEVICES_PATH}"
MAX_PAGES = 500


class IntuneError(Exception):
    """Raised when an Intune Graph read cannot safely complete."""


class IntuneConfigurationError(IntuneError):
    """Raised when the read-only Graph client is not configured."""


@dataclass(frozen=True)
class ManagedDevice:
    managed_device_id: str
    device_name: str
    serial_number: str
    manufacturer: str
    model: str
    operating_system: str
    os_version: str
    compliance_state: str
    last_sync_at: datetime | None


class IntuneGraphClient:
    def __init__(self, *, access_token: str, timeout: float = 20):
        if not access_token:
            raise IntuneConfigurationError("Microsoft Graph access token is required.")
        self.access_token = access_token
        self.timeout = timeout

    @classmethod
    def from_environment(cls, *, timeout: float = 20) -> IntuneGraphClient:
        tenant_id = os.environ.get("INTUNE_TENANT_ID", "").strip()
        client_id = os.environ.get("INTUNE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("INTUNE_CLIENT_SECRET", "")
        if not tenant_id or not client_id or not client_secret:
            raise IntuneConfigurationError(
                "INTUNE_TENANT_ID, INTUNE_CLIENT_ID, and INTUNE_CLIENT_SECRET are required."
            )
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,128}", tenant_id):
            raise IntuneConfigurationError("INTUNE_TENANT_ID has an invalid format.")
        if len(client_id) > 128 or len(client_secret) > 4096:
            raise IntuneConfigurationError("Intune client credentials exceed allowed limits.")
        token = cls._acquire_token(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            timeout=timeout,
        )
        return cls(access_token=token, timeout=timeout)

    @staticmethod
    def _acquire_token(
        *, tenant_id: str, client_id: str, client_secret: str, timeout: float
    ) -> str:
        token_url = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        payload = urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        ).encode("utf-8")
        request = Request(
            token_url,
            data=payload,
            headers={"Accept": "application/json"},
            method="POST",
        )
        response_payload = IntuneGraphClient._request_json(request, timeout=timeout)
        token = response_payload.get("access_token")
        if not isinstance(token, str) or not token.strip():
            raise IntuneError("Microsoft identity platform returned no access token.")
        return token

    def list_managed_devices(self) -> list[ManagedDevice]:
        query = urlencode(
            {
                "$select": (
                    "id,deviceName,serialNumber,manufacturer,model,operatingSystem,"
                    "osVersion,complianceState,lastSyncDateTime"
                ),
                "$top": "100",
            }
        )
        next_url = f"{GRAPH_API_ROOT}{GRAPH_DEVICES_PATH}?{query}"
        devices: list[ManagedDevice] = []
        seen_ids: set[str] = set()
        pages = 0

        while next_url:
            pages += 1
            if pages > MAX_PAGES:
                raise IntuneError("Microsoft Graph pagination exceeded the safety limit.")
            self._validate_next_url(next_url)
            request = Request(
                next_url,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
                method="GET",
            )
            payload = self._request_json(request, timeout=self.timeout)
            values = payload.get("value")
            if not isinstance(values, list):
                raise IntuneError("Microsoft Graph response is missing the device list.")
            for value in values:
                device = self._parse_device(value)
                if device.managed_device_id in seen_ids:
                    raise IntuneError("Microsoft Graph returned a duplicate managed-device ID.")
                seen_ids.add(device.managed_device_id)
                devices.append(device)
            next_url = payload.get("@odata.nextLink", "")
            if not isinstance(next_url, str):
                raise IntuneError("Microsoft Graph returned an invalid pagination link.")
        return devices

    @staticmethod
    def _validate_next_url(url: str) -> None:
        try:
            parsed = urlsplit(url)
            safe_url = (
                parsed.scheme == "https"
                and parsed.hostname == "graph.microsoft.com"
                and parsed.port in (None, 443)
                and not parsed.username
                and not parsed.password
                and parsed.path.rstrip("/") == GRAPH_DEVICES_URL_PATH
                and not parsed.fragment
            )
        except ValueError:
            safe_url = False
        if not safe_url:
            raise IntuneError("Microsoft Graph returned an unsafe managed-device pagination URL.")

    @staticmethod
    def _parse_device(value: object) -> ManagedDevice:
        if not isinstance(value, dict):
            raise IntuneError("Microsoft Graph returned an invalid managed-device record.")
        managed_device_id = value.get("id")
        if (
            not isinstance(managed_device_id, str)
            or not managed_device_id.strip()
            or len(managed_device_id) > 128
        ):
            raise IntuneError("Managed-device record has an invalid ID.")

        def text_field(name: str, max_length: int, *, required: bool = False) -> str:
            result = value.get(name, "")
            if result is None and not required:
                return ""
            if (
                not isinstance(result, str)
                or len(result) > max_length
                or required and not result.strip()
            ):
                raise IntuneError(f"Managed-device record has an invalid {name} value.")
            return result.strip()

        last_sync_value = value.get("lastSyncDateTime")
        if last_sync_value in (None, ""):
            last_sync_at = None
        elif isinstance(last_sync_value, str):
            last_sync_at = parse_datetime(last_sync_value)
            if last_sync_at is None or last_sync_at.utcoffset() is None:
                raise IntuneError("Managed-device record has an invalid lastSyncDateTime.")
        else:
            raise IntuneError("Managed-device record has an invalid lastSyncDateTime.")

        return ManagedDevice(
            managed_device_id=managed_device_id.strip(),
            device_name=text_field("deviceName", 255),
            serial_number=text_field("serialNumber", 128),
            manufacturer=text_field("manufacturer", 128),
            model=text_field("model", 128),
            operating_system=text_field("operatingSystem", 64),
            os_version=text_field("osVersion", 64),
            compliance_state=text_field("complianceState", 32),
            last_sync_at=last_sync_at,
        )

    @staticmethod
    def _request_json(request: Request, *, timeout: float) -> dict:
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            raise IntuneError(
                f"Microsoft Graph request failed with HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            reason = error.reason if isinstance(error, URLError) else error
            raise IntuneError(f"Microsoft Graph request failed: {reason}.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IntuneError("Microsoft Graph returned invalid JSON.") from error
        if not isinstance(payload, dict):
            raise IntuneError("Microsoft Graph response must be a JSON object.")
        return payload
