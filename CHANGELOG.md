# CHANGELOG — x402-wrapper

## 2026-09-21 (late night) — 402index verified + near-free prices live in production
- 402index.io domain claim VERIFIED for x402-wrapper.onrender.com
  ("Domain Verified" badge on all 3 listings). Listing names: x402wrapper,
  category "data". URLs: /service/39775003-c55a-4e16-ab05-e45e2e8c6107
  (weather-now), /service/6b9c01df-ad4a-4c59-9c2f-600fe3062a67
  (crypto-price), /service/0505e293-a404-43bb-a9e4-b087f91819ea (echo).
  Verification token stored in hidden_files/accounts/402index.json (600).
- Near-free prices confirmed LIVE in production 402 challenges (x402 v2,
  eip155:8453): weather-now 500, crypto-price 1000, echo 100 atomic USDC.
- `GET /.well-known/402index-verify.txt` live, serving the claim hash.
- Render deploy succeeded (commit 496a53a, "Near-free pricing + 402index
  domain verification route", 5 commits, manual dashboard deploy).
- Known cosmetic: extra blank lines introduced by web editor; llms.txt text
  on the deployed build still shows old prices (fixed locally with the
  circuit-breaker batch, deploys next).

## 2026-09-21 (late night) — inline loop-protection circuit breaker (v2 lane 1)
- New `circuit_breaker.py`: sliding-window loop detection in the request
  path, BEFORE payment verification. 25+ identical calls (method+path+
  canonical params+body hash) from one client within 60s trips a 5-minute
  cooldown for that request shape -> HTTP 429 with standardized
  `AGENT_LOOP_DETECTED` payload + `Retry-After` header. Blocked calls are
  never charged and never forwarded upstream.
- Identity = first X-Forwarded-For hop or peer IP (payment proofs excluded
  by design: replay protection forces proof rotation, IP stays stable).
- Per-identity rate cap: >120 calls/min -> 429 `AGENT_RATE_LIMITED`.
- Tunable via env: LOOP_WINDOW_SECONDS, LOOP_IDENTICAL_THRESHOLD,
  LOOP_COOLDOWN_SECONDS, LOOP_RATE_LIMIT_PER_MIN, LOOP_PROTECTION=off.
- `GET /v1` catalog now exposes `loop_protection` config; `llms.txt`
  documents the free insurance hook for agent builders.
- Marketing angle: "financial insurance for autonomous loops" — the
  differentiator for the 2am indie agent buyer.

## 2026-09-21 (late night) — near-free pricing + 402index verification
- 10x price cut per Brett's near-free sales directive: weather-now $0.005 ->
  $0.0005, crypto-price $0.01 -> $0.001, echo $0.001 -> $0.0001 per call
  (atomic: 500 / 1000 / 100 USDC units).
- New route `GET /.well-known/402index-verify.txt` serving the 402index
  domain-verification hash from the `INDEX_402_VERIFICATION_HASH` env var
  (404 "unverified" when unset). Enables 402index.io claim/verify flow.
- Local workspace is the source of truth; GitHub repo + Render deploy are
  updated via web flows (Render auto-deploy unreliable — manual deploys).

## 2026-09-21 (night) — official x402 v2 envelope + replay protection
- 402 challenge now follows the official x402 v2 spec (§5.1): `x402Version: 2`,
  top-level `resource` (url/description/mimeType), `accepts[]` with exactly
  scheme/network/amount/asset/payTo/maxTimeoutSeconds/extra, CAIP-2 network
  (`eip155:8453`), USDC contract address as `asset`, amount in atomic units.
- v2 wire format: PaymentRequired JSON in the 402 body AND base64-encoded in
  the `PAYMENT-REQUIRED` response header.
- Payment header is now `X-Payment` (also accepts `Payment-Signature`);
  legacy `X-Payment-Proof` still accepted. Base64 x402 PaymentPayloads
  (EIP-3009 authorizations) get an instructive 402 explaining direct-transfer
  settlement instead of a silent reject.
- Replay protection: each payment proof (tx hash) is spendable exactly once,
  persisted in `receipts/spent_hashes.json`.
- Motivation: x402scan probe rejected our custom envelope ("[405] No valid
  x402 response found"); this adapter is also the prerequisite for CDP
  Bazaar/agentic.market indexing.
- Test suite: 25/25 passing. Awaiting GitHub deploy (blocked on Brett's login).


## 2026-09-21 (evening)
- Added `GET /.well-known/x402`: unprotected discovery manifest (x402Version, endpoints, pricing, payTo) for x402 directories such as x402scan.
- Added `GET /llms.txt`: plain-language service description for agent/LLM discovery.
- Test suite: 17/17 passing (was 13/13).
- Deploy: live on Render free tier at https://x402-wrapper.onrender.com (mode=live, real Base USDC verification). GitHub: https://github.com/FrozenCorn2113/x402-wrapper (public).
