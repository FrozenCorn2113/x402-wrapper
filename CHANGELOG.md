# CHANGELOG — x402-wrapper

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
