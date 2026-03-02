# MYTUBE-137: Submit video title exceeding 255 characters — API returns validation error

## What this test verifies

Automates the test case for MYTUBE-137: verifies that `POST /api/videos` rejects
a title longer than 255 characters with a validation error response (HTTP 422).

The test delegates to the Go unit tests in `api/internal/handler/videos_test.go`,
which exercise the handler's title-length validation with stub dependencies
(no Firebase credentials or database required).

## Dependencies

- Go toolchain (same version used by the project)
- Python 3.10+
- pytest

Install Python dependencies:

```bash
pip install pytest
```

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-137/test_mytube_137.py -v
```

Or from any directory:

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-137/test_mytube_137.py -v
```

## Environment variables

No environment variables are required. The Go unit tests use stub dependencies
and do not connect to any external services.

## Expected output when the test passes

```
testing/tests/MYTUBE-137/test_mytube_137.py::TestVideoTitleLengthValidation::test_handler_package_compiles PASSED
testing/tests/MYTUBE-137/test_mytube_137.py::TestVideoTitleLengthValidation::test_title_256_chars_returns_422 PASSED
testing/tests/MYTUBE-137/test_mytube_137.py::TestVideoTitleLengthValidation::test_title_255_chars_is_accepted PASSED
testing/tests/MYTUBE-137/test_mytube_137.py::TestVideoTitleLengthValidation::test_validation_error_message_contains_character_limit PASSED
testing/tests/MYTUBE-137/test_mytube_137.py::TestVideoTitleLengthValidation::test_full_title_validation_suite_passes PASSED

5 passed in X.XXs
```

## Notes

- The API returns **HTTP 422 Unprocessable Entity** for title-too-long (not 400 Bad Request
  as written in the original test case ticket). 422 is the semantically correct status
  for business-rule validation failures on syntactically valid JSON.
- The handler uses `utf8.RuneCountInString` — the limit is 255 Unicode code points,
  not bytes.
