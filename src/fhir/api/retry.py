"""Retry helpers for synthetic FHIR extraction clients."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


def retry_with_backoff(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    initial_delay_seconds: float = 0.5,
    backoff_multiplier: float = 2.0,
    retry_exceptions: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError, OSError),
) -> T:
    """Run an operation with bounded exponential backoff."""
    delay = initial_delay_seconds
    last_error: BaseException | None = None
    for attempt in range(attempts):
        try:
            return operation()
        except retry_exceptions as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            time.sleep(delay)
            delay *= backoff_multiplier
    raise RuntimeError(f"FHIR request failed after {attempts} attempts: {last_error}") from last_error
