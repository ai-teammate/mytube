# MYTUBE-393: POST /api/videos by unregistered user — request rejected with 403/422

## Objective

Ensure that POST /api/videos rejects requests from unregistered Firebase users and does not auto-provision a local user row.

## Environment

See parent `testing/README.md` and other test folders for required environment variables. At minimum set:

- FIREBASE_TEST_TOKEN — Firebase ID token for the test user
- API_BASE_URL — API base URL (optional; default: http://localhost:8080)
- FIREBASE_TEST_UID — Test Firebase UID (default: ci-test-user-001)

## How to run

pytest testing/tests/MYTUBE-393/test_mytube_393.py -q
