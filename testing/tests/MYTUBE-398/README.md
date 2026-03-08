MYTUBE-398 Test

This directory contains a pytest wrapper that runs a Go unit test for MYTUBE-398.

Environment requirements
- Go toolchain installed (go 1.16+ recommended)
- Ensure go is available on PATH and modules can be downloaded (internet access may be required)

How to run
- From the repository root run:

  pytest -q testing/tests/MYTUBE-398 -q

- Or run the Go test directly:

  cd api/cmd/transcoder
  go test -v -count=1 -run TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB .

Expected output
- The Go test should pass and print a PASS line. Example snippet:

  === RUN   TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB
  --- PASS: TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB (0.12s)
  PASS
  ok  	./... 	0.123s

- Pytest should report the Python test as passed, e.g.:

  1 passed

Notes
- If the Go toolchain is not installed or the test depends on external services, the test may fail or be skipped.
