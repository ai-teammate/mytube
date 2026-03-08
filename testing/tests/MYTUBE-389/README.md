# MYTUBE-389: Missing local thumbnail file — existence check prevents fatal error

## Objective

Verify that the transcoder checks for the existence of `thumbnail.jpg` on the
local filesystem before attempting an upload, preventing fatal 'no such file or
directory' errors and job failure.

## Test Type

Go unit tests (Layer A — always runs, no infrastructure required).

## Architecture

The test runs the transcoder's Go unit tests covering the `silentThumbFail`
scenario:  when FFmpeg exits 0 but does not write `thumbnail.jpg` to disk (the
video-only input case).

The following behaviours are asserted:

1. **Existence check**: `os.Stat(thumbPath)` detects the missing file and
   `thumbReady` remains false — no upload is attempted.
2. **Warning logged**: the transcoder emits a log message containing
   `event=thumbnail_skipped` and `reason=silent_ffmpeg_failure`.
3. **HLS upload continues**: `UploadDir` is still called with the HLS prefix.
4. **DB updated**: `UpdateVideo` is called with `status=ready` and an empty
   `thumbnail_url`.
5. **Exit code 0**: `transcode()` returns `nil` — no fatal error.

## Environment Variables

| Variable         | Default                              | Description                    |
|------------------|--------------------------------------|--------------------------------|
| `TRANSCODER_DIR` | `<repo_root>/api/cmd/transcoder`     | Path to transcoder source dir  |
