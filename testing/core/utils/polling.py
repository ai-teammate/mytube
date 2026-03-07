"""Reusable polling utility for infrastructure integration tests."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


def poll_until(
    condition_fn: Callable[[], Any],
    timeout: float,
    interval: float = 5.0,
) -> Optional[Any]:
    """Poll ``condition_fn`` every ``interval`` seconds until it returns a
    truthy value or ``timeout`` seconds elapse.

    Returns the truthy result from ``condition_fn`` if the condition was met
    before the deadline, or ``None`` if the timeout was reached.

    Example::

        result = poll_until(
            lambda: check_execution_appeared(),
            timeout=120,
            interval=10,
        )
        assert result, "Expected execution did not appear within 120s"
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = condition_fn()
        if result:
            return result
        time.sleep(interval)
    return None
