from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ApplicationSettingsTests(TestCase):
    def setUp(self):
        self.staff_user = get_user_model().objects.create_user(
            username="settings-staff",
            password="not-a-real-secret",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def test_settings_page_requires_staff_access(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("inventory:application-settings")).status_code,
            302,
        )

        regular_user = get_user_model().objects.create_user(
            username="settings-regular",
            password="not-a-real-secret",
        )
        self.client.force_login(regular_user)
        self.assertEqual(
            self.client.get(reverse("inventory:application-settings")).status_code,
            403,
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_settings_page_shows_missing_status_without_secrets(self):
        response = self.client.get(reverse("inventory:application-settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not configured")
        self.assertContains(response, "Incomplete configuration")
        self.assertContains(response, "GROQ_API_KEY")
        self.assertContains(response, "INTUNE_CLIENT_SECRET")
        self.assertNotContains(response, "client-secret")
        self.assertNotContains(response, "access-token")

    @patch.dict(
        "os.environ",
        {
            "GROQ_API_KEY": "copilot-test-secret",
            "COPILOT_LLM_MODEL": "test-model",
            "COPILOT_LLM_API_URL": "https://llm.example.test/v1/chat/completions",
            "INTUNE_TENANT_ID": "tenant-test-id",
            "INTUNE_CLIENT_ID": "intune-test-client-id",
            "INTUNE_CLIENT_SECRET": "intune-test-secret",
        },
        clear=True,
    )
    def test_configured_status_never_discloses_environment_values(self):
        response = self.client.get(reverse("inventory:application-settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Credentials present")
        self.assertContains(response, "Configured")
        self.assertContains(response, "test-model")
        self.assertContains(response, "Custom HTTPS endpoint configured")
        for secret in (
            "copilot-test-secret",
            "tenant-test-id",
            "intune-test-client-id",
            "intune-test-secret",
            "llm.example.test",
        ):
            with self.subTest(secret=secret):
                self.assertNotContains(response, secret)
