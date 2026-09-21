"""MCP server (stdio) exposing each wrapper as a priced tool.

Run:  .venv/bin/python mcp_server.py
Speak MCP over stdin/stdout with newline-delimited JSON-RPC.
"""
from __future__ import annotations

import json
import sys
import time

import core

WRAPPERS = core.load_configs()


def tool_def(name: str, wrapper: dict) -> dict:
    price = wrapper["pricing"]["price_usdc"]
    params = wrapper["upstream"].get("passthrough_params", [])
    properties = {p: {"type": "string", "description": f"Upstream query param '{p}'"} for p in params}
    if core.mock_payments_enabled():
        proof_desc = (
            "x402 payment proof for this call (mock mode: any string starting "
            "with 'mock-'; switch to live mode with MOCK_PAYMENTS=false and a "
            "real PAY_TO_ADDRESS)."
        )
    else:
        proof_desc = (
            "x402 payment proof: a Base mainnet transaction hash (0x + 64 hex) "
            "of a USDC transfer to the service address covering this call's price."
        )
    properties["payment_proof"] = {"type": "string", "description": proof_desc}
    return {
        "name": name,
        "description": (
            f"{wrapper.get('description', '')} Costs ${price} USDC per call "
            f"(x402, {wrapper['pricing'].get('network', 'base')}). "
            "Pay per call; include payment_proof."
        ),
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": ["payment_proof"],
        },
    }


def handle(msg: dict):
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"protocolVersion": "2024-11-05",
                           "capabilities": {"tools": {}},
                           "serverInfo": {"name": "x402-wrapper-v1", "version": "0.1.0"}}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"tools": [tool_def(n, w) for n, w in WRAPPERS.items()]}}
    if method == "tools/call":
        p = msg.get("params", {})
        name = p.get("name")
        args = p.get("arguments", {}) or {}
        wrapper = WRAPPERS.get(name)
        if not wrapper:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": f"unknown tool '{name}'"}}
        proof = args.get("payment_proof")
        if not core.verify_payment(proof, wrapper):
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text",
                        "text": "PAYMENT REQUIRED (402): " + json.dumps(core.make_402(wrapper))}],
                        "isError": True}}
        if not core.check_rate_limit(wrapper):
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text", "text": "rate limit exceeded"}],
                               "isError": True}}
        params = {k: v for k, v in args.items() if k != "payment_proof"}
        started = time.time()
        status, data = core.forward(wrapper, params)
        latency_ms = int((time.time() - started) * 1000)
        core.log_receipt(wrapper, proof, status, latency_ms)
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"content": [{"type": "text",
                    "text": json.dumps({"data": data,
                                        "price_usdc": wrapper["pricing"]["price_usdc"],
                                        "mock_settlement": core.mock_payments_enabled()}, indent=2)}]}}
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"unknown method '{method}'"}}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            resp = handle(json.loads(line))
        except Exception as exc:  # noqa: BLE001
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32603, "message": str(exc)[:200]}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
