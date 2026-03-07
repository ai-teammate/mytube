# MYTUBE-370: FFmpeg command generation for silent video — audio map options omitted

## Objective

Verify that `api/cmd/transcoder/internal/ffmpeg/runner.go` detects the absence
of audio and excludes all invalid audio mapping arguments (`-map 0:a:0`, `-c:a`,
`-b:a`) from the generated FFmpeg command.

## Test type

Go unit test executed via a Python pytest wrapper.

## Dependencies

- Go ≥ 1.24 (`go` must be on `PATH`)
- Python ≥ 3.9 with `pytest`

## How to install Python dependencies

```bash
pip install -r testing/requirements.txt
```

## Exact command to run this test

From the repository root:

```bash
pytest testing/tests/MYTUBE-370/test_mytube_370.py -v
```

To run the underlying Go tests directly:

```bash
cd api
go test ./cmd/transcoder/internal/ffmpeg/... \
    -run "TestTranscodeHLS_SilentVideo" -v
```

## Environment variables / config required

None — the test uses stub runners and does not require real FFmpeg, GCP
credentials, or a running service.

## Expected output when the test passes

```
PASSED testing/tests/MYTUBE-370/test_mytube_370.py::TestFFmpegSilentVideo::test_silent_video_no_audio_map_args
PASSED testing/tests/MYTUBE-370/test_mytube_370.py::TestFFmpegSilentVideo::test_silent_video_stream_map_no_audio
PASSED testing/tests/MYTUBE-370/test_mytube_370.py::TestFFmpegSilentVideo::test_silent_video_video_map_present
PASSED testing/tests/MYTUBE-370/test_mytube_370.py::TestFFmpegSilentVideo::test_all_silent_video_go_tests_pass
```
