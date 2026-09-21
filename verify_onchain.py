"""Real on-chain USDC payment verification for Base mainnet.

Given a transaction hash, this checks via a free public Base RPC that the
transaction contains a USDC `Transfer` event paying >= the required amount to
our address.

Read-only: no private keys, no signing, no wallet access. Only enabled when
MOCK_PAYMENTS=false (which happens automatically once a real PAY_TO_ADDRESS
is configured); mock mode is the default until Brett supplies his wallet.
"""
from __future__ import annotations

import os
import re

import httpx

import core

# keccak256("Transfer(address,address,uint256)") - the ERC-20 Transfer event.
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
DEFAULT_RPC = "https://mainnet.base.org"  # free public Base RPC (rate-limited)


def rpc_url() -> str:
    return os.environ.get("BASE_RPC_URL", "").strip() or DEFAULT_RPC


def _rpc(method: str, params: list) -> object:
    """Single JSON-RPC call. Raises on transport or RPC errors."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    with httpx.Client(**core.http_client_kwargs()) as client:
        resp = client.post(
            rpc_url(), json=payload, headers={"Content-Type": "application/json"}
        )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def verify_tx_hash(
    tx_hash: str, required_atomic: int, pay_to: str, usdc_contract: str
) -> tuple[bool, str]:
    """Check that `tx_hash` moved >= `required_atomic` USDC to `pay_to`.

    Returns (ok, reason). Amounts are in USDC atomic units (6 decimals).
    """
    tx_hash = (tx_hash or "").strip()
    if not TX_HASH_RE.match(tx_hash):
        return False, "proof is not a valid transaction hash (expected 0x + 64 hex)"

    try:
        receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean rejection
        return False, f"rpc lookup failed: {str(exc)[:120]}"
    if receipt is None:
        return False, "transaction not found (not mined yet?)"
    if not isinstance(receipt, dict) or receipt.get("status") not in ("0x1", 1):
        return False, "transaction failed on-chain"

    # The `to` address, left-padded to 32 bytes as it appears in topics[2].
    want_to = pay_to.lower().replace("0x", "").rjust(64, "0")
    want_contract = usdc_contract.lower()

    for log in receipt.get("logs") or []:
        if not isinstance(log, dict):
            continue
        if (log.get("address") or "").lower() != want_contract:
            continue  # not a USDC log
        topics = log.get("topics") or []
        if len(topics) < 3 or (topics[0] or "").lower() != TRANSFER_TOPIC:
            continue  # not a Transfer event
        to_topic = (topics[2] or "").lower().replace("0x", "")
        if to_topic != want_to:
            continue  # Transfer went somewhere else
        try:
            amount = int(log.get("data") or "0x0", 16)
        except (ValueError, TypeError):
            continue
        if amount >= required_atomic:
            return True, (
                f"verified on-chain USDC transfer of {amount} atomic units "
                f"to {pay_to} in {tx_hash}"
            )
    return False, "no USDC transfer to pay_to of >= required amount in tx logs"


if __name__ == "__main__":
    # Smoke self-test with a fabricated receipt (no network needed).
    import json as _json

    _fake_receipt = {
        "status": "0x1",
        "logs": [
            {
                "address": core.usdc_contract(),
                "topics": [
                    TRANSFER_TOPIC,
                    "0x000000000000000000000000" + "a" * 40,  # from
                    "0x000000000000000000000000" + "b" * 40,  # to
                ],
                "data": hex(5_000),  # $0.005
            }
        ],
    }

    _orig = _rpc
    globals()["_rpc"] = lambda m, p: _fake_receipt  # noqa: F841 - monkeypatch
    try:
        ok, reason = verify_tx_hash(
            "0x" + "c" * 64, 5_000, "0x" + "B" * 40, core.usdc_contract()
        )
        assert ok, f"expected True, got: {reason}"
        ok, reason = verify_tx_hash(
            "0x" + "c" * 64, 5_001, "0x" + "B" * 40, core.usdc_contract()
        )
        assert not ok, f"expected False (underpaid), got: {reason}"
        ok, reason = verify_tx_hash("not-a-hash", 1, "0x" + "B" * 40, core.usdc_contract())
        assert not ok, f"expected False (bad hash), got: {reason}"
        print("verify_onchain self-test: OK")
    finally:
        globals()["_rpc"] = _orig
