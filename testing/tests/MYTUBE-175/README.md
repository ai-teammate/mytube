# MYTUBE-175: Retrieve popular and recent videos — lists sorted correctly by view count and date

## What this test verifies

Automates MYTUBE-175: verifies that the discovery APIs return videos in the
correct order based on recency and popularity.

- `GET /api/videos/recent?limit=20` — returns HTTP 200, a JSON array of videos
  ordered by `created_at DESC`, each with a non-negative `view_count`.
- `GET /api/videos/popular?limit=20` — returns HTTP 200, a JSON array of videos
  ordered by `view_count DESC`, each with a parseable `created_at` timestamp.
- Both endpoints respect the `limit` parameter (result count ≤ limit).
- Both endpoints return objects with fields: `id`, `title`, `view_count`,
  `uploader_username`, `created_at`.

## Dependencies

```bash
pip install pytest
```

No extra libraries are required — only the Python standard library (`urllib`).

## Environment variables

| Variable      | Required | Description                                              |
|---------------|----------|----------------------------------------------------------|
| `API_BASE_URL`| Yes      | Base URL of the deployed API (e.g. `https://api.example.com`) |
| `API_HOST`    | No       | API hostname, used when `API_BASE_URL` is absent (default: `localhost`) |
| `API_PORT`    | No       | API port, used when `API_BASE_URL` is absent (default: `8080`) |

## How to run

From the repository root:

```bash
API_BASE_URL=https://your-api.example.com pytest testing/tests/MYTUBE-175/test_mytube_175.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_returns_200 PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_returns_json_array PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_respects_limit PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_videos_have_required_fields PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_videos_ordered_by_created_at_desc PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestRecentVideosEndpoint::test_recent_videos_have_valid_view_count PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_returns_200 PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_returns_json_array PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_respects_limit PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_videos_have_required_fields PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_videos_ordered_by_view_count_desc PASSED
testing/tests/MYTUBE-175/test_mytube_175.py::TestPopularVideosEndpoint::test_popular_videos_have_valid_created_at PASSED
```

## Notes

- Tests that verify ordering require at least 2 ready videos in the database.
  If fewer than 2 are present, those tests skip with a clear message.
- If `API_BASE_URL` points to an unreachable host, all tests skip gracefully.
