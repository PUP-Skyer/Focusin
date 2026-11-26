import unittest

from tests import support
import app
import db

support.init_db()


class SettingsAPITests(unittest.TestCase):
    def setUp(self):
        db.reset()

    def test_settings_expose_readiness_without_plaintext_key(self):
        db.set_setting("llm_base_url", "https://example.test/v1")
        db.set_setting("llm_model", "demo-model")
        db.set_setting("llm_api_key", "super-secret")

        result = app.get_settings()

        self.assertTrue(result["has_key"])
        self.assertTrue(result["available"])
        self.assertNotIn("llm_api_key", result)
        self.assertNotIn("super-secret", str(result))

    def test_settings_are_not_ready_when_config_is_incomplete(self):
        db.set_setting("llm_api_key", "super-secret")

        result = app.get_settings()

        self.assertTrue(result["has_key"])
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main()
