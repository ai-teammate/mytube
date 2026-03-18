# MYTUBE-599 — Orphaned Owner Playlist

## Objective

Verify that `GET /api/playlists/:id` returns HTTP 404 (not 500) when the playlist's `owner_id` references a non-existent user, confirming the INNER JOIN miss is handled gracefully.

## Preconditions

- A playlist row exists in the DB whose `owner_id` does not reference any row in `users` (orphaned FK reference).
- The API server is reachable and `FIREBASE_PROJECT_ID` is set.

## Steps

1. Seed an orphaned playlist row via direct DB INSERT (FK temporarily dropped, restored with `NOT VALID`).
2. `GET /api/playlists/:id` for the orphaned playlist (public endpoint — no auth required).
3. Assert HTTP 404 (not 500 Internal Server Error).
4. Assert the response body does not contain "internal server error".
5. Assert the response body contains a "not found" message.
6. Teardown: delete the orphaned row and fully restore the FK constraint.

## Expected Result

HTTP 404 with a `"playlist not found"` body — not 500.

## Root Cause Context (MYTUBE-592)

`GetByID` runs `SELECT … JOIN users u ON u.id = p.owner_id WHERE p.id = $1`. When the owner row is absent the INNER JOIN yields no rows → `sql.ErrNoRows` → the handler returns 404 `"playlist not found"` rather than propagating an unhandled error as 500.
