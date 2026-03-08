import subprocess


def test_transcode_silent_thumbnail_failure_placeholder_thumbnail_url_in_db():
    """Run the Go unit test TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB
    in api/cmd/transcoder and assert it passes.
    """
    cmd = [
        "go",
        "test",
        "-v",
        "-count=1",
        "-run",
        "TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB",
        ".",
    ]

    proc = subprocess.run(
        cmd,
        cwd="api/cmd/transcoder",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Print output so pytest shows the Go test logs
    print(proc.stdout)

    assert proc.returncode == 0, (
        f"go test failed with exit code {proc.returncode}. See output above for details."
    )
