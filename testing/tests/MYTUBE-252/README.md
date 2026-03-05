# MYTUBE-252: Delete comment without authentication — system returns 401 unauthorized

## Objective

Verify that the system prevents unauthenticated users from deleting any comments.

## Test Type

- **Type:** API (REST)
- **Framework:** Python urllib
- **Complexity:** Simple (single endpoint, single assertion)

## Preconditions

None. This is a pure authentication test that does not require:
- A local API server (uses deployed API)
- A database setup
- Pre-seeded data (auth failures don't depend on record existence)

## Test Steps

1. Send a DELETE request to `/api/comments/69f8bc2f-dc91-45c5-a4e1-77365f19fcb0` without providing an authentication token or session.

## Expected Result

The request is rejected with a **401 Unauthorized** error. The comment remains in the database unchanged.

## Running the Test

### Quick Run
```bash
cd /home/runner/work/mytube/mytube
python -m pytest testing/tests/MYTUBE-252/test_mytube_252.py -v
```

### Against a Custom API
```bash
API_BASE_URL=http://localhost:8080 \
  python -m pytest testing/tests/MYTUBE-252/test_mytube_252.py -v
```

## Architecture Notes

- **Service Abstraction:** The test uses `CommentsService` from `testing/components/services/comments_service.py` to encapsulate all HTTP interaction. No raw urllib calls appear in test code.
- **Configuration:** API URL is configurable via the `API_BASE_URL` environment variable. Defaults to the deployed production-equivalent API.
- **No Setup Required:** The test sends DELETE to a comment ID without requiring that the comment actually exists. We're testing authentication, not comment existence.
- **Stateless:** The test is completely stateless and can be run multiple times without side effects.

## Test Implementation

**File:** `testing/tests/MYTUBE-252/test_mytube_252.py`

The test is a single method within the `TestDeleteCommentWithoutAuthentication` class:
- `test_delete_without_token_returns_401()` — Sends DELETE without token and asserts HTTP 401.

## Code Quality

- ✅ No hardcoded credentials or tokens
- ✅ No hardcoded URLs (uses config)
- ✅ No raw HTTP calls in test code
- ✅ Clear, descriptive assertion messages
- ✅ Follows existing test patterns from MYTUBE-203, MYTUBE-204, etc.
- ✅ Uses service abstraction (CommentsService)

## Dependencies

The test depends on:
- `CommentsService` — provides `delete_comment()` method
- Standard library modules: `os`, `sys`, `urllib`
- pytest (for test execution)

## Test Execution Result

```
testing/tests/MYTUBE-252/test_mytube_252.py::TestDeleteCommentWithoutAuthentication::test_delete_without_token_returns_401 PASSED [100%]

================================================== 1 passed in 0.14s ===================================================
```

## Related Tests

- **MYTUBE-203:** Delete own comment — authenticated user deletes their comment (returns 204)
- **MYTUBE-204:** Delete comment as non-owner — authenticated but not owner (returns 403)
- **MYTUBE-252:** Delete comment without authentication — unauthenticated (returns 401)

This test covers the "no auth" scenario that complements MYTUBE-203 and MYTUBE-204.
