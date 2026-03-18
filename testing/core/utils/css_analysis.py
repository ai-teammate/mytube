"""Shared CSS analysis utilities for static CSS token tests.

These helpers parse raw CSS text to verify that design tokens (CSS custom
properties) are used instead of hardcoded colour values, and to build
self-contained HTML fixture pages for computed-style tests.
"""
from __future__ import annotations

import pathlib
import re

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_CONTENT_CSS = _REPO_ROOT / "web" / "src" / "app" / "dashboard" / "_content.module.css"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"


def read_css(path: pathlib.Path) -> str:
    """Return the text content of a CSS file."""
    return path.read_text(encoding="utf-8")


def get_rule_body(css_text: str, selector: str) -> str:
    """Return the rule body for the given CSS class selector.

    Matches ``.selector { ... }`` and handles multi-line bodies.
    Returns an empty string when the selector is not found.
    """
    pattern = re.compile(
        r"\." + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = pattern.search(css_text)
    return m.group(1) if m else ""


def rule_contains(css_text: str, selector: str, token: str) -> bool:
    """Return True when *token* appears in the rule body for *selector*."""
    body = get_rule_body(css_text, selector)
    return token in body


def build_dark_theme_fixture(
    globals_css_path: pathlib.Path = _GLOBALS_CSS,
    content_css_path: pathlib.Path = _CONTENT_CSS,
) -> str:
    """Return a self-contained HTML page with dark theme, modal card, and playlist table.

    Embeds the actual ``globals.css`` and ``_content.module.css`` so that CSS
    variables resolve through Playwright's ``getComputedStyle``.
    """
    globals_css = read_css(globals_css_path)
    content_css = read_css(content_css_path)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Dashboard Dark Theme Fixture MYTUBE-602</title>\n"
        "  <style>" + globals_css + "</style>\n"
        "  <style>" + content_css + "</style>\n"
        "</head>\n"
        "<body data-theme=\"dark\">\n"
        "  <!-- Edit Video modal -->\n"
        "  <div class=\"modalCard\" id=\"modal-card\"\n"
        "       role=\"dialog\" aria-modal=\"true\">\n"
        "    <h2 class=\"modalTitle\">Edit Video</h2>\n"
        "  </div>\n"
        "  <!-- Playlist management table wrapper -->\n"
        "  <div class=\"playlistTable\" id=\"playlist-table\">\n"
        "    <table class=\"playlistTableEl\">\n"
        "      <thead>\n"
        "        <tr class=\"playlistTableHead\">\n"
        "          <th class=\"playlistTableHeadCell\">Name</th>\n"
        "          <th class=\"playlistTableHeadCell\">Date</th>\n"
        "          <th class=\"playlistTableHeadCell\">Actions</th>\n"
        "        </tr>\n"
        "      </thead>\n"
        "      <tbody>\n"
        "        <tr class=\"playlistTableRow\">\n"
        "          <td class=\"playlistTableCellTitle\">My Playlist</td>\n"
        "          <td class=\"playlistTableCellDate\">Jan 1, 2026</td>\n"
        "          <td class=\"playlistTableCellActions\">Rename</td>\n"
        "        </tr>\n"
        "      </tbody>\n"
        "    </table>\n"
        "  </div>\n"
        "</body>\n"
        "</html>"
    )
