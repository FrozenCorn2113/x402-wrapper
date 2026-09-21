"""FastAPI x402 proxy. Mock payments by default; live on-chain USDC verification
when MOCK_PAYMENTS=false and a real PAY_TO_ADDRESS is configured."""
from __future__ import annotations

import os
import time

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, PlainTextResponse

import core

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
- weather-now — $0.005/call — Current weather and forecast for any latitude/longitude (via Open-Meteo). Params: latitude, longitude, current, hourly, daily, timezone, forecast_days.
- crypto-price — $0.01/call — Crypto spot prices (via CoinGecko). Params: ids, vs_currencies.
- echo — $0.001/call — Test endpoint that echoes your params back. Params: any.

Machine-readable catalog: GET {base}/v1
Discovery manifest: GET {base}/.well-known/x402
Health: GET {base}/health
Network: Base. Asset: USDC. Receipts are returned with every paid call.
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
    return {"wrappers": core.catalog()}


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


@app.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt():
    """Plain-language service description for agent/LLM discovery."""
    return llms_text()


@app.api_route("/v1/{name}", methods=["GET", "POST"])
async def proxy(
    name: str,
    request: Request,
    x_payment: str | None = Header(default=None),
    payment_signature: str | None = Header(default=None),
    x_payment_proof: str | None = Header(default=None),  # legacy alias
):
    wrapper = WRAPPERS.get(name)
    if not wrapper:
        return JSONResponse({"error": f"unknown wrapper '{name}'"}, status_code=404)

    proof = x_payment or payment_signature or x_payment_proof

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
