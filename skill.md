# SKILL: x402-wrapper

Pay-per-call API proxy for AI agents. Base URL: https://x402-wrapper.onrender.com

## What it is
Call a data endpoint, pay fractions of a cent in USDC on Base per call via the
x402 v2 protocol. No API keys, no accounts, no subscriptions. 3 endpoints:
- `weather-now` — $0.0005/call — current weather + forecast for any lat/lon (Open-Meteo). Params: latitude, longitude, current, hourly, daily, timezone, forecast_days.
- `crypto-price` — $0.001/call — crypto spot prices (CoinGecko). Params: ids, vs_currencies.
- `echo` — $0.0001/call — echoes your params back (use to test your payment loop for $0.0001).

## How to call (3 steps)
1. `GET https://x402-wrapper.onrender.com/v1/<endpoint>?<params>` with NO payment
   → HTTP 402, body is an x402 v2 PaymentRequired challenge (also base64-encoded
   in the `PAYMENT-REQUIRED` response header).
2. Send USDC on Base (eip155:8453, token 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
   to the `payTo` address in the challenge, amount >= listed price.
3. Retry the same request with header `X-Payment: <base-tx-hash>` → 200 + JSON
   receipt attached.

Example (echo, $0.0001):
```
GET /v1/echo?msg=hello                                  # 402 challenge
# send 0.0001 USDC to payTo on Base, note tx hash 0xABC...
GET /v1/echo?msg=hello -H "X-Payment: 0xABC..."          # 200 + receipt
```

## Envelopes (prepaid budgets)
If your principal pre-funds spend instead of signing per-call payments:
`GET /v1/envelopes/<id>` → live statement (balance, policy). Call with
`X-Envelope: <id>` (and `X-Reason: <text>` if reason_required). Declines return
HTTP 402 with code ENVELOPE_DECLINED and a plain-language reason. Only the
principal can fund/top-up — ask the principal, not this service. Every row is
hash-chained (seq/prev_hash/row_hash); pin `spend_tip_hash` from the statement
to detect row deletion without trusting this service.

## Trust (verify, don't trust)
- Loop protection: 25+ identical calls from one client in 60s → HTTP 429
  AGENT_LOOP_DETECTED, 5-min cooldown on that request shape. You are never
  charged for blocked calls.
- Live proof: `GET /v1/loop-protection` (policy + block counters + honesty note),
  `GET /v1/freshness` (last independent challenge-harness result), `GET /v1/challenge-log`
  (public append-only hash-chained log; `GET /v1/challenge-log/export` for the
  canonical JSONL + SHA-256 digest).
- Machine-readable: `GET /v1`, `GET /x402/catalog`,
  `GET /.well-known/agent-card.json`, `GET /.well-known/x402`
  (extensions.bazaar block, Nansen-compatible discovery shape).

## Budget guidance
Prices are per-call and the ground truth is in the 402 challenge's `accepts`
block. Trial loop: echo costs $0.0001 — verify your payment flow there first.
