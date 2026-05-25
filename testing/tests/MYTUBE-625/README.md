# MYTUBE-625: Upload valid PNG avatar — image stored in GCS and profile updated

## Objective

Verify that the API successfully processes PNG file uploads for user avatars.

## Preconditions

- User is authenticated (valid Firebase ID token required).

## Steps

1. Send a `POST` request to `/api/me/avatar` using `multipart/form-data`.
2. Attach a file with `image/png` MIME type and size under 5 MB.

## Expected Result

The API returns HTTP 200 OK. The JSON response contains the updated `avatar_url`,
and the file is correctly uploaded to GCS under the `avatars/` prefix.

## Architecture Notes

- `AuthService.post_multipart` wraps authenticated multipart HTTP calls.
- `FIREBASE_TEST_TOKEN` is used for authentication (pre-fetched CI token).
- `APIConfig` supplies the base URL via environment variables.
- A minimal valid 1×1 PNG image is generated in-memory (no external files needed).

## Environment Variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Valid Firebase ID token for the CI test user (required) |
| `API_BASE_URL` | Base URL of the deployed API (default: `http://localhost:8080`) |
