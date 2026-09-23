"""FastAPI x402 proxy. Mock payments by default; live on-chain USDC verification
when MOCK_PAYMENTS=false and a real PAY_TO_ADDRESS is configured."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse

import circuit_breaker
import challenge_log
import core
import envelopes

app = FastAPI(title="x402 Middleman Wrapper")
WRAPPERS = core.load_configs()

SERVICE_DESCRIPTION = (
    "Pay-per-call API proxy for AI agents. Wraps ordinary data APIs behind the "
    "x402 v2 payment protocol: agents pay a few cents in USDC per call on Base — "
    "no API keys, accounts, or subscriptions. Call an endpoint without payment "
    "to get HTTP 402 with a standard x402 v2 PaymentRequired challenge "
    "(PAYMENT-REQUIRED header), pay by direct USDC transfer, then retry with "
    "the Base transaction hash in the X-Payment header."
)


def llms_text() -> str:
    base = core.public_base_url()
    return f"""# x402-wrapper

{SERVICE_DESCRIPTION}

Base URL: {base}

## How to pay
1. GET an endpoint below with no payment -> HTTP 402 with an x402 v2 PaymentRequired
   challenge (also base64-encoded in the PAYMENT-REQUIRED response header).
2. Send USDC on Base to the payTo address for at least the listed amount.
3. Retry the same request with header `X-Payment: <base-tx-hash>`.
   (Legacy `X-Payment-Proof` header is still accepted.)

## Endpoints
- weather-now — $0.0005/call — Current weather and forecast for any latitude/longitude (via Open-Meteo). Params: latitude, longitude, current, hourly, daily, timezone, forecast_days.
- crypto-price — $0.001/call — Crypto spot prices (via CoinGecko). Params: ids, vs_currencies.
- echo — $0.0001/call — Test endpoint that echoes your params back. Params: any.

## Loop protection (free, always on)
This proxy watches for runaway agents: 25+ identical calls from one client
within 60 seconds trips a 5-minute cooldown for that exact request shape
(HTTP 429, code AGENT_LOOP_DETECTED, Retry-After header). You are never
charged for blocked calls. It is financial insurance for autonomous loops —
tune via LOOP_* env vars. Verify it yourself: GET {base}/v1/loop-protection
returns the policy plus live block counters (loops_tripped,
loop_blocked_calls, rate_blocked_calls) and an honesty note explaining how
to falsify the policy independently — 25+ identical unpaid calls to any
/v1/{{wrapper}} must return HTTP 429 AGENT_LOOP_DETECTED.
Freshness beacon: GET {base}/v1/freshness shows the last independently
submitted challenge-harness result (last_independently_challenged_at,
challenged_by) measured against the published challenge cadence, so
staleness is visible without trusting us. Run the harness, then POST your
result to {base}/v1/challenge-log (public, append-only); the full log is
GET {base}/v1/challenge-log. Operator runs are never logged — your
independence is the whole point. Hold your own copy: GET
{base}/v1/challenge-log/export returns the canonical JSONL plus a SHA-256
document digest — one holder detects post-pull edits, two holders
cross-comparing head hashes close the quiet-edit window.

Machine-readable catalog: GET {base}/v1
Discovery manifest: GET {base}/.well-known/x402
Health: GET {base}/health
Network: Base. Asset: USDC. Receipts are returned with every paid call.

## Envelopes (prepaid budgets)
Some agents run under a funded principal that cannot authorize per-call spend
(jarviscooper's trust doctrine: the mandate must be signed by the PRINCIPAL,
invalidation must be enforced where the money is, ambiguity resolves to NO
purchase). Envelopes are the answer: a prepaid, policy-bounded budget the
agent draws down without touching the principal's wallet per call.
1. The principal sends USDC on Base to {core.resolve_pay_to(next(iter(WRAPPERS.values()))) if WRAPPERS else 'payTo from GET /v1'}.
2. The operator verifies the transfer read-only on-chain, then opens or tops up
   an envelope for the principal's wallet (operator-only admin API).
3. The agent calls /v1/{{wrapper}} with header `X-Envelope: <envelope id>`, and
   `X-Reason: <why you are making this call>` when the principal's policy
   requires it.
Policy enforced before every call: envelope active, balance covers the price,
price within the per-call cap, endpoint in the allowed list, per-envelope
velocity cap (per minute). Envelope calls SKIP the 402 x402 flow entirely —
no X-Payment needed. Any ambiguity (unknown/suspended/closed envelope, cap
exceeded, short balance, velocity tripped, missing or malformed reason)
refuses with HTTP 402 code ENVELOPE_DECLINED: nothing is decremented,
charged, or forwarded. Statement and per-envelope receipts: GET
{base}/v1/envelopes/{{id}} (public).

HONESTY NOTE: v1 envelopes are OPERATOR-ISSUED mandates recorded only after
verified on-chain top-ups (principal -> business wallet, read-only
verification by the operator). Principal-signed mandates (EIP-712) are v2,
not yet built. We do not hold customer keys and cannot move customer funds.
"""


@app.get("/health")
def health():
    return {
        "ok": True,
        "wrappers": sorted(WRAPPERS),
        "mode": "live" if not core.mock_payments_enabled() else "mock",
        "pay_to": (core.resolve_pay_to(next(iter(WRAPPERS.values())))
                   if WRAPPERS else None),
    }


@app.get("/v1")
def list_wrappers():
    """Machine-readable catalog: what agents can buy and for how much."""
    return {
        "wrappers": core.catalog(),
        "loop_protection": circuit_breaker.describe(),
        "envelope_support": True,
    }


@app.get("/v1/freshness")
def freshness_beacon():
    """Freshness beacon: last independent breaker challenge + staleness.

    Answers clawdsmith's "who checks, and how often" critique: the last
    independently-submitted challenge harness result, measured against the
    published cadence, so staleness is visible to a lazy buyer without
    trusting operator-published counters.
    """
    return challenge_log.freshness_report()


@app.get("/v1/challenge-log")
def get_challenge_log(limit: int = 100):
    """Public append-only log of independent breaker challenge results."""
    return {
        "challenges": challenge_log.read_all(min(max(limit, 1), 500)),
        "submit": "POST /v1/challenge-log",
        "export": "GET /v1/challenge-log/export",
    }


@app.get("/v1/challenge-log/export")
def export_challenge_log():
    """Canonical challenger-pull export of the whole challenge log.

    clawdsmith (Moltbook, 2026-09-23) asked how many challengers hold a
    copy and what minimum prevents quiet edits. This is the copy a
    challenger holds: one puller detects post-pull edits, two holders
    cross-comparing head_hash / document_digest_sha256 close the window.
    """
    return challenge_log.export_document()


@app.post("/v1/challenge-log")
async def post_challenge_log(request: Request):
    """Submit an independent breaker challenge result.

    Body (JSON): challenged_by (<=200 chars), challenge_type (<=100),
    result in [pass, fail, inconclusive], details (<=2000). Append-only;
    operator runs are never logged here — independence is the submitter's.
    """
    if not client_identity(request):
        return JSONResponse({"error": "identity required"}, status_code=400)
    raw = await request.body()
    if len(raw) > 8192:
        return JSONResponse({"error": "body too large (8KB max)"}, status_code=413)
    try:
        body = json.loads(raw) if raw else {}
    except Exception:
        return JSONResponse({"error": "body must be valid JSON"}, status_code=400)
    entry, err = challenge_log.submit(body)
    if err:
        return JSONResponse({"error": err}, status_code=422)
    return JSONResponse(entry, status_code=201)


def admin_authorized(authorization: str | None) -> bool:
    """Bearer check against the ADMIN_TOKEN env var. No token configured or
    a bad token -> False. Timing-safe compare."""
    configured = os.environ.get("ADMIN_TOKEN", "").strip()
    if not configured or not authorization:
        return False
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return False
    return hmac.compare_digest(value.strip(), configured)


def _require_admin(authorization: str | None):
    if not admin_authorized(authorization):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return None


@app.post("/v1/admin/envelopes", status_code=201)
async def admin_open_envelope(
    request: Request, authorization: str | None = Header(default=None)
):
    """Open a prepaid envelope. Operator-only: the operator calls this ONLY
    after read-only on-chain verification that the principal sent USDC to
    the business wallet. Body: {principal_wallet, label, usd_amount,
    per_call_cap, allowed_paths, velocity_per_min, reason_required}."""
    denied = _require_admin(authorization)
    if denied:
        return denied
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "body must be valid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    record, err = envelopes.open_envelope(
        principal_wallet=body.get("principal_wallet"),
        label=body.get("label"),
        usd_amount=body.get("usd_amount"),
        per_call_cap=body.get("per_call_cap"),
        allowed_paths=body.get("allowed_paths"),
        velocity_per_min=body.get("velocity_per_min"),
        reason_required=body.get("reason_required"),
        valid_wrappers=set(WRAPPERS),
    )
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return JSONResponse({"envelope": record}, status_code=201)


@app.post("/v1/admin/envelopes/{envelope_id}/topup")
async def admin_topup_envelope(
    envelope_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Record credit after MANUAL read-only on-chain verification of the
    principal's USDC transfer. The server does no verification itself.
    Body: {usd_amount, tx_hash?} — the tx hash is recorded for audit."""
    denied = _require_admin(authorization)
    if denied:
        return denied
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "body must be valid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    record, err = envelopes.topup_envelope(
        envelope_id, body.get("usd_amount"), body.get("tx_hash")
    )
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return JSONResponse({"envelope": record})


@app.post("/v1/admin/envelopes/{envelope_id}/status")
async def admin_envelope_status(
    envelope_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    """Suspend or close an envelope. Body: {status} in [active, suspended, closed]."""
    denied = _require_admin(authorization)
    if denied:
        return denied
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "body must be valid JSON"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    record, err = envelopes.set_envelope_status(envelope_id, body.get("status"))
    if err:
        return JSONResponse({"error": err}, status_code=400)
    return JSONResponse({"envelope": record})


@app.get("/v1/envelopes/{envelope_id}")
def envelope_statement(envelope_id: str):
    """Public statement for one envelope: status, balance, policy summary,
    and that envelope's receipt lines. Never exposes other envelopes' data."""
    stmt = envelopes.statement(envelope_id)
    if stmt is None:
        return JSONResponse(
            {"error": f"unknown envelope id '{envelope_id}'"}, status_code=404
        )
    return stmt


@app.get("/v1/loop-protection")
def loop_protection_report():
    """Pollable loop-protection policy + live block counters.

    Answers the buyer-verifiability question: poll this to see the loop
    policy and what the breaker has actually blocked. Honest framing —
    counters are process-local and operator-published; the response's
    honesty field states exactly how to falsify the policy independently.
    """
    return circuit_breaker.public_report()


@app.get("/.well-known/x402")
def well_known_x402():
    """Unprotected discovery manifest for x402 directories (e.g. x402scan)."""
    base = core.public_base_url()
    catalog = core.catalog()
    return {
        "x402Version": core.X402_VERSION,
        "name": "x402-wrapper",
        "description": SERVICE_DESCRIPTION,
        "baseUrl": base,
        "catalog": f"{base}/v1",
        "network": os.environ.get("NETWORK", "").strip() or "base",
        "asset": "USDC",
        "payTo": catalog[0]["pay_to"] if catalog else None,
        "endpoints": [
            {
                "path": f"/v1/{e['name']}",
                "url": e["endpoint"],
                "description": e["description"],
                "method": e["method"],
                "params": e["params"],
                "price_usdc": e["price_usdc"],
            }
            for e in catalog
        ],
    }


@app.get("/.well-known/402index-verify.txt", response_class=PlainTextResponse)
def index_402_verify():
    """Domain-ownership verification for 402index.io (serves the claim hash)."""
    h = os.environ.get("INDEX_402_VERIFICATION_HASH", "").strip()
    if not h:
        return PlainTextResponse("unverified\n", status_code=404)
    return h + "\n"


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    """Plain-language service description for agent/LLM discovery."""
    return llms_text()


def client_identity(request: Request) -> str:
    """Stable caller id for loop detection.

    Uses the first X-Forwarded-For hop (Render sets this) or the peer IP.
    Payment proofs are deliberately excluded: replay protection forces a
    fresh proof per paid call, so a looping agent rotates proofs while the
    client address stays stable.
    """
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else ""
    if not ip and request.client:
        ip = request.client.host
    return "ip:" + hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]


@app.api_route("/v1/{name}", methods=["GET", "POST"])
async def proxy(
    name: str,
    request: Request,
    x_payment: str | None = Header(default=None),
    payment_signature: str | None = Header(default=None),
    x_payment_proof: str | None = Header(default=None),  # legacy alias
    x_envelope: str | None = Header(default=None),
    x_reason: str | None = Header(default=None),
):
    wrapper = WRAPPERS.get(name)
    if not wrapper:
        return JSONResponse({"error": f"unknown wrapper '{name}'"}, status_code=404)

    # Loop protection sits BEFORE payment verification: a stuck agent gets a
    # cheap 429 here instead of burning USDC on identical paid calls, and we
    # never forward looping traffic upstream.
    identity = client_identity(request)
    pairs = sorted(request.query_params.multi_items())
    body = await request.body()
    fp = circuit_breaker.payload_fingerprint(
        request.method, request.url.path, urlencode(pairs), body
    )
    verdict = circuit_breaker.breaker.check(identity, fp)
    if verdict is not None:
        return JSONResponse(
            verdict["error"],
            status_code=429,
            headers={
                "Retry-After": str(verdict["retry_after"]),
                "X-Loop-Protection": "tripped",
            },
        )

    proof = x_payment or payment_signature or x_payment_proof

    # Envelope drawdown: a prepaid principal budget. Policy is checked BEFORE
    # any payment flow; passing calls SKIP the 402 x402 flow entirely. Any
    # ambiguity (unknown/suspended envelope, cap exceeded, short balance,
    # velocity tripped, missing/malformed reason) refuses with 402
    # ENVELOPE_DECLINED — never decremented, charged, or forwarded.
    if x_envelope:
        price_atomic = int(core.price_to_atomic(wrapper["pricing"]["price_usdc"]))
        pending, env_err = envelopes.try_spend(
            x_envelope, name, price_atomic, x_reason
        )
        if env_err:
            return JSONResponse(
                {
                    "code": env_err["code"],
                    "error": env_err["error"],
                    "envelope_id": str(x_envelope or "").strip(),
                },
                status_code=env_err["status"],
            )
        if not core.check_rate_limit(wrapper):
            return JSONResponse({"error": "rate limit exceeded"}, status_code=429)
        params = dict(request.query_params)
        if request.method == "POST":
            try:
                body = await request.json()
                if isinstance(body, dict):
                    params.update({k: str(v) for k, v in body.items()})
            except Exception:
                pass
        started = time.time()
        status, data = core.forward(wrapper, params)
        latency_ms = int((time.time() - started) * 1000)
        receipt = envelopes.finalize_spend(pending, status, latency_ms)
        return JSONResponse({"data": data, "receipt": receipt}, status_code=status)

    # A base64 x402 PaymentPayload (EIP-3009 authorization) can't be settled by
    # us directly — tell the agent how to pay instead of silently rejecting.
    if proof and core.looks_like_payment_payload(proof):
        challenge = core.make_402(wrapper)
        challenge["error"] = (
            "direct-transfer settlement: this server does not submit "
            "EIP-3009 authorizations. Send the USDC directly to payTo, then "
            "retry with the transaction hash in the X-Payment header."
        )
        return JSONResponse(
            challenge, status_code=402, headers=core.payment_required_headers(wrapper)
        )

    if not core.verify_payment(proof, wrapper):
        return JSONResponse(
            core.make_402(wrapper),
            status_code=402,
            headers=core.payment_required_headers(wrapper),
        )

    if not core.check_rate_limit(wrapper):
        return JSONResponse({"error": "rate limit exceeded"}, status_code=429)

    params = dict(request.query_params)
    if request.method == "POST":
        try:
            body = await request.json()
            if isinstance(body, dict):
                params.update({k: str(v) for k, v in body.items()})
        except Exception:
            pass

    started = time.time()
    status, data = core.forward(wrapper, params)
    latency_ms = int((time.time() - started) * 1000)
    receipt = core.log_receipt(wrapper, proof or "", status, latency_ms)

    return JSONResponse(
        {
            "data": data,
            "receipt": {
                "wrapper": receipt["wrapper"],
                "price_usdc": receipt["price_usdc"],
                "payment_proof_fp": receipt["payment_proof_fp"],
                "mock_settlement": receipt["mock_settlement"],
            },
        },
        status_code=status,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
