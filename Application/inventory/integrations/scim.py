from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class SCIMError(Exception):
    """Raised when a SCIM list request cannot be safely completed."""


@dataclass(frozen=True)
class SCIMIdentity:
    subject_id: str
    active: bool


class SCIMClient:
    def __init__(
        self,
        *,
        base_url: str,
        bearer_token: str,
        page_size: int = 100,
        timeout: float = 20,
    ):
        parsed_url = urlsplit(base_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise SCIMError("SCIM_BASE_URL must be an absolute HTTPS URL.")
        if parsed_url.username or parsed_url.password:
            raise SCIMError("SCIM_BASE_URL must not contain embedded credentials.")
        if parsed_url.query or parsed_url.fragment:
            raise SCIMError("SCIM_BASE_URL must not contain a query or fragment.")
        if not bearer_token:
            raise SCIMError("SCIM bearer token is required.")
        if page_size < 1:
            raise SCIMError("SCIM page size must be positive.")
        self.users_url = urlunsplit(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip("/") + "/Users", "", "")
        )
        self.bearer_token = bearer_token
        self.page_size = page_size
        self.timeout = timeout

    def list_users(self) -> list[SCIMIdentity]:
        identities: list[SCIMIdentity] = []
        seen_subject_ids: set[str] = set()
        start_index = 1
        total_results: int | None = None

        while total_results is None or start_index <= total_results:
            query = urlencode(
                {
                    "attributes": "id,active",
                    "startIndex": start_index,
                    "count": self.page_size,
                }
            )
            request = Request(
                f"{self.users_url}?{query}",
                headers={
                    "Accept": "application/scim+json",
                    "Authorization": f"Bearer {self.bearer_token}",
                },
            )
            payload = self._get_page(request)
            resources = payload.get("Resources")
            response_total = payload.get("totalResults")
            if not isinstance(resources, list) or type(response_total) is not int:
                raise SCIMError("SCIM response is missing Resources or totalResults.")
            if (
                response_total < 0
                or len(resources) > self.page_size
                or not resources
                and start_index <= response_total
            ):
                raise SCIMError("SCIM response has invalid pagination data.")
            if total_results is not None and total_results != response_total:
                raise SCIMError("SCIM totalResults changed while reading paginated results.")
            total_results = response_total

            for resource in resources:
                if not isinstance(resource, dict):
                    raise SCIMError("SCIM response contains an invalid user resource.")
                subject_id = resource.get("id")
                active = resource.get("active")
                if not isinstance(subject_id, str) or not subject_id.strip():
                    raise SCIMError("SCIM user resource is missing a valid id.")
                if not isinstance(active, bool):
                    raise SCIMError("SCIM user resource is missing a boolean active value.")
                if subject_id in seen_subject_ids:
                    raise SCIMError("SCIM response contains a duplicate user id.")
                seen_subject_ids.add(subject_id)
                identities.append(SCIMIdentity(subject_id=subject_id, active=active))

            start_index += len(resources)

        return identities

    def _get_page(self, request: Request) -> dict:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            raise SCIMError(f"SCIM request failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise SCIMError(f"SCIM request failed: {error.reason if isinstance(error, URLError) else error}.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SCIMError("SCIM server returned invalid JSON.") from error

        if not isinstance(payload, dict):
            raise SCIMError("SCIM response must be a JSON object.")
        return payload
