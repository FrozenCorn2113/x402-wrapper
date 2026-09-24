"""Prepaid spend envelopes (MVP v1): a principal's on-chain USDC top-up becomes
an operator-tracked credit line that an agent draws down through /v1/{name}.

The product shape comes straight from customer discovery (2026-09-22/23):
  * jarviscooper (Moltbook): "I won't spend a principal's funds to generate a
    data point" — an agent under a funded principal cannot self-authorize
    spend, so near-free pricing does not fix onboarding. His trust doctrine:
    (1) the mandate must be signed by the PRINCIPAL, not the agent;
    (2) invalidation must be enforced WHERE THE MONEY IS;
    (3) ambiguity resolves to NO purchase.
  * AureliusX: wants "a reversible envelope plus an explicit reason for the
    call, not just a hard ceiling."
  * deepdonorbot: blocked on funding for agentic work.

Trust design (Brett's hard constraints):
  * The OPERATOR opens and tops up envelopes, ONLY after read-only on-chain
    verification that the principal sent USDC to the business wallet
    (0x7f7e1e0cc60f2623398140d473276c015686e75c, Base mainnet). On-chain
    verification is MANUAL for now — Len checks the transfer on Base before
    calling POST /v1/admin/envelopes/{id}/topup. The code only records what
    the operator attests.
  * We track balances; we NEVER hold customer keys and cannot move customer
    funds. Only Brett can release payouts. Contract escrow is DEFERRED to v2
    (documented, not built).
  * Principal-signed mandates (EIP-712) are v2, not built. Nothing here
    claims otherwise — the HONESTY NOTE in llms.txt says this in plain words.

jarviscooper's rule is load-bearing in try_spend(): ANY ambiguity — unknown
id, suspended/closed status, cap exceeded, short balance, velocity tripped,
missing or malformed reason — refuses with ENVELOPE_DECLINED (HTTP 402) and
NEVER decrements, charges, or forwards.

CREDIT-OBSERVABILITY RULE (2026-09-24, from jarviscooper's buyer-side
feedback): "the only bound that reads from the buyer seat is one you can
watch and empty on demand" — so no credit may enter the ledger as a bare
number. Every credit carries its on-chain provenance (tx hash, amount,
timestamp, rail) and the public statement exposes the FULL credit history,
so a principal can reconcile every credit against Base directly instead of
taking the operator's word. The operator remains in the credit path in v1
(manual on-chain verification); the statement layer makes every credit
observable, which is what keeps the bound honest.

MANDATE-HASH RULE (2026-09-25, from neodelvorn's void-on-context-change
feedback): a credit's number and provenance still don't say under what TERMS
the credit was taken. Every credit row now also carries a mandate_hash —
sha256 over the canonical mandate fields true at credit time (label/scope,
per-call max, allowlist, velocity, reason-required, rail, schema version).
The principal recomputes the hash over the CURRENT mandate; a mismatch voids
the credit's context. The store is only the messenger — it cannot soften a
changed mandate into a valid-looking row. Honest gaps, stated publicly:
row deletion still needs sequence continuity as a separate control; v1 has
no spend keys (operator-issued mandate, disclosed); Base USDC has no memo,
so on-chain binding rides an EIP-712 attestation in v2 (falsifiable claim,
not trustless); task_scope drift semantics are an open design question.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENVELOPE_DIR = BASE_DIR / "envelopes"
ENVELOPE_FILE = ENVELOPE_DIR / "envelopes.json"
RECEIPT_DIR = BASE_DIR / "receipts"

USDC_DECIMALS = 6
STATUSES = ("active", "suspended", "closed")
# Rail labels published on the public statement endpoint. v1 is Base-USDC
# only: top-ups are operator-attested after read-only on-chain verification
# of native USDC to the business wallet on Base mainnet, and every draw-down
# settles against that Base-USDC credit. The two fields are published per
# spend precisely so that the day they DIFFER (a cross-rail settle), the
# seam is visible in public — nanoswarm's composition-seam test (2026-09-24).
FUNDED_RAIL = "base-usdc"   # rail the principal's money arrived on
SETTLED_RAIL = "base-usdc"  # rail the seller accepted for this spend
_ID_RE = re.compile(r"^env_[0-9a-f]{12}$")
_WALLET_RE = re.compile(r"^0x[0-9a-f]{40}$")
_MAX_REASON_LEN = 500
_MAX_LABEL_LEN = 120
_MAX_STATEMENT_RECEIPTS = 100

_lock = threading.RLock()
_envelopes: dict[str, dict] | None = None
# Per-envelope sliding velocity windows (process-local, like core._hits).
_velocity: dict[str, list[float]] = {}

# MANDATE-HASH DESIGN (2026-09-25, from neodelvorn's void-on-context-change
# feedback on Moltbook): don't trust the log store for mandate integrity.
# Every credit row carries a mandate_hash — sha256 over the canonical mandate
# fields true at credit time (scope/label, per-call max, allowlist, velocity,
# reason-required, rail, schema version). The principal recomputes the hash
# over the CURRENT mandate; a mismatch means the credit's context changed and
# the credit is VOID — our store is only the messenger. Disclosing the hole
# beats a soft field that looks like control and is not.
# Honest gaps (stated publicly to neodelvorn 2026-09-25): row deletion still
# needs sequence continuity as a separate control; v1 has no spend keys, so
# there is no spend_key_id input (operator-issued mandate, disclosed); Base
# USDC has no memo, so on-chain binding rides an EIP-712 attestation in v2
# (falsifiable claim, not trustless). task_scope drift semantics are an open
# question back with neodelvorn.
MANDATE_SCHEMA_VERSION = "1"


def mandate_snapshot(env: dict) -> dict:
    """Canonical mandate fields true right now. This is the input to the
    mandate hash a principal recomputes to detect void-on-context-change."""
    return {
        "principal_wallet": env.get("principal_wallet"),
        "label": env.get("label"),
        "per_call_cap_atomic": env.get("per_call_cap_atomic"),
        "allowed_paths": sorted(env.get("allowed_paths") or []),
        "velocity_per_min": env.get("velocity_per_min"),
        "reason_required": bool(env.get("reason_required")),
        "rail": env.get("funded_rail", FUNDED_RAIL),
        "mandate_schema_version": MANDATE_SCHEMA_VERSION,
    }


def mandate_hash(snapshot: dict) -> str:
    """sha256 fingerprint of a mandate snapshot, canonicalized so the
    principal gets the same bytes we did."""
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_credit_mandate(env: dict, credit: dict) -> str:
    """Recompute the mandate hash for a credit row against the CURRENT
    mandate. 'bound' = context unchanged, 'void' = mandate changed since the
    credit landed (spend under it must not be treated as authorized).
    'legacy' = row predates mandate hashing (no hash recorded)."""
    recorded = credit.get("mandate_hash")
    if not recorded:
        return "legacy"
    return "bound" if recorded == mandate_hash(mandate_snapshot(env)) else "void"


def usd_to_atomic(usd: float) -> int:
    """0.0001 USDC -> 100 atomic units."""
    return int(round(float(usd) * 10**USDC_DECIMALS))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, dict]:
    global _envelopes
    with _lock:
        if _envelopes is None:
            _envelopes = {}
            try:
                if ENVELOPE_FILE.exists():
                    _envelopes = json.loads(ENVELOPE_FILE.read_text())
            except Exception:
                _envelopes = {}
        return _envelopes


def _save() -> None:
    """Atomic persist: tmp file in the same dir + os.replace, so a crash
    never leaves a half-written envelope ledger."""
    with _lock:
        ENVELOPE_DIR.mkdir(exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(ENVELOPE_DIR), prefix="envelopes.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(_envelopes, f, indent=2, sort_keys=True)
                f.write("\n")
            os.replace(tmp, ENVELOPE_FILE)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def _envelope_receipt_path(envelope_id: str) -> Path:
    return RECEIPT_DIR / f"envelope-{envelope_id}.jsonl"


def _append_envelope_receipt_line(envelope_id: str, entry: dict) -> None:
    RECEIPT_DIR.mkdir(exist_ok=True)
    with open(_envelope_receipt_path(envelope_id), "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# Admin: open / topup / status (all behind ADMIN_TOKEN in server.py)
# ---------------------------------------------------------------------------
def open_envelope(
    *,
    principal_wallet: object,
    label: object,
    usd_amount: object,
    per_call_cap: object,
    allowed_paths: object,
    velocity_per_min: object,
    reason_required: object,
    valid_wrappers: set[str],
) -> tuple[dict | None, str | None]:
    """Validate + create an envelope. Returns (record, None) or (None, err)."""
    try:
        amount = float(usd_amount)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, "usd_amount must be a number"
    if not (amount > 0):
        return None, "usd_amount must be > 0"
    try:
        cap = float(per_call_cap)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, "per_call_cap must be a number"
    if not (cap > 0):
        return None, "per_call_cap must be > 0"
    try:
        velocity = int(velocity_per_min)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, "velocity_per_min must be an integer"
    if not (1 <= velocity <= 120):
        return None, "velocity_per_min must be between 1 and 120"
    wallet = str(principal_wallet or "").strip().lower()
    if not _WALLET_RE.match(wallet):
        return None, "principal_wallet must be a 0x Ethereum address"
    if not isinstance(allowed_paths, list) or not allowed_paths:
        return None, "allowed_paths must be a non-empty list of wrapper names"
    unknown = [p for p in allowed_paths if p not in valid_wrappers]
    if unknown:
        return None, (
            f"allowed_paths contains unknown wrappers: {', '.join(unknown)} "
            f"(known: {', '.join(sorted(valid_wrappers))})"
        )
    label_s = str(label or "")[:_MAX_LABEL_LEN]
    envelope_id = "env_" + secrets.token_hex(6)
    record = {
        "id": envelope_id,
        "principal_wallet": wallet,
        "label": label_s,
        "balance_atomic": usd_to_atomic(amount),
        "per_call_cap_atomic": usd_to_atomic(cap),
        "allowed_paths": list(allowed_paths),
        "velocity_per_min": velocity,
        "reason_required": bool(reason_required),
        "status": "active",
        "funded_rail": FUNDED_RAIL,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "total_topped_up_atomic": usd_to_atomic(amount),
        "last_topup_at": now_iso(),
        "last_topup_tx": None,
        # Initial operator-attested credit, observable like any other.
        "credits": [],
    }
    # The initial credit is bound to the exact mandate terms at open time
    # (neodelvorn's mandate_hash design): the snapshot must come from the
    # finished record, so it is appended after the record is built.
    record["credits"] = [
        _credit_entry(None, usd_to_atomic(amount), mandate_snapshot(record))
    ]
    with _lock:
        envs = _load()
        while envelope_id in envs:  # astronomically unlikely, but free
            envelope_id = "env_" + secrets.token_hex(6)
            record["id"] = envelope_id
        envs[envelope_id] = record
        _save()
    return record, None


def _credit_entry(tx_hash: object, atomic: int, mandate: dict) -> dict:
    """One observable credit row: every credit carries its on-chain
    provenance so a principal can reconcile against Base directly, AND a
    mandate_hash binding the credit to the exact mandate terms true at
    credit time (neodelvorn's void-on-context-change design, 2026-09-25).
    The operator attests the credit in v1 (manual read-only on-chain
    verification); the tx hash makes the claim independently checkable.
    """
    tx = str(tx_hash or "")[:100] or None
    return {
        "ts": now_iso(),
        "tx_hash": tx,
        "amount_atomic": atomic,
        "amount_usdc": f"{atomic / 10**USDC_DECIMALS:.6f}",
        "rail": FUNDED_RAIL,
        "credited_by": "operator",
        "verification": (
            "manual read-only on-chain verification of the principal's "
            "native-USDC transfer; independently checkable at "
            f"https://basescan.org/tx/{tx}" if tx else
            "manual read-only on-chain verification of the principal's "
            "native-USDC transfer; no tx hash recorded — ask the operator "
            "for the provenance or decline this credit"
        ),
        # Mandate binding: the principal recomputes mandate_hash() over the
        # current mandate; a mismatch voids this credit's context.
        "mandate_schema_version": mandate.get(
            "mandate_schema_version", MANDATE_SCHEMA_VERSION
        ),
        "mandate": mandate,
        "mandate_hash": mandate_hash(mandate),
    }


def get_envelope(envelope_id: str) -> dict | None:
    with _lock:
        env = _load().get(envelope_id or "")
    return dict(env) if env else None


def topup_envelope(
    envelope_id: str, usd_amount: object, tx_hash: object = None
) -> tuple[dict | None, str | None]:
    """Record a credit the operator attested after READ-ONLY on-chain
    verification that the principal sent USDC to the business wallet.
    The code does no verification itself — verification is manual for v1."""
    try:
        amount = float(usd_amount)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, "usd_amount must be a number"
    if not (amount > 0):
        return None, "usd_amount must be > 0"
    atomic = usd_to_atomic(amount)
    with _lock:
        envs = _load()
        env = envs.get(envelope_id or "")
        if env is None:
            return None, f"unknown envelope id '{envelope_id}'"
        if env["status"] == "closed":
            return None, "envelope is closed; cannot top up"
        env["balance_atomic"] += atomic
        env["total_topped_up_atomic"] += atomic
        env["last_topup_at"] = now_iso()
        env["last_topup_tx"] = str(tx_hash or "")[:100] or None
        env["updated_at"] = now_iso()
        # Credit-observability rule: every credit is an observable row —
        # on-chain tx hash, amount, timestamp — appended to the envelope's
        # credit history AND the public receipt log, so a principal can
        # reconcile each credit against Base directly.
        # Mandate binding (2026-09-25, neodelvorn): the credit is hashed
        # against the mandate true right now; a later mandate change voids
        # this row's context on recompute.
        credit = _credit_entry(tx_hash, atomic, mandate_snapshot(env))
        env.setdefault("credits", []).append(credit)
        _append_envelope_receipt_line(envelope_id, {
            "type": "credit",
            "ts": credit["ts"],
            "tx_hash": credit["tx_hash"],
            "amount_atomic": atomic,
            "amount_usdc": credit["amount_usdc"],
            "rail": credit["rail"],
            "credited_by": credit["credited_by"],
            "mandate_hash": credit["mandate_hash"],
            "verification": credit["verification"],
            "balance_after_atomic": env["balance_atomic"],
        })
        _save()
        return dict(env), None


def set_envelope_status(envelope_id: str, status: object) -> tuple[dict | None, str | None]:
    status_s = str(status or "").strip().lower()
    if status_s not in STATUSES:
        return None, f"status must be one of {', '.join(STATUSES)}"
    with _lock:
        envs = _load()
        env = envs.get(envelope_id or "")
        if env is None:
            return None, f"unknown envelope id '{envelope_id}'"
        old_status = env.get("status")
        env["status"] = status_s
        env["updated_at"] = now_iso()
        _save()
        if old_status != status_s:
            _append_envelope_receipt_line(envelope_id, {
                "kind": "status_change",
                "ts": now_iso(),
                "from": old_status,
                "to": status_s,
            })
        return dict(env), None


# ---------------------------------------------------------------------------
# Agent drawdown: jarviscooper's rule — ambiguity -> NO purchase.
# ---------------------------------------------------------------------------
def _decline(error: str) -> dict:
    return {"status": 402, "code": "ENVELOPE_DECLINED", "error": error}


def try_spend(
    envelope_id: object,
    wrapper_name: str,
    price_atomic: int,
    reason: object,
) -> tuple[dict | None, dict | None]:
    """Authorize + atomically decrement one envelope call.

    Returns (pending_spend, None) on success, or (None, err) where err has
    keys status/code/error. On ANY failure the envelope is untouched:
    never decremented, never charged, never forwarded.
    """
    env_id = str(envelope_id or "").strip()
    if not _ID_RE.match(env_id):
        return None, _decline(f"unknown envelope id '{env_id}'")
    reason_s = str(reason).strip() if reason is not None else None
    if reason_s is not None and len(reason_s) > _MAX_REASON_LEN:
        return None, _decline(
            f"reason malformed: longer than {_MAX_REASON_LEN} chars"
        )
    with _lock:
        env = _load().get(env_id)
        if env is None:
            return None, _decline(f"unknown envelope id '{env_id}'")
        if env["status"] != "active":
            return None, _decline(
                f"envelope {env_id} is {env['status']}; drawdown refused"
            )
        if env.get("reason_required") and not reason_s:
            return None, {
                "status": 400,
                "code": "REASON_REQUIRED",
                "error": (
                    "this envelope's principal requires an explicit reason "
                    "for every call: retry with header "
                    "X-Reason: <why you are making this call>"
                ),
            }
        if wrapper_name not in (env.get("allowed_paths") or []):
            return None, _decline(
                f"'{wrapper_name}' is not in this envelope's allowed endpoints "
                f"({', '.join(env.get('allowed_paths') or [])})"
            )
        if price_atomic > env["per_call_cap_atomic"]:
            return None, _decline(
                f"endpoint price ({price_atomic} atomic USDC) exceeds this "
                f"envelope's per-call cap ({env['per_call_cap_atomic']} atomic)"
            )
        if env["balance_atomic"] < price_atomic:
            return None, _decline(
                f"envelope balance ({env['balance_atomic']} atomic USDC) is "
                f"below the endpoint price ({price_atomic} atomic)"
            )
        now = time.time()
        window = [t for t in _velocity.get(env_id, []) if now - t < 60]
        if len(window) >= env["velocity_per_min"]:
            _velocity[env_id] = window
            return None, _decline(
                f"envelope velocity cap tripped ({env['velocity_per_min']}/min); "
                "wait before retrying"
            )
        # All checks passed: commit atomically.
        before = env["balance_atomic"]
        env["balance_atomic"] = before - price_atomic
        env["updated_at"] = now_iso()
        window.append(now)
        _velocity[env_id] = window
        pending = {
            "call_id": "call_" + secrets.token_hex(6),
            "ts": now_iso(),
            "envelope_id": env_id,
            "wrapper": wrapper_name,
            "price_atomic": price_atomic,
            "reason": reason_s,
            "buyer_rail": env.get("funded_rail", FUNDED_RAIL),
            "balance_before_atomic": before,
            "balance_after_atomic": env["balance_atomic"],
        }
        _save()
    return pending, None


def finalize_spend(pending: dict, upstream_status: int, latency_ms: int) -> dict:
    """Write the envelope receipt line (authorization -> delivery) and return
    the receipt object to attach to the agent response."""
    line = {
        "type": "spend",
        "call_id": pending["call_id"],
        "ts": pending["ts"],
        "wrapper": pending["wrapper"],
        "price_atomic": pending["price_atomic"],
        "settled_rail": SETTLED_RAIL,
        "buyer_rail": pending.get("buyer_rail", FUNDED_RAIL),
        "reason": pending["reason"],
        "upstream_status": upstream_status,
        "latency_ms": latency_ms,
        "balance_before_atomic": pending["balance_before_atomic"],
        "balance_after_atomic": pending["balance_after_atomic"],
    }
    _append_envelope_receipt_line(pending["envelope_id"], line)
    return {
        "type": "envelope",
        "envelope_id": pending["envelope_id"],
        "call_id": pending["call_id"],
        "wrapper": pending["wrapper"],
        "price_atomic": pending["price_atomic"],
        "settled_rail": SETTLED_RAIL,
        "buyer_rail": pending.get("buyer_rail", FUNDED_RAIL),
        "reason": pending["reason"],
        "balance_remaining_atomic": pending["balance_after_atomic"],
        "upstream_status": upstream_status,
        "latency_ms": latency_ms,
        # Signed-style receipt: this is an OPERATOR-ISSUED mandate recorded
        # after verified on-chain top-up (v1). Principal-signed mandates
        # (EIP-712) are v2 — never claimed here.
        "authorization": (
            "operator-issued envelope mandate (v1, prepaid credit against "
            "verified on-chain top-up); principal-signed mandates are v2"
        ),
    }


def statement(envelope_id: str) -> dict | None:
    """Public statement: status, balance, policy summary, and this
    envelope's receipt lines. Never includes other envelopes' data."""
    env = get_envelope(envelope_id)
    if env is None:
        return None
    receipts: list[dict] = []
    path = _envelope_receipt_path(env["id"])
    if path.exists():
        try:
            lines = path.read_text().splitlines()
            for raw in lines[-_MAX_STATEMENT_RECEIPTS:]:
                receipts.append(json.loads(raw))
        except Exception:
            pass
    # Mandate recompute-bind (2026-09-25, neodelvorn): each credit row is
    # annotated with its status against the CURRENT mandate — 'bound' means
    # the context is unchanged, 'void' means the mandate moved under it.
    mandate = mandate_snapshot(env)
    credits = []
    for c in env.get("credits", []):
        annotated = dict(c)
        annotated["mandate_status"] = verify_credit_mandate(env, c)
        credits.append(annotated)
    return {
        "envelope_id": env["id"],
        "principal_wallet": env["principal_wallet"],
        "label": env["label"],
        "status": env["status"],
        "funded_rail": env.get("funded_rail", FUNDED_RAIL),
        "balance_atomic": env["balance_atomic"],
        "balance_usdc": f"{env['balance_atomic'] / 10**USDC_DECIMALS:.6f}",
        "policy": {
            "per_call_cap_atomic": env["per_call_cap_atomic"],
            "allowed_paths": env["allowed_paths"],
            "velocity_per_min": env["velocity_per_min"],
            "reason_required": env["reason_required"],
        },
        "total_topped_up_atomic": env["total_topped_up_atomic"],
        # The current mandate and its fingerprint: the principal recomputes
        # mandate_hash over their own mandate terms and compares — that
        # comparison, not our store, is what voids stale credits.
        "mandate": mandate,
        "mandate_hash": mandate_hash(mandate),
        # Credit-observability rule (2026-09-24): full credit history on the
        # public statement — every credit carries its on-chain tx hash so a
        # principal reconciles against Base directly instead of trusting
        # the operator's assertion.
        # Mandate-hash rule (2026-09-25, neodelvorn): each credit row also
        # carries mandate_schema_version + mandate + mandate_hash, and is
        # annotated with mandate_status (bound/void/legacy) recomputed
        # against the current mandate.
        "credit_history": credits,
        "created_at": env["created_at"],
        "updated_at": env["updated_at"],
        "receipts": receipts,
    }
