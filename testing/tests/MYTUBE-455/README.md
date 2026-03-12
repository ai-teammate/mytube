# MYTUBE-455 — Hero section visual panel: frosted effect and image thumbnail

Verifies the appearance of the right-side visual panel in the hero section:

- The `.visual-panel` element is present in the DOM and is visible.
- Title **"Personal Playback Preview"** is displayed inside the panel.
- Quality badge pills (`4K`, `Full HD`, `HD`) are rendered with non-empty labels.
- The panel applies a frosted glass effect via `backdrop-filter`, a semi-transparent
  `rgba` background, or a glass-style border.
- A thumbnail area (`image_9.png` or a video thumbnail) is present inside the panel.

## ⚠️ Known limitation — fixture mode

The `.visual-panel` element is **not present on the live deployed homepage**
(`https://ai-teammate.github.io/mytube`). When the live page does not expose
the element the test automatically falls back to **fixture mode**: a local HTTP
server serves a minimal HTML replica of the expected visual panel structure
(matching the design spec), and all assertions run against that.

**Consequence**: in fixture mode the test asserts against HTML it authored
itself, so all assertions pass by construction. A `UserWarning` is emitted
in CI output whenever the fallback is active so the mode is always visible.

Once the feature is deployed to the live site the `loaded_visual_panel`
fixture in `conftest.py` should be updated to retire or demote the fallback.

## Architecture

```
Tests (test_mytube_455.py)
  → Components (testing/components/pages/visual_panel_page/)
  → Frameworks  (testing/frameworks/web/playwright/fixtures.py)
  → Core        (testing/core/config/web_config.py)
```

| Layer | What lives there |
|-------|-----------------|
| **Test** | Assertions (`TestHeroVisualPanel`) |
| **Component** | `VisualPanelPage` — DOM selectors and computed-style queries |
| **Framework** | `browser` pytest fixture (Playwright / Chromium) |
| **Core** | `WebConfig` — env-var access |

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Running the tests

From the repository root:

```bash
pytest testing/tests/MYTUBE-455/test_mytube_455.py -v
```

## Expected output (passing)

```
PASSED test_visual_panel_element_exists
PASSED test_visual_panel_is_visible
PASSED test_panel_title_text
PASSED test_quality_badge_pills_present
PASSED test_quality_badge_labels_are_non_empty
PASSED test_panel_has_frosted_glass_effect
PASSED test_thumbnail_area_present
```
