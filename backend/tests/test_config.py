"""Tests for preventing accidental use of missing or blank secret settings."""
import os
import unittest
from unittest.mock import patch

from app.config import required_env


class RequiredEnvironmentTests(unittest.TestCase):
    def test_missing_setting_fails_without_a_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "JWT_SECRET must be configured"):
                required_env("JWT_SECRET")

    def test_blank_passwords_fail(self):
        for value in ("", "   ", "\t"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"ADMIN_PASSWORD": value}, clear=True):
                    with self.assertRaises(RuntimeError):
                        required_env("ADMIN_PASSWORD")

    def test_configured_value_is_returned_without_modification(self):
        with patch.dict(os.environ, {"ANALYST_PASSWORD": "  test-only-value  "}, clear=True):
            self.assertEqual(required_env("ANALYST_PASSWORD"), "  test-only-value  ")

    def test_error_does_not_include_another_secret(self):
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "test-only-private-value"}, clear=True):
            with self.assertRaises(RuntimeError) as error:
                required_env("JWT_SECRET")
            self.assertNotIn("test-only-private-value", str(error.exception))


if __name__ == "__main__":
    unittest.main()
