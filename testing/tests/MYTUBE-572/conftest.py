"""Pytest fixtures for MYTUBE-572 tests."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.frameworks.web.playwright.fixtures import browser  # noqa: F401
