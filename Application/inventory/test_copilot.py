from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Asset, LifecycleStatus
from .copilot import run_copilot_query
from .copilot_llm import CopilotLLMError


class CopilotQueryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="copilot-user",
            password="test-password",
        )
        self.view_permission = Permission.objects.get(
            content_type__app_label="inventory",
            codename="view_asset",
        )
        self.client.force_login(self.user)

    def create_asset(self, **overrides):
        values = {
            "asset_id": "AST-1001",
            "asset_type": "Laptop",
            "manufacturer": "Example",
            "model": "Business Laptop",
            "site": "Sydney",
            "department": "IT",
            "lifecycle_status": LifecycleStatus.ASSIGNED,
            "custodian_ref": "EMP-1001",
            "purchase_date": date(2024, 1, 1),
            "warranty_end": date(2027, 1, 1),
            "source_last_updated": date(2026, 1, 1),
        }
        values.update(overrides)
        return Asset.objects.create(**values)

    def test_copilot_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("inventory:copilot"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_copilot_requires_asset_view_permission(self):
        response = self.client.get(reverse("inventory:copilot"))
        self.assertEqual(response.status_code, 403)

    def test_overdue_return_query_only_returns_overdue_return_pending_assets(self):
        today = date(2026, 10, 20)
        overdue = self.create_asset(
            asset_id="AST-OVERDUE",
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=today - timedelta(days=2),
        )
        self.create_asset(
            asset_id="AST-NOT-DUE",
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=today + timedelta(days=2),
        )

        result = run_copilot_query("Show overdue returns", today=today)

        self.assertEqual(result["intent"], "overdue_returns")
        self.assertEqual([asset.pk for asset in result["assets"]], [overdue.pk])
        self.assertTrue(result["read_only"])

    def test_warranty_query_defaults_to_60_days_and_excludes_disposed_assets(self):
        today = date(2026, 10, 20)
        soon = self.create_asset(
            asset_id="AST-WARRANTY-SOON",
            lifecycle_status=LifecycleStatus.IN_STOCK,
            custodian_ref="",
            warranty_end=today + timedelta(days=30),
        )
        self.create_asset(
            asset_id="AST-DISPOSED",
            lifecycle_status=LifecycleStatus.DISPOSED,
            custodian_ref="",
            warranty_end=today + timedelta(days=20),
            disposal_evidence_ref="DISP-REF",
        )

        result = run_copilot_query("Show warranties expiring soon", today=today)

        self.assertEqual(result["intent"], "warranty_expiry")
        self.assertEqual([asset.pk for asset in result["assets"]], [soon.pk])
        self.assertEqual(result["metadata"]["days"], 60)

    def test_asset_identifier_lookup_matches_exact_identifier(self):
        asset = self.create_asset(asset_id="AST-2002")

        result = run_copilot_query("Find asset AST-2002", today=date(2026, 10, 20))

        self.assertEqual(result["intent"], "asset_lookup")
        self.assertEqual([item.pk for item in result["assets"]], [asset.pk])

    def test_unsupported_query_does_not_change_asset(self):
        asset = self.create_asset()
        before = asset.lifecycle_status

        result = run_copilot_query("Please assign this laptop to another employee")

        asset.refresh_from_db()
        self.assertEqual(result["intent"], "unsupported")
        self.assertEqual(asset.lifecycle_status, before)

    def test_copilot_post_renders_read_only_results(self):
        self.user.user_permissions.add(self.view_permission)
        self.create_asset(
            asset_id="AST-OVERDUE",
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=date(2026, 10, 19),
        )

        response = self.client.post(
            reverse("inventory:copilot"),
            {"query": "Show overdue returns"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Read-only beta")
        self.assertContains(response, "AST-OVERDUE")

    @patch("inventory.views.propose_asset_intent")
    def test_natural_language_intent_uses_llm_proposal_but_python_executes_search(
        self, propose_intent
    ):
        self.user.user_permissions.add(self.view_permission)
        asset = self.create_asset(
            asset_id="AST-NATURAL-1",
            manufacturer="Northwind Devices",
        )
        propose_intent.return_value = {
            "intent": "asset_search",
            "term": "Northwind",
            "field": "manufacturer",
        }

        response = self.client.post(
            reverse("inventory:copilot"),
            {"query": "Find our Northwind laptops"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result"]["source"], "llm")
        self.assertEqual(
            [result.pk for result in response.context["result"]["assets"]],
            [asset.pk],
        )
        self.assertTrue(response.context["result"]["read_only"])
        propose_intent.assert_called_once_with("Find our Northwind laptops")

    @patch("inventory.views.propose_asset_intent")
    def test_copilot_displays_provider_failure_without_changing_records(
        self, propose_intent
    ):
        self.user.user_permissions.add(self.view_permission)
        asset = self.create_asset()
        propose_intent.side_effect = CopilotLLMError(
            "LLM provider request failed with HTTP 503."
        )

        response = self.client.post(
            reverse("inventory:copilot"),
            {"query": "Find devices allocated to our regional office"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI interpretation failed")
        self.assertContains(response, "HTTP 503")
        asset.refresh_from_db()
        self.assertEqual(asset.lifecycle_status, LifecycleStatus.ASSIGNED)

    @patch("inventory.views.propose_asset_intent")
    def test_supported_deterministic_question_does_not_call_llm(self, propose_intent):
        self.user.user_permissions.add(self.view_permission)
        self.create_asset(
            lifecycle_status=LifecycleStatus.RETURN_PENDING,
            return_due_date=date(2026, 10, 19),
        )

        response = self.client.post(
            reverse("inventory:copilot"),
            {"query": "Show overdue returns"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["result"]["source"], "deterministic")
        propose_intent.assert_not_called()

    @patch("inventory.views.propose_asset_intent")
    def test_copilot_post_requires_asset_view_permission(self, propose_intent):
        response = self.client.post(
            reverse("inventory:copilot"),
            {"query": "Find my laptop"},
        )
        self.assertEqual(response.status_code, 403)
        propose_intent.assert_not_called()
