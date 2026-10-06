"""Tests for search_app (placeholder module until OpenSearch is wired)."""

from __future__ import annotations

from django.apps import apps
from django.test import SimpleTestCase, TestCase


class SearchAppConfigTests(SimpleTestCase):
    def test_app_is_installed(self):
        self.assertTrue(apps.is_installed("search_app"))

    def test_app_config_name(self):
        config = apps.get_app_config("search_app")
        self.assertEqual(config.name, "search_app")


class SearchAppSmokeTests(TestCase):
    """
    Reserved for OpenSearch integration tests.
    Keeps a DB-backed smoke test so `manage.py test search_app` is meaningful.
    """

    def test_placeholder(self):
        self.assertTrue(True)
