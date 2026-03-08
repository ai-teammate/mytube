MYTUBE-402: Browser offline transition triggers authentication services error

How to run
---------

Install dependencies:

    pip install -r testing/requirements.txt
    playwright install

Run the test:

    pytest testing/tests/MYTUBE-402 -q

Environment variables
---------------------
- APP_URL / WEB_BASE_URL: base URL of deployed frontend (default: https://ai-teammate.github.io/mytube)
- PLAYWRIGHT_HEADLESS: "true" (default) or "false"
- FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD (optional): if provided the test will log in with these credentials; otherwise the test will attempt to inject a fake authenticated session by discovering the Firebase API key from the deployed app.

Expected output
---------------
When the test passes, Playwright will navigate to the dashboard, toggle the browser into offline mode, and assert that the site header displays a role="alert" message: "Authentication services are currently unavailable".