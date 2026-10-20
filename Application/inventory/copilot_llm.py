from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .copilot import MAX_QUERY_LENGTH
from .models import LifecycleStatus


DEFAULT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
ALLOWED_SEARCH_FIELDS = {
    "asset_id",
    "asset_type",
    "manufacturer",
    "model",
    "serial_ref",
    "site",
    "department",
    "custodian_ref",
}


class CopilotLLMError(Exception):
    """Raised when LLM intent proposal or validation fails."""


class CopilotLLMNotConfigured(CopilotLLMError):
    """Raised when an LLM provider is not enabled."""


def propose_asset_intent(query: str, *, timeout: float = 15) -> dict | None:
    """Ask a configured LLM for a constrained intent; never send inventory records."""
    if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
        raise CopilotLLMError("The question is empty or exceeds the supported length.")
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get(
        "COPILOT_LLM_API_KEY", ""
    )
    if not api_key:
        raise CopilotLLMNotConfigured("LLM assistance is not configured.")
    endpoint = os.environ.get("COPILOT_LLM_API_URL", DEFAULT_ENDPOINT).strip()
    model = os.environ.get("COPILOT_LLM_MODEL", DEFAULT_MODEL).strip()
    parsed_endpoint = urlsplit(endpoint)
    if (
        parsed_endpoint.scheme != "https"
        or not parsed_endpoint.hostname
        or parsed_endpoint.username
        or parsed_endpoint.password
        or parsed_endpoint.fragment
    ):
        raise CopilotLLMError("COPILOT_LLM_API_URL must be an HTTPS endpoint.")
    if len(api_key) > 4096 or not model or len(model) > 128:
        raise CopilotLLMError("LLM configuration exceeds supported limits.")

    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Classify the user's asset inventory question as one read-only "
                    "intent. Return only JSON with exactly the allowed fields. "
                    "Never return SQL, code, tools, actions, or explanations. "
                    "Allowed shapes: {\"intent\":\"overdue_returns\"}; "
                    "{\"intent\":\"warranty_expiry\",\"days\":30}; "
                    "{\"intent\":\"lifecycle_status\",\"status\":\"Assigned\"}; "
                    "{\"intent\":\"asset_search\",\"term\":\"laptop\","
                    "\"field\":\"model\"}. Search fields are asset_id, asset_type, "
                    "manufacturer, model, serial_ref, site, department, custodian_ref, "
                    "or any. Lifecycle status must be one of the stored application "
                    "statuses. Use a default 60 days for unspecified warranty windows. "
                    "Read-only Intune intents are also allowed: "
                    "{\"intent\":\"intune_devices\"}; "
                    "{\"intent\":\"intune_noncompliant\"}; "
                    "{\"intent\":\"intune_match_review\",\"status\":\"unmatched\"} "
                    "or status duplicate; {\"intent\":\"intune_snapshot_status\"}. "
                    "Do not infer or invent device data. These intents only query the saved "
                    "local Intune snapshot, never Microsoft Graph live."
                ),
            },
            {"role": "user", "content": query.strip()},
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_response = response.read(65537)
        if len(raw_response) > 65536:
            raise CopilotLLMError("LLM provider response exceeded the 64 KiB safety limit.")
        response_payload = json.loads(raw_response)
    except HTTPError as error:
        raise CopilotLLMError(
            f"LLM provider request failed with HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        # Do not surface provider URLs, request details, or transport internals to users.
        raise CopilotLLMError("LLM provider request failed due to a network or timeout error.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CopilotLLMError("LLM provider returned invalid JSON.") from error

    if not isinstance(response_payload, dict):
        raise CopilotLLMError("LLM provider response must be a JSON object.")
    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise CopilotLLMError("LLM provider response has no completion choice.")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise CopilotLLMError("LLM provider response has no JSON intent.")
    try:
        intent = json.loads(content)
    except json.JSONDecodeError as error:
        raise CopilotLLMError("LLM provider returned an invalid intent document.") from error
    return validate_asset_intent(intent)


def validate_asset_intent(value: object) -> dict | None:
    """Accept only exact, bounded read-only intent documents."""
    if not isinstance(value, dict):
        raise CopilotLLMError("LLM intent must be a JSON object.")
    intent = value.get("intent")
    allowed_shapes = {
        "overdue_returns": {"intent"},
        "warranty_expiry": {"intent", "days"},
        "lifecycle_status": {"intent", "status"},
        "asset_search": {"intent", "term", "field"},
        "intune_devices": {"intent"},
        "intune_noncompliant": {"intent"},
        "intune_snapshot_status": {"intent"},
        "intune_match_review": {"intent", "status"},
    }
    if (
        not isinstance(intent, str)
        or intent not in allowed_shapes
        or set(value) != allowed_shapes[intent]
    ):
        raise CopilotLLMError("LLM returned an unsupported or over-specified intent.")
    if intent == "warranty_expiry":
        days = value["days"]
        if type(days) is not int or not 1 <= days <= 365:
            raise CopilotLLMError("Warranty intent days must be an integer from 1 to 365.")
    elif intent == "lifecycle_status":
        if value["status"] not in LifecycleStatus.values:
            raise CopilotLLMError("LLM returned an invalid lifecycle status.")
    elif intent == "intune_match_review":
        if not isinstance(value["status"], str) or value["status"] not in {"unmatched", "duplicate"}:
            raise CopilotLLMError("Intune match review status must be unmatched or duplicate.")
    elif intent == "asset_search":
        term = value["term"]
        field = value["field"]
        if (
            not isinstance(term, str)
            or not term.strip()
            or len(term) > 100
            or any(ord(character) < 32 for character in term)
        ):
            raise CopilotLLMError("Asset search term is empty or too long.")
        if (
            not isinstance(field, str)
            or field != "any"
            and field not in ALLOWED_SEARCH_FIELDS
        ):
            raise CopilotLLMError("LLM returned an unsupported asset search field.")
        return {**value, "term": term.strip()}
    return value
