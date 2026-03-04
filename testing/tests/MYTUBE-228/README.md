# MYTUBE-228: Add video to playlist as owner — video appended to the end of the collection

## Overview

Verifies that the playlist owner can add a video and that the system assigns
the position as `COALESCE(MAX(current_positions), 0) + 1` (append-only).

Two test layers:

| Layer | What it tests | Requirements |
|-------|--------------|--------------|
| A — Go unit tests | Handler and repository logic (no DB/network needed) | Go toolchain in `api/` |
| B — HTTP integration | Full end-to-end against the deployed API | `FIREBASE_TEST_TOKEN`, `API_BASE_URL` |

## Dependencies

```
pip install pytest
```

No additional Python dependencies beyond the standard library and pytest.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIREBASE_TEST_TOKEN` | Layer B only | — | Firebase ID token for the CI test user. Layer B is skipped when absent. |
| `API_BASE_URL` | Layer B only | `https://mytube-api-80693608388.us-central1.run.app` | Base URL of the deployed API. |

## How to Run

```bash
# From the repository root:
cd /path/to/mytube

# Run both layers (Layer B will skip gracefully when FIREBASE_TEST_TOKEN is unset):
pytest testing/tests/MYTUBE-228/test_mytube_228.py -v

# Run with a real Firebase token to exercise Layer B:
FIREBASE_TEST_TOKEN=<token> pytest testing/tests/MYTUBE-228/test_mytube_228.py -v
```

## Expected Output (all layers pass)

```
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoHandlerGoUnit::test_add_video_success_returns_204_unit PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoHandlerGoUnit::test_add_video_no_auth_returns_401_unit PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoHandlerGoUnit::test_add_video_forbidden_returns_403_unit PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoHandlerGoUnit::test_get_playlist_includes_video_position_unit PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoRepositoryGoUnit::test_repository_add_video_success_unit PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoToPlaylist::test_add_video_response_is_success PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoToPlaylist::test_get_playlist_returns_200 PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoToPlaylist::test_added_video_appears_in_playlist PASSED
testing/tests/MYTUBE-228/test_mytube_228.py::TestAddVideoToPlaylist::test_video_position_is_append_only PASSED
```
