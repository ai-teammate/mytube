# MYTUBE-401

Test: Restoration of Firebase service connectivity — authentication error dismissed

How to run
----------

1. Install Python dependencies (from repository root):

```bash
python3 -m pip install -r testing/requirements.txt
```

2. Run the test:

```bash
pytest testing/tests/MYTUBE-401/test_mytube_401.py -q
```

Environment variables
---------------------
- APP_URL or WEB_BASE_URL: Base URL of the web app (default: https://ai-teammate.github.io/mytube)
- FIREBASE_API_KEY: (optional) If set along with FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD the test will run in live mode; otherwise it will run in simulation mode.
- FIREBASE_TEST_EMAIL, FIREBASE_TEST_PASSWORD: CI test user credentials (optional for live mode)

Expected output
---------------
The test should pass, reporting that the auth error alert was removed after the Firebase domains were unblocked.
