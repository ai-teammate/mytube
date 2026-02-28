"""Service object for managing the Go API process lifecycle during tests."""
import os
import subprocess
import time
import urllib.request
import urllib.error
from typing import Optional


class ApiProcessService:
    """
    Starts and stops the Go API binary in a subprocess with configurable
    environment variables.  Provides helpers to wait for the server to become
    ready (or to confirm it exited) and to issue HTTP requests against it.

    Usage::

        service = ApiProcessService(binary_path, port=18080, env={"DB_PASSWORD": "bad"})
        service.start()
        try:
            status, body = service.get("/health")
        finally:
            service.stop()

    Dependency injection: callers pass the binary path and all config; nothing
    is hardcoded inside this class.
    """

    def __init__(
        self,
        binary_path: str,
        port: int = 18080,
        env: Optional[dict] = None,
        startup_timeout: float = 5.0,
    ):
        self._binary_path = binary_path
        self._port = port
        self._env = env or {}
        self._startup_timeout = startup_timeout
        self._process: Optional[subprocess.Popen] = None
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the API process.  Does NOT wait for readiness."""
        proc_env = os.environ.copy()
        proc_env.update(self._env)
        proc_env["PORT"] = str(self._port)

        self._process = subprocess.Popen(
            [self._binary_path],
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def stop(self) -> None:
        """Terminate the process if still running and collect remaining output."""
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        self._collect_output()
        self._process = None

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        """Return True if the process is still alive."""
        return self._process is not None and self._process.poll() is None

    def exit_code(self) -> Optional[int]:
        """Return the process exit code, or None if still running."""
        if self._process is None:
            return None
        return self._process.poll()

    def wait_for_exit(self, timeout: float = 5.0) -> Optional[int]:
        """Block until the process exits or *timeout* seconds pass.

        Returns the exit code, or None on timeout.
        """
        if self._process is None:
            return None
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            pass
        self._collect_output()
        return self._process.poll()

    def wait_for_ready(self, path: str = "/health") -> bool:
        """Poll the given path until the server responds or startup_timeout expires.

        Returns True when the server is accepting connections, False on timeout.
        """
        deadline = time.monotonic() + self._startup_timeout
        url = f"http://127.0.0.1:{self._port}{path}"
        while time.monotonic() < deadline:
            if not self.is_running():
                return False
            try:
                urllib.request.urlopen(url, timeout=1)
                return True
            except urllib.error.HTTPError:
                # Server responded (even with 4xx/5xx) — it is up.
                return True
            except (urllib.error.URLError, OSError):
                time.sleep(0.1)
        return False

    def get_log_output(self) -> str:
        """Return all captured stdout/stderr from the process so far."""
        self._collect_output()
        return "\n".join(self._stdout_lines)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def get(self, path: str, headers: Optional[dict] = None) -> tuple[int, str]:
        """Issue GET *path* and return (status_code, response_body)."""
        url = f"http://127.0.0.1:{self._port}{path}"
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _collect_output(self) -> None:
        """Read any pending lines from stdout without blocking."""
        if self._process is None or self._process.stdout is None:
            return
        # Non-blocking read: communicate() would block; use readline with poll.
        while True:
            if self._process.stdout.readable():
                line = self._process.stdout.readline()
                if not line:
                    break
                self._stdout_lines.append(line.rstrip("\n"))
            else:
                break
