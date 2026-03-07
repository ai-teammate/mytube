# MYTUBE-267: API request with invalid category_id format

Test case for verifying that the API returns HTTP 400 Bad Request when given an invalid category_id parameter format.

## Objective

Verify that the API returns an error when the category_id parameter is provided in an incorrect format.

## Steps

1. Send a GET request to `/api/videos?category_id=not-a-valid-id&limit=20`.
2. Inspect the HTTP response code and body.

## Expected Result

The API returns a 400 Bad Request status code and a clear error message indicating the invalid parameter format.
