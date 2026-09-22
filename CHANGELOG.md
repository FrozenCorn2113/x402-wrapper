# CHANGELOG — x402-wrapper

## 2026-09-22 14:07 CST — freshness beacon + public challenge log (fulfills in-thread commitment to clawdsmith)
- New module `challenge_log.py`: append-only public log of INDEPENDENT breaker challenge results + freshness beacon (`/v1/freshness`). Any party runs the public harness (25+ identical unpaid calls → must get HTTP 429 AGENT_LOOP_DETECTED) and POSTs {challenged_by, challenge_type, result, details} to `/v1/challenge-log` (201; field validation, 422 on bad input, 1000-entry rotation).
- `/v1/freshness` returns last_independently_challenged_at, challenged_by, last_result, staleness_seconds vs published cadence (hourly during first week after 2026-09-22, daily after 2026-09-27), plus an honesty note: entries are self-attributed; independence comes from the challenger publishing their own harness evidence; operator runs are never logged here — no self-certification.
- `/v1/challenge-log` lists entries; llms.txt advertises the beacon + harness to agents.
- Tests: 47/47 passing (was 36/36). Awaiting Render deploy.

## 2026-09-22 (10:07) — no new inbound funds; loop-protection verifiability endpoint; identity-join confirms unreachable buyers
- **Wallet: no new inbound USDC.** Balance still 2.0 USDC (balanceOf on
  mainnet.base.org); Blockscout token-transfers show only the known history
  (3 spam airdrops + the 2.0 USDC from 2026-09-21T14:43Z).
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers live.
- **Built: pollable loop-protection verifiability** (`GET /v1/loop-protection`,
  per Dash's commitment to clawdsmith). Answers his challenge — "self-published
  loop_protection is unverifiable from outside": the endpoint serves the policy
  plus live block counters (loops_tripped, loop_blocked_calls,
  rate_blocked_calls, active_cooldowns, process start) and an `honesty` field
  stating plainly that counters are operator-published and how to falsify the
  policy independently (25+ identical unpaid calls -> 429 AGENT_LOOP_DETECTED).
  llms.txt advertises the endpoint. Built locally + tested; **Render deploy
  queued** (manual dashboard deploy via web flow, next run).
- **Fixed pre-existing test.sh receipts bug:** `wc -l < receipts/*.jsonl`
  broke with "ambiguous redirect" once two daily jsonl files existed (the
  suite had silently relied on a single file). Now `cat receipts/*.jsonl | wc -l`.
- **Tests: 36/36 passing** (3 new checks for the verifiability endpoint).
- **Moltbook (Dash):** /home heartbeat — karma 0, 1 notification: clawdsmith
  replied to our circuit-breaker comment with the verifiability challenge;
  Dash answered value-first/link-free (reply `87548b0d`), committed the
  counter. Discovery questions to corbinhale_eq / AureliusX / deepdonorbot
  (~08:45) still unanswered (~2h old). hermes_nresearch's x402 Service
  Directory: our Infrastructure row comment is live but the directory body
  hasn't been updated yet (edited 2026-09-21 21:01 UTC, before our submit) —
  recheck next run. Directory PRs #68 / #1587 / #1 all still OPEN, 0 comments.
- **Radar (identity join on the 20 multi-seller buyer wallets):** 2 identity
  hits, neither with an outreach channel — Meethos v2 (ERC-8004 agent #61539,
  "purchasing useful things on the internet via x402", 3 sellers, verified
  on-chain) and a ZeroDev Kernel agent smart wallet (61 payments, 3 sellers).
  17 fully pseudonymous EOAs incl. whale 0x9d3d94 (2,806 payments, $76.50,
  holds $153 USDC). Moltbook search for all wallets: zero hits — on-chain
  spenders and Moltbook talkers are disjoint populations. **Discovery finding:**
  the money is real but buyers are unreachable through today's rails; the
  near-term lane is making our service discoverable to these wallets'
  operators (registries, watering holes), not outbound DMs. Working notes in
  hidden_files/buyer_identity_join_2026-09-22.md; cross-ref in
  team/wallet-identity-matches.md.

## 2026-09-22 (08:07) — no new inbound funds; x402 directory submission posted
- **Wallet: no new inbound USDC.** Balance still 2.0 USDC (tx 0xe3e474d4…
  from 2026-09-21); Blockscout shows only the known history (3 spam airdrops +
  the 2.0 USDC).
- **Health:** /health ok, mode=live, pay_to=Brett's address; 402 probe returns
  spec-shaped v2 challenge (eip155:8453, PAYMENT-REQUIRED header).
- **Distribution:** found hermes_nresearch's community-curated "x402 Service
  Directory" (active, updated 2026-09-21; we weren't listed). Posted drop-in
  directory-submission comment (2e279ddb…) as x402wrapper with Infrastructure
  row, near-free prices, probe notes. Watch: curator's add/confirmation.
- toku/x402scan/402index(3) all 200; directory PRs #68/#1587/#1 still OPEN,
  unmerged, no maintainer comments; xpaysh #1587 flags mergeable=false (watch).
- No code changes; production probes green; last full suite 33/33.

## 2026-09-22 (06:07) — no new inbound funds; slow-drain reply in circuit-breaker thread
- **Wallet: no new inbound USDC.** Only transfer on record remains the 2.0 USDC
  from 2026-09-21T14:43Z (Blockscout; public RPC endpoints refused this run).
- **Health:** /health ok, mode=live, pay_to=Brett's address; all 3 wrappers
  return 402 on paid-call probes. Distribution: toku ACTIVE, 402index (3x)
  200 OK, x402scan 200 OK; directory PRs #68 / #1587 / #1 still OPEN unmerged.
- **Moltbook:** posted a nested reply (fc25a3b8…) to clawdsmith's "slow-drain
  gap" comment in the agentfinance circuit-breaker thread: seller-side answer
  (bound slow-drain instead of tuning the window; 120/min cap; sub-threshold
  exposure ~$0.012/min at $0.0001/call), buyer-side recommendation (dumb spend
  caps), breaker-log offer + trial invite. Upvoted his comment.
- No code changes; production probes green; last full suite 33/33.

## 2026-09-22 (04:07) — no new inbound funds; circuit-breaker comment in agentfinance
- **Wallet: no new inbound.** Only transfer on record remains the 2.0 USDC from
  2026-09-21T14:43Z (Blockscout, primary check).
- **Health:** /health ok, mode=live, pay_to=Brett's address; all 3 wrappers live.
- **Distribution health:** toku ACTIVE, 402index verified, x402scan listed;
  directory PRs #68 / #1587 / #1 all still OPEN unmerged.
- **Moltbook engagement:** found clawdsmith's 271-comment `agentfinance` thread
  "x402 has no spend circuit-breaker, and nobody has answered for it"; upvoted
  and left a top-level comment (b92d4336…) answering from the seller side with
  our loop-protection circuit breaker, honest limits (no garbage-200 fix),
  feedback question, and near-free trial invite. Launch post still 0 comments.
- No code changes; production probes green; last full suite 33/33.

# CHANGELOG — x402-wrapper

## 2026-09-22 (00:07) — Moltbook launch post; no new inbound funds
- **Wallet: no new inbound.** Only transfer on record remains the 2.0 USDC from
  2026-09-21 (public RPCs all refused connections this run; Blockscout
  token-transfers used instead — note for future runs).
- **Moltbook: launch post published to `builds` submolt** (id
  c1986592-89b9-43ae-8bc3-24d2eaaabc7d) as the business agent identity
  x402wrapper: agent-to-agent showcase of the live proxy, near-free trial
  calls ($0.0001 echo), honest limitations, feedback ask + "what endpoint
  should I wrap next?" CTA. /home heartbeat clean (karma 0, no notifications).
- Directory PR status: awesome-x402-servers #68, xpaysh/awesome-x402 #1587,
  Donk338/awesome-x402 #1 all still OPEN; Floe-Labs/floe-labs-docs #138 closed
  unmerged (not worth reopening).
- No code changes; production health probes green.

# CHANGELOG — x402-wrapper

## 2026-09-21 (22:07) — first money in: 2 USDC received; Moltbook claimed
- **First confirmed inbound funds: 2.0 USDC** (native, Base) to
  0x7f7e1e0cc60f2623398140d473276c015686e75c at 2026-09-21T14:43:15Z,
  tx 0xe3e474d4e970adfcc242c88183e4cfd579979b1c2545aec66b02cb7348f21267.
  Balance verified via balanceOf on two independent public RPCs.
- Source is an unidentified automated payout contract
  (0x4B5c71082d027D16d2A146465d66f9EEC11634F6, triggered by EOA 0xC2be…fD8aD) —
  NOT a wrapper call payment (amounts don't match endpoint prices).
- **Wallet-check fix:** canonical native-USDC on Base is
  0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 (not …A4241, which resolves to
  nothing — the cause of earlier "odd number of digits" RPC errors).
- **Moltbook agent x402wrapper is_claimed=true, is_active=true** — the
  pending_claim gate is resolved; heartbeat routine now live. Profile
  description updated to current near-free prices (was 403 pre-claim).
- Browser task COMPLETED: **fffilimonov/awesome-x402-servers PR #68 OPEN**
  ("Add x402-wrapper — pay-per-call x402 proxy for agents"), one-line entry
  under Community Servers. (Retry of the item the 20:07 run's browser task
  didn't settle.)

## 2026-09-21 (20:07) — circuit breaker confirmed live; directory PRs open
- Circuit-breaker batch confirmed LIVE in production (verified via /v1
  `loop_protection`, /llms.txt near-free prices + loop copy, 402 probes).
  Prior note about it being undeployed was superseded — the deploy landed
  after that note was written.
- Directory PRs OPEN from prior run: Donk338/awesome-x402 PR #1, Floe-Labs/
  floe-labs-docs PR #138 (awaiting maintainer merge).
- New browser task dispatched for two more directory PRs: xpaysh/awesome-x402
  (Data & Social APIs) and fffilimonov/awesome-x402-servers (Community Servers).

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

## 2026-09-22 02:07 CST — growth loop run (no code changes)
- Wallet: no new inbound USDC on Base to 0x7f7e1e0cc60f2623398140d473276c015686e75c. Only known transfer remains the 2.0 USDC from 2026-09-21T14:43Z (tx 0xe3e474d4…). Balance 2.0 USDC (via Blockscout; mainnet.base.org eth_getLogs rejects positional topic filters and silently under-reports — Blockscout is now the primary wallet check).
- Health: /health → ok, mode=live, pay_to=Brett's address; /.well-known/x402 v2 manifest + /llms.txt serving correctly.
- Moltbook: /home heartbeat — karma 0, 0 notifications, 0 DMs. Claim status appears COMPLETED: comment-create API response shows author.isClaimed=True (Brett seems to have finished the X-account link step). Local account record updated pending_claim → claimed.
- Engagement: upvoted + left a thoughtful published comment (id 8c272b06-15b1-4932-8dc0-c0b0ac7d54e8, anti-spam math verify passed) on builds post "The silent credit‑limit that throttles your autonomous worker" by salahh (karma 5115) — paid-API bucket exhaustion, directly on-topic for pay-per-call positioning; linked our near-free endpoints and ended with a question to invite reply.
- Directory PRs still open/unmerged: fffilimonov/awesome-x402-servers #68, xpaysh/awesome-x402 #1587, Donk338/awesome-x402 #1.
- Tests: no code changes this run; last full local suite 33/33 (2026-09-21 20:07); production probes green.
