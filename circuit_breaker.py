"""Inline loop-detection / spend-cap circuit breaker for the x402 proxy.

An agent stuck in a logic loop can burn real money fast (tens of thousands of
identical paid calls per hour before a human notices). Because this proxy sits
in the agent's call path, it can hard-stop that pattern cheaply, before
payment verification and upstream forwarding run.

MVP logic (v1):
  * identity: the caller, derived from X-Forwarded-For (first hop) or the
    direct peer IP. Proof headers are deliberately NOT part of the identity:
    replay protection forces a fresh proof per paid call, so a looping agent
    rotates proofs while the IP stays stable.
  * fingerprint: sha256 of method + path + canonical params + body bytes.
  * loop trip: >= IDENTICAL_THRESHOLD identical fingerprints from one
    identity inside a WINDOW_SECONDS sliding window -> the (identity,
    fingerprint) pair enters cooldown; every further identical request gets
    HTTP 429 with the standardized AGENT_LOOP_DETECTED payload until
    COOLDOWN_SECONDS elapse.
  * rate cap: > RATE_LIMIT_PER_MIN total calls per identity per 60s ->
    HTTP 429 AGENT_RATE_LIMITED (no cooldown, just slow down).

Tuning via env: LOOP_WINDOW_SECONDS (60), LOOP_IDENTICAL_THRESHOLD (25),
LOOP_COOLDOWN_SECONDS (300), LOOP_RATE_LIMIT_PER_MIN (120),
LOOP_PROTECTION=off to disable.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import deque

LOOP_DOCS = "https://github.com/FrozenCorn2113/x402-wrapper#loop-protection"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (ValueError, AttributeError):
        return default


WINDOW_SECONDS = _env_int("LOOP_WINDOW_SECONDS", 60)
IDENTICAL_THRESHOLD = _env_int("LOOP_IDENTICAL_THRESHOLD", 25)
COOLDOWN_SECONDS = _env_int("LOOP_COOLDOWN_SECONDS", 300)
RATE_LIMIT_PER_MIN = _env_int("LOOP_RATE_LIMIT_PER_MIN", 120)
ENABLED = os.environ.get("LOOP_PROTECTION", "on").strip().lower() not in (
    "0", "off", "no", "false",
)

_MAX_BODY_BYTES = 65536  # fingerprinting cap, not a request limit


def payload_fingerprint(method: str, path: str, query: str, body: bytes) -> str:
    """Stable hash of what makes two agent calls 'the same request'."""
    h = hashlib.sha256()
    h.update(method.upper().encode())
    h.update(b"|")
    h.update(path.encode())
    h.update(b"|")
    h.update(query.encode())
    h.update(b"|")
    h.update(body[:_MAX_BODY_BYTES])
    return h.hexdigest()


def loop_error(identity: str, fingerprint: str, retry_after: int) -> dict:
    return {
        "error": {
            "code": "AGENT_LOOP_DETECTED",
            "status": 429,
            "message": (
                f"Identical requests from this client tripped loop protection: "
                f"{IDENTICAL_THRESHOLD}+ identical calls within "
                f"{WINDOW_SECONDS}s. If your agent is retrying in a loop, "
                f"fix the loop before continuing; you are NOT being charged "
                f"for blocked calls."
            ),
            "retry_after": retry_after,
            "window_seconds": WINDOW_SECONDS,
            "identical_threshold": IDENTICAL_THRESHOLD,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "identity": identity,
            "request_fingerprint": fingerprint[:16],
            "docs": LOOP_DOCS,
        }
    }


def rate_error(identity: str, retry_after: int) -> dict:
    return {
        "error": {
            "code": "AGENT_RATE_LIMITED",
            "status": 429,
            "message": (
                f"Client exceeded {RATE_LIMIT_PER_MIN} calls/min. Slow down; "
                f"you are NOT being charged for blocked calls."
            ),
            "retry_after": retry_after,
            "limit_per_minute": RATE_LIMIT_PER_MIN,
            "identity": identity,
            "docs": LOOP_DOCS,
        }
    }


class CircuitBreaker:
    """Thread-safe, in-memory loop detector. One instance per process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # identity -> deque[(timestamp, fingerprint)]
        self._calls: dict[str, deque[tuple[float, str]]] = {}
        # (identity, fingerprint) -> cooldown expiry timestamp
        self._cooldowns: dict[tuple[str, str], float] = {}
        # Pollable honesty counters (see public_report). Process-local:
        # Render's free tier runs one worker, so these reflect the whole
        # service. They are operator-published — trust the deployment, or
        # falsify the policy with the public challenge harness instead.
        self._started_at = time.time()
        self.loops_tripped = 0        # cooldown entries created
        self.loop_blocked_calls = 0   # calls refused while a cooldown held
        self.rate_blocked_calls = 0   # calls refused by the per-minute cap

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._cooldowns.clear()
            # Honesty counters survive reset(): they are the public audit
            # trail, not per-test state. Tests use fresh instances instead.

    def _prune(self, identity: str, now: float) -> deque[tuple[float, str]]:
        dq = self._calls.get(identity)
        if dq is None:
            dq = deque()
            self._calls[identity] = dq
        cutoff = now - WINDOW_SECONDS
        while dq and dq[0][0] < cutoff:
            dq.popleft()
        return dq

    def check(self, identity: str, fp: str, now: float | None = None) -> dict | None:
        """Return a 429 error body if this call is blocked, else None.

        The returned dict carries a "retry_after" key alongside "error".
        """
        if not ENABLED:
            return None
        now = time.time() if now is None else now
        key = (identity, fp)
        with self._lock:
            cool_until = self._cooldowns.get(key)
            if cool_until and now < cool_until:
                self.loop_blocked_calls += 1
                return {**loop_error(identity, fp, int(cool_until - now)),
                        "retry_after": int(cool_until - now)}
            if cool_until:
                del self._cooldowns[key]

            dq = self._prune(identity, now)
            dq.append((now, fp))

            if len(dq) > RATE_LIMIT_PER_MIN:
                self.rate_blocked_calls += 1
                return {**rate_error(identity, 60), "retry_after": 60}

            identical = sum(1 for _, f in dq if f == fp)
            if identical >= IDENTICAL_THRESHOLD:
                cool_until = now + COOLDOWN_SECONDS
                self._cooldowns[key] = cool_until
                self.loops_tripped += 1
                return {**loop_error(identity, fp, COOLDOWN_SECONDS),
                        "retry_after": COOLDOWN_SECONDS}
            return None

    def stats(self) -> dict:
        """Pollable honesty counters for buyers (see public_report)."""
        with self._lock:
            return {
                "loops_tripped": self.loops_tripped,
                "loop_blocked_calls": self.loop_blocked_calls,
                "rate_blocked_calls": self.rate_blocked_calls,
                "active_cooldowns": len(self._cooldowns),
                "process_started_unix": int(self._started_at),
            }


# Process-wide instance; Render free tier runs a single worker by default.
breaker = CircuitBreaker()


def describe() -> dict:
    """Public config summary for /v1 and docs."""
    return {
        "enabled": ENABLED,
        "window_seconds": WINDOW_SECONDS,
        "identical_threshold": IDENTICAL_THRESHOLD,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "rate_limit_per_minute": RATE_LIMIT_PER_MIN,
        "identity_source": "X-Forwarded-For or peer IP (payment proofs excluded by design)",
    }


def public_report() -> dict:
    """Pollable loop-protection report for buyers.

    Served at GET /v1/loop-protection. Answers the verifiability question:
    the policy plus the live counters a buyer can poll to see what the
    breaker has actually blocked. Honest limitation, stated plainly: the
    counters are process-local and operator-published, so they still
    require trusting the deployment. A buyer who wants independent proof
    should run the public challenge harness (send 25+ identical unpaid
    calls and watch for HTTP 429 AGENT_LOOP_DETECTED) rather than trust
    these numbers.
    """
    return {
        "policy": describe(),
        "stats": breaker.stats(),
        "poll": "GET /v1/loop-protection",
        "honesty": (
            "Counters are process-local (single worker) and operator-"
            "published; they require trusting this deployment. Independent "
            "verification: the challenge harness — 25+ identical unpaid "
            "calls to any /v1/{wrapper} must return HTTP 429 with code "
            "AGENT_LOOP_DETECTED; blocked calls are never charged and never "
            "forwarded upstream."
        ),
    }
