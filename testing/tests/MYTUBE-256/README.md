# MYTUBE-256

Test case: Update video metadata with non-existent category — 400 Bad Request returned

## Objective

Verify that the API validates the `category_id` and returns an error if the category does not exist in the database.

## Preconditions

- User is authenticated and owns a video.

## Test Steps

1. Use the owner's credentials to call `PUT /api/videos/:id` for an existing video.
2. Provide a `category_id` that does not exist in the system (e.g., 999999).
3. Inspect the API response status and body.
4. Send a GET request to `/api/videos/[video_id]` to verify no changes were made.

## Expected Result

The API returns a 400 Bad Request status code. The video's metadata remains unchanged in the database.

## Architecture

- Uses ApiProcessService to manage the Go API server subprocess.
- Uses UserService and VideoService for idempotent test-data seeding.
- Uses direct HTTP requests to the API with Bearer token authentication.
- All database operations are transactional and cleaned up after tests.
