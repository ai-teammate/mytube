"""UploadLayoutPage — component for verifying the upload page responsive grid layout.

Encapsulates the local HTML fixture server, viewport management, and CSS
computed-style retrieval used by MYTUBE-506 layout tests.

Architecture notes
------------------
- Provides a self-contained HTML fixture replicating the upload.module.css
  workspace block, served by a Python HTTPServer so no Firebase auth is needed.
- Tests receive an UploadLayoutPage instance from a pytest fixture and call
  only semantic methods; no raw Playwright APIs in test code.
- WorkspaceStyles is a dataclass with computed column_count derived from the
  resolved grid-template-columns string.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from playwright.sync_api import Page

# ---------------------------------------------------------------------------
# HTML fixture — exact copy of the workspace CSS from upload.module.css
# ---------------------------------------------------------------------------

FIXTURE_HTML: str = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Upload layout fixture</title>
  <style>
    /* Exact copy of upload.module.css .workspace block */
    .workspace {
      display: grid;
      grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
      padding: 20px;
    }

    @media (max-width: 639px) {
      .workspace {
        grid-template-columns: 1fr;
      }
    }

    /* Minimal children to make the grid concrete */
    .upload-card {
      background: #f5f5f5;
      min-height: 200px;
      padding: 16px;
    }
    .library-area {
      background: #e8e8e8;
      min-height: 200px;
      padding: 16px;
    }
  </style>
</head>
<body>
  <div class="workspace" data-testid="workspace">
    <div class="upload-card" data-testid="upload-card">Upload card</div>
    <div class="library-area" data-testid="library-area">Library area</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP server helpers
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the single HTML fixture for every GET request."""

    def do_GET(self) -> None:  # noqa: N802
        body = FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # suppress server noise
        pass


def start_fixture_server() -> tuple[HTTPServer, str]:
    """Start the local fixture server on a free port and return ``(server, url)``.

    The server runs in a daemon thread and must be shut down explicitly by
    calling ``server.shutdown()`` when done (e.g. in a pytest fixture teardown).
    """
    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WorkspaceStyles:
    """Computed CSS properties of the ``.workspace`` grid container."""

    display: str
    grid_template_columns: str
    column_gap: str

    @property
    def column_count(self) -> int:
        """Number of resolved column tracks in ``grid_template_columns``."""
        return len(self.grid_template_columns.split())


@dataclass
class ElementBounds:
    """Rendered bounding box of a DOM element (from getBoundingClientRect)."""

    top: float
    left: float
    width: float
    height: float


# ---------------------------------------------------------------------------
# Page component
# ---------------------------------------------------------------------------

_GET_WORKSPACE_STYLES_JS = """
() => {
    const el = document.querySelector('[data-testid="workspace"]');
    if (!el) return null;
    const cs = window.getComputedStyle(el);
    return {
        display: cs.display,
        gridTemplateColumns: cs.gridTemplateColumns,
        columnGap: cs.columnGap
    };
}
"""


class UploadLayoutPage:
    """Component for the upload workspace layout fixture page.

    Wraps a Playwright ``Page`` loaded with the local HTML fixture and exposes
    semantic methods for asserting CSS grid behaviour at different viewports.

    Parameters
    ----------
    page:
        A Playwright ``Page`` that has already navigated to the fixture URL.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_workspace_styles(self) -> WorkspaceStyles:
        """Return the computed CSS grid properties of the workspace container.

        Raises ``AssertionError`` when the ``[data-testid="workspace"]`` element
        is not found on the page.
        """
        raw = self._page.evaluate(_GET_WORKSPACE_STYLES_JS)
        assert raw is not None, (
            "Could not find [data-testid='workspace'] element on the fixture page. "
            f"URL: {self._page.url}"
        )
        return WorkspaceStyles(
            display=raw["display"],
            grid_template_columns=raw["gridTemplateColumns"],
            column_gap=raw["columnGap"],
        )

    def get_element_bounds(self, testid: str) -> Optional[ElementBounds]:
        """Return the rendered bounding box of the element with *testid*.

        Returns ``None`` when the element is not found in the DOM.

        Parameters
        ----------
        testid:
            Value of the ``data-testid`` attribute to look up.
        """
        raw = self._page.evaluate(
            """(tid) => {
                const el = document.querySelector('[data-testid="' + tid + '"]');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return { top: r.top, left: r.left, width: r.width, height: r.height };
            }""",
            testid,
        )
        if raw is None:
            return None
        return ElementBounds(
            top=raw["top"],
            left=raw["left"],
            width=raw["width"],
            height=raw["height"],
        )
