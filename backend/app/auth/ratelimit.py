"""Attempts per client address in a sliding hour, in this process (task Z10): joining a course and failed
logins. Behind the proxy the address comes from X-Forwarded-For (uvicorn --proxy-headers). Per-account
lockout (`auth.max_failed_logins`) stays in the account service."""
import threading
import time
from collections import deque


class AttemptWindow:
    def __init__(self, per_hour: int) -> None:
        self.per_hour = per_hour
        self._seen: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque:
        q = self._seen.setdefault(key, deque())
        while q and q[0] <= now - 3600:
            q.popleft()
        return q

    def _wait_locked(self, key: str, now: float) -> int:
        q = self._trim(key, now)
        return max(1, int(q[0] + 3600 - now) + 1) if len(q) >= self.per_hour else 0

    def _add_locked(self, key: str, now: float) -> None:
        self._trim(key, now).append(now)
        if len(self._seen) > 10_000:  # forget idle addresses
            for k in [k for k, v in self._seen.items() if not v]:
                del self._seen[k]

    def wait(self, key: str) -> int:
        """0 if another attempt is allowed now, else the seconds until it is."""
        with self._lock:
            return self._wait_locked(key, time.monotonic())

    def add(self, key: str) -> None:
        """Count an attempt whose outcome is known only afterwards (a failed login)."""
        with self._lock:
            self._add_locked(key, time.monotonic())

    def allow(self, key: str) -> int:
        """Check and count this attempt in one step (parallel requests cannot both pass): 0 if allowed,
        else the seconds to wait (nothing is counted)."""
        with self._lock:
            now = time.monotonic()
            wait = self._wait_locked(key, now)
            if not wait:
                self._add_locked(key, now)
            return wait


def window(app_state, name: str, per_hour: int) -> AttemptWindow:
    """The process-wide window `name` on app.state (created on first use)."""
    found = getattr(app_state, name, None)
    if found is None:
        found = AttemptWindow(per_hour)
        setattr(app_state, name, found)
    return found


def login_failures(request, services) -> AttemptWindow:
    """Failed logins per client address; API v1 and v2 share the window (task Z10)."""
    per_hour = services.settings.limits.accounts.login_failures_per_hour
    return window(request.app.state, "login_failures", per_hour)


def client_address(request) -> str:
    return request.client.host if request.client else "unknown"
