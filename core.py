"""Shared core: wrapper configs, mock x402 verification, upstream forwarding, receipts."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

BASE_DIR = Path(__file__).resolve().parent
CONFIG_DIR = BASE_DIR / "configs"
RECEIPT_DIR = BASE_DIR / "receipts"

PLACEHOLDER_PAY_TO = "0xREPLACE_ME_BEFORE_DEPLOY"
# USDC token contract on Base mainnet (used by the on-chain verifier).
BASE_USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# Sandbox-only egress glue fingerprint; never present on Render/Railway/Fly.
_HATCH_CA = "/usr/local/share/ca-certificates/hatch-egress-ca.crt"
USDC_DECIMALS = 6
X402_VERSION = 2

# Human network names -> CAIP-2 chain ids (x402 v2 requires CAIP-2).
NETWORK_CAIP2 = {
    "base": "eip155:8453",
    "base-sepolia": "eip155:84532",
    "ethereum": "eip155:1",
    "sepolia": "eip155:11155111",
    "polygon": "eip155:137",
    "avalanche": "eip155:43114",
}


def network_to_caip2(name: str) -> str:
    """'base' -> 'eip155:8453'. Passes through values already in CAIP-2 form."""
    name = (name or "").strip()
    if ":" in name:
        return name
    return NETWORK_CAIP2.get(name.lower(), name or "eip155:8453")


# --- environment-driven config (12-factor; nothing secret lives in YAML) ---
def in_sandbox() -> bool:
    """True only inside the Hatch dev sandbox. Never true on normal hosts."""
    return bool(os.environ.get("HATCH_EGRESS")) or os.path.exists(_HATCH_CA)


def http_client_kwargs() -> dict:
    """httpx.Client kwargs. Normal hosts get plain defaults; the sandbox gets
    its proxy/CA glue. Used for upstream forwarding AND Base RPC calls."""
    if not in_sandbox():
        return {"trust_env": True, "timeout": 20.0}
    # Sandbox: httpx's env parsing chokes on the rotating proxy creds, so pass
    # the proxy explicitly and trust the egress MITM CA.
    proxy_url = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    verify: str | bool = _HATCH_CA if os.path.exists(_HATCH_CA) else True
    return {
        "proxy": httpx.Proxy(url=proxy_url) if proxy_url else None,
        "trust_env": False,
        "timeout": 20.0,
        "verify": verify,
    }


def usdc_contract() -> str:
    """USDC token contract address on the configured network."""
    return os.environ.get("USDC_ASSET", "").strip() or BASE_USDC_CONTRACT


def resolve_pay_to(wrapper: dict) -> str:
    """PAY_TO_ADDRESS env wins; falls back to the wrapper YAML value."""
    return os.environ.get("PAY_TO_ADDRESS", "").strip() or wrapper.get("pricing", {}).get(
        "pay_to", PLACEHOLDER_PAY_TO
    )


def mock_payments_enabled() -> bool:
    """True by default; flips off automatically once a real wallet address is
    configured, or explicitly via MOCK_PAYMENTS=false."""
    raw = os.environ.get("MOCK_PAYMENTS")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "y", "on")
    pt = os.environ.get("PAY_TO_ADDRESS", "").strip()
    return not (pt.startswith("0x") and pt != PLACEHOLDER_PAY_TO and len(pt) == 42)


def load_configs() -> dict[str, dict]:
    wrappers: dict[str, dict] = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        with open(path) as f:
            cfg = yaml.safe_load(f)
        wrappers[cfg["name"]] = cfg
    return wrappers


def price_to_atomic(price_usdc: str) -> str:
    """'0.005' USDC -> '5000' atomic units."""
    return str(int(float(price_usdc) * 10**USDC_DECIMALS))


def public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")


def resolve_asset(wrapper: dict) -> str:
    """x402 v2 wants the token contract address in `asset`, not the symbol."""
    raw = os.environ.get("USDC_ASSET", "").strip() or wrapper.get("pricing", {}).get(
        "asset", "USDC"
    )
    if raw.startswith("0x") and len(raw) == 42:
        return raw
    if raw.upper() == "USDC":
        return usdc_contract()
    return raw


def make_402(wrapper: dict) -> dict:
    """Official x402 v2 PaymentRequired object.

    Shape per x402-specification-v2 §5.1: x402Version, error, resource (required,
    with url), accepts[] (exactly scheme/network/amount/asset/payTo/
    maxTimeoutSeconds/extra). The same object goes in the 402 JSON body and,
    base64-encoded, in the PAYMENT-REQUIRED response header.
    """
    pricing = wrapper["pricing"]
    network = network_to_caip2(
        os.environ.get("NETWORK", "").strip() or pricing.get("network", "base")
    )
    resource_url = f"{public_base_url()}/v1/{wrapper['name']}"
    return {
        "x402Version": X402_VERSION,
        "error": "payment required",
        "resource": {
            "url": resource_url,
            "description": wrapper.get("description", ""),
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": network,
                "amount": price_to_atomic(pricing["price_usdc"]),
                "asset": resolve_asset(wrapper),
                "payTo": resolve_pay_to(wrapper),
                "maxTimeoutSeconds": 300,
                "extra": {
                    "name": "USDC",
                    "decimals": USDC_DECIMALS,
                    "settlement": "direct-transfer",
                    "howToPay": (
                        "Send USDC on Base to payTo for at least amount "
                        "(atomic units), then retry the request with the "
                        "transaction hash in the X-Payment header."
                    ),
                },
            }
        ],
    }


def payment_required_headers(wrapper: dict) -> dict:
    """v2 wire format: base64 PaymentRequired JSON in the PAYMENT-REQUIRED header."""
    raw = json.dumps(make_402(wrapper), separators=(",", ":")).encode()
    import base64

    return {"PAYMENT-REQUIRED": base64.b64encode(raw).decode()}


def looks_like_payment_payload(proof: str) -> bool:
    """True if the X-Payment value looks like a base64 x402 PaymentPayload
    (EIP-3009 authorization) rather than a plain tx hash. We settle by direct
    transfer, so these get an instructive 402 instead of a silent reject."""
    if not proof or proof.startswith("0x") or proof.startswith("mock-"):
        return False
    try:
        import base64

        decoded = base64.b64decode(proof + "=" * (-len(proof) % 4)).decode(
            "utf-8", "ignore"
        )
    except Exception:
        return False
    return '"authorization"' in decoded or '"signature"' in decoded or '"payload"' in decoded


# --- replay protection: each payment proof (tx hash) is spendable exactly once ---
SPENT_FILE = RECEIPT_DIR / "spent_hashes.json"
_spent: set[str] | None = None


def _load_spent() -> set[str]:
    global _spent
    if _spent is None:
        _spent = set()
        try:
            if SPENT_FILE.exists():
                _spent = set(json.loads(SPENT_FILE.read_text()))
        except Exception:
            _spent = set()
    return _spent


def is_spent(proof: str) -> bool:
    return proof in _load_spent()


def mark_spent(proof: str) -> None:
    spent = _load_spent()
    if proof in spent:
        return
    spent.add(proof)
    try:
        RECEIPT_DIR.mkdir(exist_ok=True)
        SPENT_FILE.write_text(json.dumps(sorted(spent)))
    except Exception:
        pass


def verify_payment(proof: str | None, wrapper: dict) -> bool:
    """Mock mode (default): accepts any non-empty proof starting with 'mock-'.

    Live mode (MOCK_PAYMENTS=false + real PAY_TO_ADDRESS): the proof must be a
    Base mainnet tx hash containing a USDC transfer to our address of at least
    the wrapper price. Verified read-only via public RPC; no private keys.

    Either way, a proof is spendable exactly once (replay protection).
    """
    if not proof or is_spent(proof):
        return False
    if mock_payments_enabled():
        ok = proof.startswith("mock-")
    else:
        from verify_onchain import verify_tx_hash  # lazy: verify_onchain imports core

        ok, _reason = verify_tx_hash(
            proof,
            int(price_to_atomic(wrapper["pricing"]["price_usdc"])),
            resolve_pay_to(wrapper),
            usdc_contract(),
        )
    if ok:
        mark_spent(proof)
    return ok


def fingerprint(proof: str) -> str:
    return hashlib.sha256(proof.encode()).hexdigest()[:16]


# --- simple in-memory per-minute rate limiting ---
_hits: dict[str, list[float]] = {}


def check_rate_limit(wrapper: dict) -> bool:
    """True if allowed, False if over the limit."""
    limit = int(wrapper.get("limits", {}).get("max_per_minute", 60))
    now = time.time()
    window = [t for t in _hits.get(wrapper["name"], []) if now - t < 60]
    if len(window) >= limit:
        _hits[wrapper["name"]] = window
        return False
    window.append(now)
    _hits[wrapper["name"]] = window
    return True


def forward(wrapper: dict, params: dict) -> tuple[int, dict]:
    """Forward to upstream. Returns (status_code, json_body)."""
    upstream = wrapper["upstream"]
    allowed = upstream.get("passthrough_params") or []
    query = {k: v for k, v in params.items() if (not allowed or k in allowed)}
    url = upstream["base_url"].rstrip("/") + upstream["path"]
    started = time.time()
    try:
        with httpx.Client(**http_client_kwargs()) as client:
            resp = client.request(
                upstream.get("method", "GET"), url, params=query,
                headers={"User-Agent": "x402-wrapper-v1"},
            )
        latency_ms = int((time.time() - started) * 1000)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:2000]}
        return resp.status_code, body
    except Exception as exc:  # noqa: BLE001 - surface as 502
        latency_ms = int((time.time() - started) * 1000)
        return 502, {"error": "upstream unreachable", "detail": str(exc)[:200]}


def log_receipt(wrapper: dict, proof: str, upstream_status: int, latency_ms: int) -> dict:
    RECEIPT_DIR.mkdir(exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    receipt = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "wrapper": wrapper["name"],
        "price_usdc": wrapper["pricing"]["price_usdc"],
        "network": os.environ.get("NETWORK", "").strip()
        or wrapper["pricing"].get("network", "base"),
        "asset": wrapper["pricing"].get("asset", "USDC"),
        "pay_to": resolve_pay_to(wrapper),
        "payment_proof_fp": fingerprint(proof),
        "upstream_status": upstream_status,
        "latency_ms": latency_ms,
        "mock_settlement": mock_payments_enabled(),
    }
    with open(RECEIPT_DIR / f"{day}.jsonl", "a") as f:
        f.write(json.dumps(receipt) + "\n")
    return receipt


def catalog() -> list[dict]:
    return [
        {
            "name": w["name"],
            "description": w.get("description", ""),
            "endpoint": f"{public_base_url()}/v1/{w['name']}",
            "method": w["upstream"].get("method", "GET"),
            "params": w["upstream"].get("passthrough_params", []),
            "price_usdc": w["pricing"]["price_usdc"],
            "network": os.environ.get("NETWORK", "").strip()
            or w["pricing"].get("network", "base"),
            "asset": w["pricing"].get("asset", "USDC"),
            "pay_to": resolve_pay_to(w),
        }
        for w in load_configs().values()
    ]
