MYTUBE-402 - Application offline detection for auth services

How to run:

1. Install deps (assumes Python 3.10+ and pytest, playwright installed):
   pip install -r testing/requirements.txt || pip install pytest playwright
   playwright install --install-deps

2. Run the test:
   pytest testing/tests/MYTUBE-402/test_mytube_402.py -q

Environment variables:
- APP_URL or WEB_BASE_URL (optional) - default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS (optional) - default: true
- PLAYWRIGHT_SLOW_MO (optional)
- FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD (optional) - if set, the test will log in; otherwise it will use fake-session injection

Expected output on success:
- pytest passes (1 passed)
