"""Slows down password guessing: after 5 failed logins for the same email
within 15 minutes, further attempts are refused until the window passes.

Kept in memory, which is fine for a single server. If CASIO ever runs on
several servers, move this to the database or Redis."""
import time
from collections import defaultdict, deque
from threading import Lock

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60

_failures: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def _prune(key: str, now: float) -> deque[float]:
    q = _failures[key]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    return q


def is_blocked(key: str) -> bool:
    with _lock:
        return len(_prune(key, time.monotonic())) >= MAX_FAILURES


def record_failure(key: str) -> None:
    with _lock:
        _prune(key, time.monotonic()).append(time.monotonic())


def reset(key: str | None = None) -> None:
    with _lock:
        if key is None:
            _failures.clear()
            _events.clear()
        else:
            _failures.pop(key, None)


# General-purpose limiter for expensive actions (e.g. AI coach questions).
_events: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str, limit: int, window_seconds: int) -> bool:
    """True (and counts the attempt) if fewer than `limit` attempts happened
    in the last `window_seconds`. Best effort: per server process."""
    now = time.monotonic()
    with _lock:
        q = _events[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
