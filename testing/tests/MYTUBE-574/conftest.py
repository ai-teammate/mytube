"""Pytest fixtures for MYTUBE-574 tests.

Browser lifecycle is managed through the shared framework fixture so that
the test file itself stays free of Playwright internals.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Re-export the shared browser fixture from the framework layer.
from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401
