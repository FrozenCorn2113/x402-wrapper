"""FastAPI x402 proxy. Mock payments by default; live on-chain USDC verification
when MOCK_PAYMENTS=false and a real PAY_TO_ADDRESS is configured."""
from __future__ import annotations

import os
import time

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

import core

app = FastAPI(title="x402 Middleman Wrapper")
WRAPPERS = core.load_configs()


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


@app.api_route("/v1/{name}", methods=["GET", "POST"])
async def proxy(name: str, request: Request, x_payment_proof: str | None = Header(default=None)):
    wrapper = WRAPPERS.get(name)
    if not wrapper:
        return JSONResponse({"error": f"unknown wrapper '{name}'"}, status_code=404)

    if not core.verify_payment(x_payment_proof, wrapper):
        return JSONResponse(core.make_402(wrapper), status_code=402)

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
    receipt = core.log_receipt(wrapper, x_payment_proof or "", status, latency_ms)

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
