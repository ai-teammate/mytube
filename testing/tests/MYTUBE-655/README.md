# MYTUBE-655 — Delete avatar in progress: button disabled and shows loading state

## What is tested

Verifies that clicking the **"Remove avatar"** button on the Account Settings page
immediately disables the button and shows **"Removing…"** text while the
`DELETE /api/me/avatar` request is in flight.

## Dependencies

```
pytest==8.4.2
playwright==1.58.0
```

## Install

```bash
cd /path/to/repo
pip install -r testing/requirements.txt
playwright install chromium
```

## Run

```bash
pytest testing/tests/MYTUBE-655/test_mytube_655.py -v
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the web app |
| `FIREBASE_TEST_EMAIL` | For live mode only | — | Test user email |
| `FIREBASE_TEST_PASSWORD` | For live mode only | — | Test user password |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms |

## Expected output when tests pass

```
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_settings_tsx_exists PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_removing_state_initialised_false PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_set_removing_true_before_fetch PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_set_removing_false_in_finally PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_button_disabled_when_removing PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_button_shows_removing_text_in_flight PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteSourceAnalysis::test_button_shows_remove_avatar_text_idle PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteFixtureMode::test_button_is_enabled_initially PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteFixtureMode::test_button_disabled_during_delete PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteFixtureMode::test_button_shows_removing_text_during_delete PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteFixtureMode::test_button_re_enabled_after_delete PASSED
testing/tests/MYTUBE-655/test_mytube_655.py::TestAvatarDeleteLiveMode::test_remove_avatar_button_disabled_and_shows_removing_in_flight SKIPPED/PASSED
```

Live-mode test passes when credentials are set; skips otherwise.
