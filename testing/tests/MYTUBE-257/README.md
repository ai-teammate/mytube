# MYTUBE-257: Tag Deduplication Test

## Purpose

This test validates that the API correctly handles duplicate tag values in video metadata requests by deduplicating them before storage and returning unique tags in the response.

## Test Objective

Ensure that when a PUT request to `/api/videos/:id` includes duplicate tag values (e.g., `["tutorial", "tutorial", "coding"]`), the API:
1. Returns HTTP 200 OK with deduplicated tags in the response body
2. Persists deduplicated tags in the database
3. Returns the same deduplicated tags in subsequent GET requests

## Architecture

This test follows the established testing architecture patterns:

- **ApiProcessService**: Manages the lifecycle of the Go API binary (start, wait for ready, stop)
- **UserService**: Handles idempotent test-user creation and lookup
- **VideoService**: Seeds initial video rows with metadata
- **DBConfig**: Provides environment-driven database configuration
- **Direct PostgreSQL Connection**: Used for data verification and cleanup

## Prerequisites

### Required Environment Variables

- **FIREBASE_TEST_TOKEN** (required): A valid Firebase ID token for authentication. Test skips if not set.
- **FIREBASE_PROJECT_ID** (required): The Firebase project ID for the API server's Firebase verifier. Test skips if not set.

### Optional Environment Variables

- **API_BINARY**: Path to the pre-built Go API binary (default: `<repo_root>/api/mytube-api`)
- **FIREBASE_TEST_UID**: Firebase UID associated with the test token (default: `test-uid-mytube-257`)
- **DB_HOST**, **DB_PORT**, **DB_USER**, **DB_PASSWORD**, **DB_NAME**, **SSL_MODE**: Database connection settings (defaults match test DB configuration)

## Test Structure

The test is organized into three main steps matching the ticket requirements:

### Step 1: Send PUT Request with Duplicate Tags
- Sends `PUT /api/videos/{video_id}` with a request body containing duplicate tags
- Verifies HTTP 200 response
- Validates response is valid JSON

### Step 2: Inspect Response Tags
- Parses the response JSON and extracts the tags array
- Asserts that all expected unique tags are present
- Asserts that no duplicates exist in the response

### Step 3: Verify Database Persistence
- Sends `GET /api/videos/{video_id}` to fetch the stored video
- Verifies the persisted tags match the PUT response
- Ensures deduplication persisted to the database

## Running the Test

### Prerequisites
Ensure the following are set up:
```bash
export FIREBASE_TEST_TOKEN="your-firebase-token"
export FIREBASE_PROJECT_ID="your-firebase-project-id"
export FIREBASE_TEST_UID="test-uid-mytube-257"
```

### Run the test
```bash
pytest testing/tests/MYTUBE-257/test_mytube_257.py -v
```

### Run with custom API binary
```bash
API_BINARY=/path/to/custom/binary pytest testing/tests/MYTUBE-257/test_mytube_257.py -v
```

## Test Results Interpretation

- **✅ PASSED (6/6 tests)**: All assertions passed, deduplication works correctly
- **❌ FAILED**: One or more assertions failed; check the error message for details

### Common Failure Scenarios

1. **Tag order differs from expectation**: The test uses set equality, so order doesn't matter. If this fails, the set of tags doesn't match.
2. **Duplicates in response**: The test detects if duplicates were not removed.
3. **Missing or extra tags**: The test verifies all expected unique tags are present, no more, no less.
4. **Database persistence failed**: If Step 3 fails but Step 2 passes, the tags weren't persisted correctly.

## Notes

- The test uses module-scoped fixtures to minimize setup/teardown overhead
- No hardcoded waits; `ApiProcessService.wait_for_ready()` polls the `/health` endpoint
- All fixtures handle cleanup on teardown (process stops, database connections close)
- Test user and video are seeded idempotently (find-or-create pattern)
