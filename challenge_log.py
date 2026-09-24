"""Public challenge log + freshness beacon for loop-protection verifiability.

clawdsmith's critique (Moltbook, 2026-09-22): a static policy page "fixes who
can check, not how often" — a lazy buyer can't tell a stale breaker from a
dead one. The committed design:

  * any party (a buyer, a third-party monitor) can RUN the challenge harness:
    25+ identical unpaid calls to any /v1/{wrapper}; the breaker must return
    HTTP 429 AGENT_LOOP_DETECTED;
  * the challenger POSTs the result here; this log is append-only and public;
  * every entry is hash-chained (SHA-256 of the previous entry), so silent
    tampering breaks the chain and is visible via GET /v1/freshness;
  * GET /v1/freshness shows the last independently-submitted challenge
    (last_independently_challenged_at, challenged_by) plus staleness vs the
    published cadence, so staleness is visible to a lazy buyer.

No self-certification: the operator's own runs are NOT logged as independent
challenges, and entries are self-attributed by the submitter — independence
comes from the challenger publishing their own harness evidence, not from
this server vouching for them. Field caps keep the log abuse-resistant
(spam is self-defeating: it only makes the log less credible).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "challenge-log")
_LOG_FILE = os.path.join(_LOG_DIR, "challenge_log.jsonl")
_MAX_ENTRIES = 1000
_MAX_BY = 200
_MAX_TYPE = 100
_MAX_DETAILS = 2000
_RESULTS = ("pass", "fail", "inconclusive")

# Entry types that live in the hash-chained log but are NOT independent
# breaker challenges. The copy-holder roster commits registrations in the
# checkpoint (holder_roster.register), and those must never reset the
# freshness beacon: staleness measures independent harness runs only.
# "log-genesis" is the operator-attributed bootstrap anchor (see
# ensure_genesis): the log started here, nothing more.
_NON_CHALLENGE_TYPES = {"copy-holder-registration", "log-genesis"}

# Published challenge cadence: hourly during the first week after the breaker
# shipped publicly (2026-09-22), then daily. Staleness is measured against
# this cadence so a lazy buyer can see at a glance whether the beaker is
# being checked as often as promised.
_CADENCE_POLICY = {
    "first_week_interval_seconds": 3600,
    "steady_interval_seconds": 86400,
    "steady_after_unix": 1790467200,  # 2026-09-27T00:00:00Z
    "harness": (
        "25+ identical unpaid calls to any /v1/{wrapper} must return HTTP 429 "
        "with error code AGENT_LOOP_DETECTED; blocked calls are never charged "
        "and never forwarded upstream. Publish your harness code and run logs; "
        "submit {challenged_by, challenge_type, result, details} to "
        "POST /v1/challenge-log."
    ),
}

# Hash chaining (clawdsmith's Moltbook question, 2026-09-23): every entry carries
# the SHA-256 of the previous entry, so silent tampering with the public log
# breaks the chain and is visible to any verifier. First entry chains to a
# fixed genesis constant.
_GENESIS = "0" * 64


def _canonical(entry: dict) -> bytes:
    """Deterministic bytes for hashing: entry without its own entry_hash."""
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(entry: dict) -> str:
    return hashlib.sha256(_canonical(entry)).hexdigest()


_lock = threading.Lock()


# Bootstrap anchor entry: guarantees a freshly started server always offers
# a REAL entry_hash for POST /v1/holder-roster. The first holder literally
# could not self-register: the log had 0 entries, so no entry_hash existed
# to cite (spawn3's Moltbook dry-run report, 2026-09-24 — their bogus-hash
# POST hit our 422 "not an entry_hash in the challenge log", correctly).
# A holder cites this entry to say "I pulled the export and anchored to
# what the server showed at boot" — they still cannot cite it without
# reading the export, so the pull-proof property is preserved.
#
# Honesty labels, matching the rest of the protocol: this is self-attributed
# to the operator, it is NOT an independent breaker challenge (it is in
# _NON_CHALLENGE_TYPES, so the freshness beacon ignores it), and it is the
# only entry the operator ever writes on its own initiative.
_GENESIS_ENTRY = {
    "challenged_by": "x402wrapper-operator",
    "challenge_type": "log-genesis",
    "result": "pass",
    "details": (
        "Bootstrap anchor: the challenge log was empty when the server "
        "started. This entry gives every later entry a hash-chained "
        "predecessor and gives copy-holders a real entry_hash to cite in "
        "POST /v1/holder-roster before any independent harness run exists. "
        "Not an independent breaker challenge; independence is established "
        "only by independently submitted harness runs."
    ),
}


def ensure_genesis() -> dict | None:
    """Seed an empty log with the log-genesis bootstrap entry (once).

    Idempotent: no-op when the log file already has entries, so it is safe
    to call on every server startup (Render free tier restarts are frequent
    and its filesystem is ephemeral). Returns the stored entry, or None.

    NOTE: this acquires _lock itself and inlines the append — it must NOT
    call submit() (threading.Lock is not reentrant).
    """
    with _lock:
        if os.path.exists(_LOG_FILE):
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                if any(line.strip() for line in f):
                    return None  # log already bootstrapped
        err = _valid(_GENESIS_ENTRY)
        if err:
            return None  # cannot happen: the constant entry is valid
        _ensure_dir()
        stored = {
            "id": 1,
            "submitted_at_unix": int(time.time()),
            "challenged_by": _GENESIS_ENTRY["challenged_by"],
            "challenge_type": _GENESIS_ENTRY["challenge_type"],
            "result": _GENESIS_ENTRY["result"],
            "details": _GENESIS_ENTRY["details"],
            "prev_hash": _GENESIS,
        }
        stored["entry_hash"] = _hash(stored)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(stored) + "\n")
    return stored


def _ensure_dir() -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)


def _valid(entry: dict) -> str | None:
    if not isinstance(entry, dict):
        return "body must be a JSON object"
    for key, cap in (("challenged_by", _MAX_BY),
                     ("challenge_type", _MAX_TYPE),
                     ("details", _MAX_DETAILS)):
        val = entry.get(key, "")
        if not isinstance(val, str) or not val.strip():
            return f"missing or empty '{key}'"
        if len(val) > cap:
            return f"'{key}' exceeds {cap} chars"
    if entry.get("result") not in _RESULTS:
        return f"'result' must be one of {_RESULTS}"
    return None


def submit(entry: dict) -> tuple[dict | None, str | None]:
    """Append a challenge result. Returns (stored_entry, error)."""
    err = _valid(entry)
    if err:
        return None, err
    with _lock:
        _ensure_dir()
        lines: list[str] = []
        if os.path.exists(_LOG_FILE):
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        # Rotation: keep the newest _MAX_ENTRIES; old evidence is archived.
        if len(lines) >= _MAX_ENTRIES:
            with open(_LOG_FILE + ".bak", "w", encoding="utf-8") as f:
                f.writelines(lines[: len(lines) - _MAX_ENTRIES + 1])
            lines = lines[len(lines) - _MAX_ENTRIES + 1 :]
        stored = {
            "id": len(lines) + 1,
            "submitted_at_unix": int(time.time()),
            "challenged_by": entry["challenged_by"].strip(),
            "challenge_type": entry["challenge_type"].strip(),
            "result": entry["result"],
            "details": entry["details"].strip(),
            "prev_hash": (json.loads(lines[-1])["entry_hash"]
                          if lines and json.loads(lines[-1]).get("entry_hash")
                          else _GENESIS),
        }
        stored["entry_hash"] = _hash(stored)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(stored) + "\n")
    return stored, None


def read_all(limit: int = 100) -> list[dict]:
    with _lock:
        if not os.path.exists(_LOG_FILE):
            return []
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    return rows[-limit:]


def verify_chain() -> dict:
    """Verify the hash chain over the whole log.

    Returns chain_valid, entries_checked, and first_bad_id (or None). Entries
    stored before hash chaining shipped have no hashes and break the chain —
    that's reported honestly rather than papered over.
    """
    rows = read_all(_MAX_ENTRIES)
    expected_prev = _GENESIS
    checked = 0
    first_bad = None
    for row in rows:
        checked += 1
        eh = row.get("entry_hash")
        ph = row.get("prev_hash")
        if (not isinstance(eh, str) or not isinstance(ph, str)
                or len(eh) != 64 or len(ph) != 64
                or ph != expected_prev or _hash(row) != eh):
            first_bad = row.get("id")
            break
        expected_prev = eh
    return {
        "chain_valid": first_bad is None,
        "entries_checked": checked if first_bad is None else checked - 1,
        "first_bad_id": first_bad,
    }


def _target_interval(now: float) -> int:
    return (_CADENCE_POLICY["first_week_interval_seconds"]
            if now < _CADENCE_POLICY["steady_after_unix"]
            else _CADENCE_POLICY["steady_interval_seconds"])


def freshness_report() -> dict:
    """Freshness beacon: the last independently submitted challenge + staleness.

    Roster registrations (copy-holder-registration entries) live in the same
    hash-chained log but are NOT independent breaker challenges, so they are
    skipped here: the beacon must measure harness runs only.
    """
    entries = read_all(_MAX_ENTRIES)
    latest = next(
        (e for e in reversed(entries)
         if e.get("challenge_type") not in _NON_CHALLENGE_TYPES),
        None,
    )
    now = int(time.time())
    interval = _target_interval(now)
    stale_seconds = now - latest["submitted_at_unix"] if latest else None
    return {
        "cadence": _CADENCE_POLICY,
        "target_interval_seconds": interval,
        "last_independently_challenged_at": (
            latest["submitted_at_unix"] if latest else None),
        "challenged_by": latest["challenged_by"] if latest else None,
        "last_result": latest["result"] if latest else None,
        "staleness_seconds": stale_seconds,
        "fresh": bool(latest) and stale_seconds is not None and stale_seconds <= interval * 1.5,
        "challenges_recorded": sum(
            1 for e in entries if e.get("challenge_type") not in _NON_CHALLENGE_TYPES),
        "holder_registrations_recorded": sum(
            1 for e in entries
            if e.get("challenge_type") == "copy-holder-registration"),
        "chain": verify_chain(),
        "log": "GET /v1/challenge-log",
        "honesty": (
            "Entries are self-submitted by challengers (challenged_by is a "
            "self-asserted label). Independence comes from the challenger "
            "publishing their own harness code and run logs — the "
            "operator's own runs are never logged here. A stale beacon means "
            "nobody has run the harness recently; it says nothing about "
            "whether the breaker is broken — run the harness yourself."
        ),
    }


def export_document() -> dict:
    """Canonical challenger-pull export of the whole challenge log.

    The independent-copy protocol (clawdsmith, Moltbook 2026-09-23: "how
    many challengers hold a copy today, and what minimum prevents quiet
    edits?"): a challenger pulls THIS document, keeps it, and later
    re-pulls to diff. Post-pull edits break the chain against their copy
    (detection), and two holders cross-comparing head_hash / document
    digest close the quiet-edit window (prevention floor).

    document_digest_sha256 is the SHA-256 of raw_jsonl (exact canonical
    JSONL bytes of every entry, one line each with trailing newline) so a
    holder can verify the export without trusting the operator's digest.
    """
    with _lock:
        raw = ""
        if os.path.exists(_LOG_FILE):
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                raw = f.read()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    chain = verify_chain()
    return {
        "format": "x402wrapper-challenge-export",
        "format_version": 1,
        "exported_at_unix": int(time.time()),
        "genesis_hash": _GENESIS,
        "entries_count": len(rows),
        "head_hash": rows[-1]["entry_hash"] if rows else _GENESIS,
        "document_digest_sha256": hashlib.sha256(
            raw.encode("utf-8")).hexdigest(),
        "chain_valid": chain["chain_valid"],
        "chain_entries_checked": chain["entries_checked"],
        "first_bad_id": chain["first_bad_id"],
        "entries": rows,
        "raw_jsonl": raw,
        "how_to_verify": (
            "1. sha256(raw_jsonl) must equal document_digest_sha256 — this "
            "checks the export you hold is the one the server produced. "
            "2. For each entry: sha256 of canonical JSON (keys sorted, no "
            "spaces, entry_hash excluded) must equal entry_hash, and "
            "prev_hash must equal the previous entry's entry_hash (first "
            "entry chains to genesis_hash) — this checks the chain. "
            "3. Keep this export and re-pull later: any post-pull edit to "
            "the log breaks the chain against your copy. Two holders "
            "cross-comparing head_hash / document_digest_sha256 close the "
            "quiet-edit window entirely."
        ),
    }
