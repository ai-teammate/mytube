"""Conftest for MYTUBE-602 tests.

Re-exports the shared Playwright ``browser`` fixture from the framework layer
so that test files in this folder do not need to instantiate sync_playwright
directly.
"""
from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401
