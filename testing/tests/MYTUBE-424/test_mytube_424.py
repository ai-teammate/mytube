"""
MYTUBE-424: LogoIcon component — rendered as SVG with correct viewBox and attributes

Objective
---------
Verify the LogoIcon component renders the correct SVG structure, dimensions,
and color attributes.

Steps
-----
1. Render LogoIcon.tsx to static HTML using ReactDOMServer.renderToStaticMarkup
   so the fixture always reflects the *current* component source.
2. Serve the rendered HTML via a local HTTP server.
3. Open the page in a Playwright browser.
4. Inspect the rendered DOM element via LogoIconPage.

Expected Result
---------------
The component renders an <svg> element with viewBox="0 0 44 44" and uses
fill="currentColor".

Test approach
-------------
A small TypeScript script renders the real LogoIcon component to a static
HTML string at test-setup time using ReactDOMServer.renderToStaticMarkup.
This ensures the fixture always tracks the live component source — any change
to LogoIcon.tsx is immediately reflected in the test.  The resulting HTML is
served by a local HTTP server; Playwright verifies the SVG attributes via the
LogoIconPage page object.

Architecture
------------
- LogoIconPage (Page Object) from testing/components/pages/logo_icon/ handles
  all Playwright interactions.
- WebConfig from testing/core/config/ centralises env-var access.
- Playwright sync API with pytest module-scoped fixtures.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from testing.core.config.web_config import WebConfig
from testing.components.pages.logo_icon import LogoIconPage

# ---------------------------------------------------------------------------
# Repository root paths
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_WEB_DIR = os.path.join(_REPO_ROOT, "web")
_LOGO_ICON_TSX = os.path.join(_WEB_DIR, "src", "components", "icons", "LogoIcon.tsx")

# tsconfig used by ts-node to transpile the render script (CommonJS mode so
# node can load it; module resolution set to "node" to satisfy ts-node).
_TSCONFIG_CONTENT = """{
  "compilerOptions": {
    "target": "ES2017",
    "module": "CommonJS",
    "moduleResolution": "node",
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "jsx": "react",
    "strict": false
  }
}"""

# TypeScript render script: imports the real LogoIcon and renders it to a
# string.  Written to a temp file inside web/ so that ts-node can resolve
# node_modules and the relative import to the component.
_RENDER_SCRIPT_CONTENT = """\
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import LogoIcon from './src/components/icons/LogoIcon';
const html = renderToStaticMarkup(React.createElement(LogoIcon));
process.stdout.write(html + '\\n');
"""


def _render_logo_icon_svg() -> str:
    """Render LogoIcon.tsx to an SVG string via ts-node.

    Writes a temporary TypeScript render script into web/ (so that ts-node
    resolves node_modules correctly), executes it, then removes the temp file.
    Raises RuntimeError if ts-node fails.
    """
    ts_node = os.path.join(_WEB_DIR, "node_modules", ".bin", "ts-node")
    if not os.path.exists(ts_node):
        raise RuntimeError(f"ts-node not found at {ts_node}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".ts",
        dir=_WEB_DIR,
        prefix="_render_logo_icon_",
        delete=False,
    ) as script_file:
        script_file.write(_RENDER_SCRIPT_CONTENT)
        script_path = script_file.name

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        dir=_WEB_DIR,
        prefix="_tsconfig_render_",
        delete=False,
    ) as cfg_file:
        cfg_file.write(_TSCONFIG_CONTENT)
        tsconfig_path = cfg_file.name

    try:
        env = {**os.environ, "TS_NODE_PROJECT": tsconfig_path}
        result = subprocess.run(
            [ts_node, "--transpile-only", os.path.basename(script_path)],
            cwd=_WEB_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ts-node failed (rc={result.returncode}):\n{result.stderr}"
            )
        return result.stdout.strip()
    finally:
        os.unlink(script_path)
        os.unlink(tsconfig_path)


def _build_fixture_html(svg_markup: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>LogoIcon test fixture</title></head>
<body>
  <div id="root">{svg_markup}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fixture_server():
    """Render LogoIcon from source and serve it via a local HTTP server."""
    svg_markup = _render_logo_icon_svg()
    html_content = _build_fixture_html(svg_markup).encode("utf-8")

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def logo_icon_page(fixture_server):
    """Return a LogoIconPage connected to the rendered fixture page."""
    config = WebConfig()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless)
        page = browser.new_page()
        page.goto(fixture_server, wait_until="domcontentloaded")
        yield LogoIconPage(page)
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLogoIconSVGAttributes:
    """Verify LogoIcon renders an SVG with the expected attributes."""

    def test_svg_element_is_present(self, logo_icon_page: LogoIconPage):
        """The component renders exactly one <svg> root element."""
        count = logo_icon_page.svg_count()
        assert count == 1, f"Expected exactly one <svg> inside #root, got {count}"

    def test_svg_view_box(self, logo_icon_page: LogoIconPage):
        """The SVG has viewBox='0 0 44 44'."""
        view_box = logo_icon_page.get_view_box()
        assert view_box == "0 0 44 44", (
            f"Expected viewBox='0 0 44 44', got '{view_box}'"
        )

    def test_svg_fill_current_color(self, logo_icon_page: LogoIconPage):
        """The SVG uses fill='currentColor'."""
        fill = logo_icon_page.get_fill()
        assert fill == "currentColor", (
            f"Expected fill='currentColor', got '{fill}'"
        )
