MYTUBE-400

Test: Access application with active network — no authentication error alert displayed

Required environment variables:
- FIREBASE_TEST_EMAIL: test account email
- FIREBASE_TEST_PASSWORD: test account password

Notes:
- This test logs in and navigates to /dashboard and asserts that the specific authentication-unavailable alert is not present.
