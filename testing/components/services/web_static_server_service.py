"""Service object for serving the built Next.js frontend via HTTP."""
import os
import subprocess
import time
import urllib.request
import urllib.error
from typing import Optional
import threading


class WebStaticServerService:
    """Serves the pre-built Next.js static frontend via Python HTTP server."""

    def __init__(
        self,
        repo_root: str,
        port: int = 3000,
        startup_timeout: float = 10.0,
    ):
        self._repo_root = repo_root
        self._out_dir = os.path.join(repo_root, "web", "out")
        self._port = port
        self._startup_timeout = startup_timeout
        self._process: Optional[subprocess.Popen] = None
        self._output_thread: Optional[threading.Thread] = None
        self._stdout_lines: list[str] = []

    def start(self) -> None:
        """Start the HTTP server serving the static frontend."""
        if not os.path.isdir(self._out_dir):
            raise RuntimeError(f"Frontend build directory not found: {self._out_dir}")

        self._process = subprocess.Popen(
            [
                "python", "-m", "http.server",
                str(self._port),
                "--directory", self._out_dir,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        self._output_thread = threading.Thread(target=self._read_output, daemon=True)
        self._output_thread.start()

    def stop(self) -> None:
        """Terminate the HTTP server."""
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        
        if self._output_thread:
            self._output_thread.join(timeout=2)
        
        self._process = None

    def is_running(self) -> bool:
        """Return True if the server is still running."""
        return self._process is not None and self._process.poll() is None

    def wait_for_ready(self, path: str = "/") -> bool:
        """Poll the server until it responds or timeout expires."""
        deadline = time.monotonic() + self._startup_timeout
        url = f"http://127.0.0.1:{self._port}{path}"
        attempts = 0
        while time.monotonic() < deadline:
            attempts += 1
            if not self.is_running():
                logs = self.get_log_output()
                print(f"Web server crashed. Logs:\n{logs}", flush=True)
                return False
            try:
                urllib.request.urlopen(url, timeout=1)
                print(f"Web server ready after {attempts} attempts", flush=True)
                return True
            except (urllib.error.URLError, OSError):
                if attempts % 20 == 0:
                    print(f"Web server not ready yet (attempt {attempts})", flush=True)
                time.sleep(0.1)
        logs = self.get_log_output()
        print(f"Web server timeout. Logs:\n{logs}", flush=True)
        return False

    def get_log_output(self) -> str:
        """Return all captured output from the server."""
        return "\n".join(self._stdout_lines)

    def _read_output(self) -> None:
        """Read output from the server (runs in background thread)."""
        if self._process is None or self._process.stdout is None:
            return
        try:
            for line in iter(self._process.stdout.readline, ""):
                if line:
                    self._stdout_lines.append(line.rstrip("\n"))
        except Exception:
            pass
