# MYTUBE-636 — Client-side file size validation (> 5 MB)

## Objective

Verify that the Account Settings page prevents selecting an image file larger than 5 MB by displaying an immediate client-side error message, without sending any network request to the backend.

## Preconditions

- User is authenticated and on the Account Settings page (`/settings`).
- Firebase test credentials are available via `FIREBASE_TEST_EMAIL` / `FIREBASE_TEST_PASSWORD`.

## Steps

1. Navigate to `/settings` (log in first with Firebase test credentials).
2. Simulate selecting an image file whose size exceeds 5 MB via the avatar file input (`id="avatar_file"`).
3. Assert that a `<p role="alert">` element appears immediately with the text `"File is too large. Maximum size is 5 MB."`.
4. Assert that no network request is sent to the avatar upload endpoint (`/api/me/avatar`).

## Expected Result

- The error message `"File is too large. Maximum size is 5 MB."` is displayed near the upload control.
- No `POST /api/me/avatar` request is made — validation is entirely client-side.

## Test Cases

| Test | Description |
|------|-------------|
| `test_oversized_file_shows_error_message` | Error alert appears immediately after file selection |
| `test_oversized_file_does_not_trigger_network_request` | No HTTP request to avatar endpoint when file is rejected |
