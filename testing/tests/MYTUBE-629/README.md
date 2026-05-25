# MYTUBE-629 — Re-upload avatar: previous file is overwritten in GCS

## Objective

Verify that re-uploading an avatar for the same user uses a deterministic
GCS object key (`avatars/<user_db_id>.<ext>`) so that the second upload
overwrites the existing GCS object rather than creating a parallel file with
a unique suffix.

## Test Type

`api` — REST API test that starts a local Go API server subprocess.

## Preconditions

- A PostgreSQL database is accessible with the credentials from the
  `DB_*` environment variables.
- A test user row already exists (or can be seeded) for the Firebase UID
  specified in `FIREBASE_TEST_UID`.
- A valid Firebase ID token for that user is provided via
  `FIREBASE_TEST_TOKEN`.
- The Firebase project ID is provided via `FIREBASE_PROJECT_ID`.

## Test Steps

1. Build a fresh Go API binary from the current source.
2. Start the API server on a dedicated local port (`18629`).
3. Seed a test user row for `FIREBASE_TEST_UID` (idempotent `ON CONFLICT`).
4. `POST /api/me/avatar` with a 1×1 red PNG (`image_a`).
5. Assert HTTP 200 and capture `avatar_url_a`.
6. `POST /api/me/avatar` with a 1×1 blue PNG (`image_b` — different content).
7. Assert HTTP 200 and capture `avatar_url_b`.
8. Assert `avatar_url_a == avatar_url_b` (deterministic key → overwrite).
9. Assert the URL contains `avatars/` and the user's database UUID.
10. *(Optional)* Download the live GCS object and verify its SHA-256 matches
    `image_b` (skipped when GCS credentials are absent).

## Expected Result

Both uploads return HTTP 200. The `avatar_url` field is identical on both
responses. The GCS object content matches the second uploaded image.

## Environment Variables

| Variable                        | Required | Description |
|---------------------------------|----------|-------------|
| `FIREBASE_TEST_TOKEN`           | Yes      | Firebase ID token for the test user. |
| `FIREBASE_PROJECT_ID`           | Yes      | Firebase project ID for the token verifier. |
| `FIREBASE_TEST_UID`             | No       | `firebase_uid` of the DB test user. Default: `ci-test-user-001`. |
| `API_BINARY`                    | No       | Path to the compiled Go binary. Default: `/tmp/mytube-api-629`. |
| `DB_HOST`                       | No       | Postgres host. Default: `localhost`. |
| `DB_PORT`                       | No       | Postgres port. Default: `5432`. |
| `DB_USER`                       | No       | Postgres user. Default: `postgres`. |
| `DB_PASSWORD`                   | No       | Postgres password. |
| `DB_NAME`                       | No       | Postgres database name. Default: `mytube`. |
| `SSL_MODE`                      | No       | Postgres SSL mode. Default: `disable`. |
| `HLS_BUCKET`                    | No       | GCS bucket for avatar storage. Default: `mytube-hls-output`. |
| `CDN_BASE_URL`                  | No       | Public CDN URL prefix. Default: `https://storage.googleapis.com/mytube-hls-output`. |
| `GCP_PROJECT_ID`                | No       | GCP project (live GCS check only). |
| `GOOGLE_APPLICATION_CREDENTIALS`| No       | Path to GCP service-account JSON key (live GCS check only). |

## Running the Tests

```bash
# Minimal run (skips live GCS check):
FIREBASE_TEST_TOKEN=<token> FIREBASE_PROJECT_ID=<project> \
  pytest testing/tests/MYTUBE-629/test_mytube_629.py -v

# With live GCS verification:
FIREBASE_TEST_TOKEN=<token> FIREBASE_PROJECT_ID=<project> \
  GCP_PROJECT_ID=<gcp_project> \
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  pytest testing/tests/MYTUBE-629/test_mytube_629.py -v
```

## Expected Output

```
PASSED  TestAvatarReUploadOverwritesGCSObject::test_first_upload_returns_200
PASSED  TestAvatarReUploadOverwritesGCSObject::test_first_upload_returns_avatar_url
PASSED  TestAvatarReUploadOverwritesGCSObject::test_second_upload_returns_200
PASSED  TestAvatarReUploadOverwritesGCSObject::test_second_upload_returns_avatar_url
PASSED  TestAvatarReUploadOverwritesGCSObject::test_avatar_url_is_deterministic
PASSED  TestAvatarReUploadOverwritesGCSObject::test_avatar_url_contains_expected_bucket_prefix
SKIPPED TestAvatarReUploadOverwritesGCSObject::test_gcs_object_content_matches_second_upload [GCS creds absent]
```
