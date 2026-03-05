# MYTUBE-239: View user profile with no public playlists — playlists section is hidden

## Objective

Verify that the user profile page does not show an empty playlists section if
the user has no public playlists to display.

## Test modes

**Live mode** (activated when `FIREBASE_API_KEY`, `FIREBASE_TEST_EMAIL`, and
`FIREBASE_TEST_PASSWORD` are set and the CI test user has no public playlists):

1. Authenticates as the CI test user via Firebase.
2. Resolves the username via `GET /api/me`.
3. Navigates to `/u/<username>` on the deployed app.
4. Clicks the Playlists tab, waits for load.
5. Asserts zero playlist cards and "No playlists yet." message (or section hidden).

**Fixture mode** (fallback — always available):

Serves a local HTML page from `http://127.0.0.1:19239` that replicates the
expected empty-playlists state with a "No playlists yet." message and no
playlist card links.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable              | Required for live mode | Default                                  |
|-----------------------|------------------------|------------------------------------------|
| `APP_URL`             | No                     | `https://ai-teammate.github.io/mytube`   |
| `API_BASE_URL`        | No                     | `http://localhost:8081`                  |
| `FIREBASE_API_KEY`    | Yes                    | —                                        |
| `FIREBASE_TEST_EMAIL` | Yes                    | —                                        |
| `FIREBASE_TEST_PASSWORD` | Yes                 | —                                        |
| `PLAYWRIGHT_HEADLESS` | No                     | `true`                                   |
| `PLAYWRIGHT_SLOW_MO`  | No                     | `0`                                      |

## How to run

From the repository root:

```bash
cd /path/to/mytube
pip install playwright pytest
playwright install chromium

# Fixture mode (no credentials needed)
pytest testing/tests/MYTUBE-239/test_mytube_239.py -v

# Live mode (set Firebase credentials first)
export FIREBASE_API_KEY=...
export FIREBASE_TEST_EMAIL=...
export FIREBASE_TEST_PASSWORD=...
pytest testing/tests/MYTUBE-239/test_mytube_239.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-239/test_mytube_239.py::TestProfileNoPublicPlaylists::test_profile_page_renders_correctly PASSED
testing/tests/MYTUBE-239/test_mytube_239.py::TestProfileNoPublicPlaylists::test_no_playlist_cards_visible PASSED
testing/tests/MYTUBE-239/test_mytube_239.py::TestProfileNoPublicPlaylists::test_empty_state_message_or_section_hidden PASSED
```
