MYTUBE-394 Test: Proactive Firebase auth heartbeat detection

Purpose
-------
Verify that the application detects Firebase authentication service unavailability mid-session and displays the message "Authentication services are currently unavailable." automatically.

Running locally
---------------
Requirements:
- Python 3.10+
- Playwright and browsers installed (pip install -r testing/requirements.txt; playwright install)

Run the single test:

    pytest -q testing/tests/MYTUBE-394/test_mytube_394.py

Environment variables
---------------------
- WEB_BASE_URL or APP_URL: Base URL of the deployed app (default used in project config)
- FIREBASE_API_KEY, FIREBASE_TEST_EMAIL, FIREBASE_TEST_PASSWORD: Optional — set to run in live mode. If unset, the test runs in simulation mode.

Notes
-----
- This folder includes config.yaml required by test harness.
- The test uses injected init scripts to accelerate the heartbeat interval for CI speed and to simulate an authenticated user when credentials are not available.
- Do not mutate Playwright Page objects for cross-test state; use window-scoped flags via page.evaluate instead.
