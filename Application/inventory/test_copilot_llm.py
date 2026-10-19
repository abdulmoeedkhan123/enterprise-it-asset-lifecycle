import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.test import SimpleTestCase

from .copilot_llm import (
    CopilotLLMError,
    CopilotLLMNotConfigured,
    propose_asset_intent,
    validate_asset_intent,
)
from .models import LifecycleStatus


class CopilotIntentValidationTests(SimpleTestCase):
    def test_accepts_only_bounded_read_only_intents(self):
        self.assertEqual(
            validate_asset_intent({"intent": "overdue_returns"}),
            {"intent": "overdue_returns"},
        )
        self.assertEqual(
            validate_asset_intent(
                {"intent": "lifecycle_status", "status": LifecycleStatus.ASSIGNED}
            ),
            {"intent": "lifecycle_status", "status": LifecycleStatus.ASSIGNED},
        )
        self.assertEqual(
            validate_asset_intent(
                {"intent": "asset_search", "term": " laptop ", "field": "model"}
            ),
            {"intent": "asset_search", "term": "laptop", "field": "model"},
        )

    def test_rejects_mutation_sql_unknown_fields_and_invalid_parameters(self):
        invalid_intents = (
            {"intent": "assign_asset", "asset_id": "AST-1"},
            {"intent": "overdue_returns", "sql": "DELETE FROM assets"},
            {"intent": "warranty_expiry", "days": True},
            {"intent": "warranty_expiry", "days": 366},
            {"intent": "lifecycle_status", "status": "Unknown"},
            {"intent": "asset_search", "term": "laptop", "field": "password"},
            {"intent": "asset_search", "term": "", "field": "any"},
            [],
        )
        for intent in invalid_intents:
            with self.subTest(intent=intent), self.assertRaises(CopilotLLMError):
                validate_asset_intent(intent)

    def test_provider_requires_explicit_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(CopilotLLMNotConfigured):
                propose_asset_intent("Find an asset by its model")

    @patch("inventory.copilot_llm.urlopen")
    def test_provider_gets_only_query_and_returns_validated_json_intent(
        self, mocked_urlopen
    ):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "asset_search",
                                    "term": "Laptop",
                                    "field": "asset_type",
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()
        mocked_urlopen.return_value = response
        with patch.dict(
            "os.environ",
            {"GROQ_API_KEY": "test-api-key"},
        ):
            intent = propose_asset_intent("Find laptops in inventory")

        request, = mocked_urlopen.call_args.args
        sent_payload = json.loads(request.data)
        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-api-key",
        )
        self.assertEqual(
            sent_payload["messages"][1]["content"],
            "Find laptops in inventory",
        )
        self.assertEqual(
            request.full_url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(sent_payload["model"], "openai/gpt-oss-20b")
        self.assertEqual(intent["intent"], "asset_search")
        self.assertNotIn("assets", sent_payload)

    @patch("inventory.copilot_llm.urlopen")
    def test_provider_http_error_is_explicit_and_does_not_expose_secret(
        self, mocked_urlopen
    ):
        mocked_urlopen.side_effect = HTTPError(
            "https://api.example.test/v1/chat/completions",
            503,
            "Unavailable",
            {},
            None,
        )
        with patch.dict(
            "os.environ",
            {"GROQ_API_KEY": "top-secret-test-token"},
        ):
            with self.assertRaises(CopilotLLMError) as raised:
                propose_asset_intent("Find laptops")

        self.assertIn("HTTP 503", str(raised.exception))
        self.assertNotIn("top-secret-test-token", str(raised.exception))

    @patch("inventory.copilot_llm.urlopen")
    def test_provider_rejects_malformed_completion_content(self, mocked_urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "not json"}}]}
        ).encode()
        mocked_urlopen.return_value = response
        with patch.dict(
            "os.environ",
            {"GROQ_API_KEY": "test-api-key"},
        ):
            with self.assertRaisesMessage(CopilotLLMError, "invalid intent document"):
                propose_asset_intent("Find laptops")
