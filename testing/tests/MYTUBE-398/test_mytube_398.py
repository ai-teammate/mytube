import shutil
import subprocess
import re
from pathlib import Path
import pytest


@pytest.mark.integration
def test_transcode_silent_thumbnail_failure_placeholder_thumbnail_url_in_db():
    """Run the Go unit test TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB
    in api/cmd/transcoder and assert it passes.

    This test is treated as an integration-style wrapper: it will be skipped when the
    Go toolchain is not available on PATH to avoid confusing failures in environments
    that don't have Go installed.
    """
    # Guard: skip if Go is not available
    if shutil.which("go") is None:
        pytest.skip("Go toolchain not found on PATH; install Go (https://golang.org/dl/) to run this test")

    # Default timeout (seconds) and attempt to read from local config.yaml
    default_timeout = 120
    cfg_path = Path(__file__).parent / "config.yaml"
    timeout = default_timeout
    try:
        if cfg_path.exists():
            txt = cfg_path.read_text()
            m = re.search(r"timeout:\s*(\d+)", txt)
            if m:
                timeout = int(m.group(1))
    except Exception:
        # If config can't be read, fall back to default timeout
        timeout = default_timeout

    cmd = [
        "go",
        "test",
        "-v",
        "-count=1",
        "-run",
        "TestTranscode_SilentThumbnailFailure_PlaceholderThumbnailURLInDB",
        ".",
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd="api/cmd/transcoder",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        # Fail with helpful diagnostic including any captured output
        out = (exc.stdout or "").strip()
        pytest.fail(f"go test timed out after {timeout}s. Output (truncated):\n{out}")

    # Print output so pytest shows the Go test logs
    print(proc.stdout or "")

    assert proc.returncode == 0, (
        f"go test failed with exit code {proc.returncode}. See output above for details."
    )
