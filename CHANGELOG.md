# CHANGELOG — x402-wrapper

## 2026-09-24 (04:55) — Growth loop: Strale 402 parity (price-sentence error, Link agent-card header, CORS expose)
- **Wallet: no new inbound.** Balance 2.0 USDC unchanged (balanceOf 0x1e8480); legacy Blockscout tokentx endpoint confirms only inbound ever is the 2.0 USDC from 2026-09-21. Health: /health 200, mode=live, pay_to=Brett's address, 3 wrappers.
- **Strale 402-shape parity (discovery finding → code):** Strale (api.strale.io — the named vendor with two independent agent buyers, $0.02–$0.54/call) fetched live; their 402 pattern: (1) `error` carries a plain-English price sentence ("Payment required. IBAN Validation costs $0.0540 USDC per call."), (2) `Link: </.well-known/agent-card.json>; rel="agent-card"` response header (in-band discovery), (3) CORS `access-control-expose-headers: Payment-Required,X-Payment-Response`. Our 402 now does all three (additive). Also confirmed: Strale sends NO challenge header at all (challenge lives in body only) — our body + dual-header-mirror is a superset, no change needed. And Strale sends `extra.name="USD Coin"` — the ecosystem norm, confirming the PayAPI extra.name risk was a misread.
- **Tests:** local suite 130/130 (3 new checks: 402 error price sentence, 402 Link agent-card header, 402 CORS expose-headers). Commit c501ff6 pushed to main.
- **Deploy:** dashboard deploy of c501ff6 dispatched this run (fresh browser task per standing lesson); verification pending.
- Run notes: hidden_files/growth-2026-09-24-0455.md.

## 2026-09-24 (04:25) — Growth loop: discovery gaps closed — /skill.md + agent-card aliases + BlockRun 402-shape parity
- **Wallet: no new inbound.** 2.0 USDC unchanged (balanceOf + Blockscout filter=to both agree); latest inbound remains BSTONK spam dust (2026-09-23T01:16:35Z). Health: /health 200, mode=live, pay_to=Brett's address, 3 wrappers.
- **Discovery surface (why):** synthesis §6q–§6r — buyer agents probe whoever is *discoverable*; Strale's template is agent-card.json + /x402/catalog + agent skill files. Remaining gaps closed this run: (1) `/skill.md` — new terse machine-readable agent skill (payment flow, envelope usage, trust verification, budget guidance); served live at /skill.md. (2) Agent-card aliases — the card is now served at three conventional paths: `/.well-known/agent-card.json`, `/agent-card.json` (Strale-style root), `/.well-known/agent.json` (A2A convention). (3) llms.txt advertises skill.md; agent-card `discovery` block gains `skill_md`. All additive, no behavior changes.
- **BlockRun 402-shape parity (discovery finding → code):** BlockRun's own docs (awesome-blockrun how-it-works.md) show their 402 body repeats `price.amount` in USD at top level "for clients that only read the body", and they ship the challenge under both `PAYMENT-REQUIRED` and `X-Payment-Required` headers. Our 402 now does both (additive). Also fixed a stale core.py comment claiming PayAPI "requires" extra.name="USD Coin" — Ink's 03:55 verification showed Nansen sends the identical value; PayAPI's "USDC" expectation was a misread.
- **Ticket→price mapping (§6t):** BlockRun's published ladder ($0.002/req cheapest data, +$0.001 flat fee, 5% media margin, $0.003 video minimum, $0.012 virtual-portrait, ~$0.1575 music, ~$0.84 Sora-2) explains the observed ladder shapes — the evaluator ritual is buyers *walking the vendor's real price list*. Transparent per-call pricing is what draws repeat spend.
- **Tests:** local suite 127/127 (10 new checks this run: llms.txt skill.md ad, skill.md content, root + A2A agent-card aliases, 402 top-level price, X-Payment-Required mirror, header-value identity, decoded-challenge price). Run notes: hidden_files/growth-2026-09-24-0425.md.
- **Deploy saga — RESOLVED, all live:** deploy of 7a9f389 succeeded but /skill.md returned "skill.md not installed" — two-layered cause: (1) Dockerfile COPY list omitted skill.md (fixed 81916e3); (2) `.dockerignore` excludes `*.md` from the build context, silently dropping skill.md even with the COPY line (fixed 1b1ef7b with `!skill.md` exception). A steered redeploy task failed at hand-off; fresh deploy task for 1b1ef7b cut over. **Verified live via direct curl: /skill.md serves content ✅, 402 carries BOTH payment-required + x-payment-required headers ✅, 402 body carries top-level price ✅.**

## 2026-09-24 (03:55) — Growth loop: Nansen bazaar-shape manifest rework + new evaluator wallet 0xb9fCbaa0
- **Wallet: no new inbound.** 2.0 USDC unchanged; latest inbound remains BSTONK spam dust (2026-09-23T01:16:35Z). Health: /health 200, mode=live, pay_to=Brett's address, 3 wrappers.
- **Ink (discovery copy, Nansen mirror):** `/.well-known/x402` now carries a Nansen-style `extensions.bazaar` block (per-endpoint info + JSON Schema 2020-12 contract) — buyers price-ladder Nansen's catalog off this exact shape. Also: network now `"eip155:8453"` (was `"base"`), asset now the USDC contract address + `"assetName": "USDC"`, description corrected to "fractions of a cent" (was "a few cents" — mis-stated our $0.0001–$0.001 prices), llms.txt gains a "Discovery shape" section. Kept `extra.name = "USD Coin"` — verified live against Nansen's 402 (same value); the PayAPI "USDC" expectation is a misread, not our defect. Kept header copy "(PAYMENT-REQUIRED header)" — that is the actual key the code sends (headers are case-insensitive, so both forms work). Draft: hidden_files/copy-drafts/discovery-rework-2026-09-24-0355.md.
- **Radar (buyer-watch):** whale 0x9d3d quiet ~49 min, Strale ladder still paused; 0x30a6 burst #3 ended 19:19Z; Nansen 0 in-window (0x0Ab1 $0.01 cadence may have stopped); fd64 metronome holding ~$0.024. **NEW: fresh evaluator wallet 0xb9fCbaa0…FC19DF3f — 48× laddered tickets ($0.035→$0.23, $4.42) to e903 in 13 min + $0.566 to new vendor 0x4c860fd1 — strongest new agent-spend signal of the day.** Meethos ~6.9d dormant. Sweep: buyer-watch-2026-09-24-0355.md; discovery synthesis §6s.
- **Deploy:** push to main (this run); Render auto-deploy unreliable — dashboard deploy needed.
- **Tests:** local suite 117/117 (5 new checks: bazaar block, CAIP-2 network/asset contract, price-copy truthfulness, bazaar structure, llms.txt discovery-shape section). Run notes: hidden_files/growth-2026-09-24-0355.md.

## 2026-09-24 (02:55) — Growth loop: PayAPI bounce concern resolved (pending canary), 0x9305 = most buyer-diverse vendor, metronome tickets 3×'d
- **Wallet: no new inbound.** Balance 2.0 USDC; only real inbound remains 2.0 USDC from 2026-09-21; newer transfers all spam dust.
- **Health:** /health 200, mode=live, pay_to=Brett's address, 3 wrappers.
- **PayAPI listing — NOT bounced.** Gmail check (this run): ack email 2026-09-23 02:27 CST "The form accepted x402-wrapper. That is not live."; next step is THEIR canary (operator pays one call from their wallet). No verdict email as of 03:00 CST; no canary landed. ~25h in review/canary queue — wait, do NOT re-submit. Live 402 already sends extra.name "USD Coin" (standing bounce candidate resolved). directory-submission-payapi.md corrected.
- **Radar (buyer-watch):** whale 0x9d3d QUIET this window — no ladder beyond $0.108 → Strale; Strale stuck at 2 buyers; no return to the 12 probes. **0x9305 is the demand hotspot:** 3 independent repeat buyers now (0xaca237 50 × $0.05, 0x0Ab1C750 48 × $0.01 since Sep 21, burst buyer 0xbF757f5d 8 × $0.01 this window) + 728D probed it — most buyer-diverse vendor on the watch list; "what does 0x9305 sell?" trace queued. **Metronome 0xfd64 tickets 3×'d to $0.0199–$0.0251** (was $0.0082) — e903 repriced mid-day, kept the client: pricing-power data point. 0x30a6 burst died again (reads like human/cron session, not evaluator; NO Strale touch ever — downgraded). 0x07fBca/0xaca237 no reactivation; 0x67b3 quiet ~9h; 0x79015C7b no repeat yet. Meethos ~6.6d dormant. Sweep: buyer-watch-2026-09-24-0255.md.
- **Dash (Moltbook):** claim intact, karma 9, no DMs. clawdsmith phantoms NOT recovered (12 missing, 273 vs 261); zero comments posted. nanoswarm rails question unanswered; jarviscooper silent. xpaysh#1587 still OPEN (rebase needs Brett's GitHub OK, standing). Heartbeat: dash-heartbeat-2026-09-24-0255.md.
- No code changes; last full local suite 112/112 (2026-09-23 18:25). Run notes: hidden_files/growth-2026-09-24-0255.md.

## 2026-09-24 (00:25) — Growth loop: no new inbound funds; Radar sweep + Dash heartbeat; toku prices resolved, PayAPI pending
- **Wallet: no new inbound.** Only real USDC transfer ever is 2.0 USDC from 2026-09-21T14:43:15Z; since then only spam dust (latest BSTONK 2026-09-23T01:16Z). Balance 2.0 USDC.
- **Prod parity confirmed:** /health live (mode=live, pay_to=Brett's address), /.well-known/agent-card.json and /x402/catalog both 200 with correct payload; local git 778329d synced with main. The 18:25 deploy blocker is resolved — Brett's 2026-09-23 git-credential-helper fix in place at ~/.git-credentials-x402 (600-perm); plain git+HTTPS is the working push path (gh CLI still unauthenticated).
- **Radar (buyer-watch):** whale 0x9d3d94… biggest window yet — 163 payments, $3.20; ritual explicit: fixed-$0.01 first-contact probes across discoverable vendors then price-ladder the responders (12 new probes 13:24–13:42Z: 0x0b2dAb84, 0xbc66B65E, 0xB52f5B05, 0x5AA6f07c, 0x19311476, 0xaEC99140, 0x8c192e64, 0xA884D7Fd, 0xdAbAF1F3, 0x53065d33, 0xF57d17ca, 0x739fF099 — identity hunt queued). Strale ladder escalated to $0.324 (new Strale-window high). 0x30a6… second mega-burst: 341 payments, $3.12, $0.562×3 new high, A/B alternation e903↔0x260E, still NO Strale touch (Strale stays 2-buyer). 0x67b3 quiet after 11:09Z (identity still unknown); 0xfd64 metronome unbroken; 0x4417 dust expanded; new one-off payers 0x728D → 4df6, 0xc93a → nano; Meethos ~6.8d silent. Sweep notes: buyer-watch-2026-09-24-0025.md; discovery synthesis §6q.
- **Dash (Moltbook):** claim intact (is_claimed True, active, karma 9, no DMs). clawdsmith-thread moderation worsening — second phantom notification (16:15:06Z), both phantom IDs 404, public tree down to ~104/273 comments. ZERO comments posted (replying blind to invisible comments off-limits). nanoswarm: no rails answer; jarviscooper silent — $5 envelope offer + cross-rail seam question both open.
- **toku.agency stale-price concern RESOLVED** — all three services now show correct live prices ($0.0001/$0.001/$0.0005). **PayAPI listing STILL NOT LIVE** (191 verified / 207 incl. unverified searched, zero hits; window closes ~2026-09-24 02:07Z).
- No code changes; tests last ran 112/112 (2026-09-23 18:25). Run notes: hidden_files/growth-2026-09-24-0025.md.

## 2026-09-23 (18:25) — Strale-surface mirror: agent-card.json + /x402/catalog (deployed 19:06 CST, verified live 200s)
- **Discovery surface:** §6o finding — real buyers (whale → Strale) price-ladder off agent-card.json + /x402/catalog. Added both: `GET /.well-known/agent-card.json` (name, provider, capabilities+prices, payment rails eip155:8453/USDC, payTo, envelope support, trust endpoints, discovery links) and `GET /x402/catalog` (thin catalog alias). llms.txt discovery section now advertises both.
- **Tests:** local suite 112/112 (5 new checks for agent-card + x402/catalog). No behavior changes to paid flow.
- **Deploy:** pushed to main 2026-09-23 ~19:10 CST; Render deploy via dashboard (auto-deploy was disabled by specific-commit deploy, re-enable pending).
- **Wallet:** no new inbound. Balance 2.0 USDC; only real USDC transfer ever is the 2026-09-21 2.0 USDC. Health: /health ok, mode=live, pay_to=Brett's address, 3 wrappers.

## 2026-09-23 (17:25) — toku price sync + nanoswarm admissions + whale 4-vendor circuit; no new inbound funds
- **Wallet: no new inbound.** Only USDC transfer remains 2.0 USDC from 2026-09-21. PayAPI review-canary not landed; listing not live (window closes ~09-24 02:07Z).
- **Health:** /health ok, mode=live, pay_to=Brett's address, 3 wrappers. Production parity verified for today's builds: envelope_support:true, /v1/challenge-log/export live (empty chain by design), export advertised.
- **toku.agency listing synced:** no PATCH/PUT endpoint exists (405), so deleted all 3 stale services and re-created them with correct copy — $0.0005/$0.001/$0.0001 USDC per call, X-Payment header (x402 v2) mechanics, llms.txt + /.well-known/x402 links, placeholder note on the Toku USD price field. New ids: cmudwqfl50001gm0akkkamlpz, cmudwqge70001gm0a6dpxz6kf, cmudwqh6j0001gm0agt48kmly.
- **Dash (Moltbook):** karma 9, no DMs. nanoswarm replied (95ca6230) granting BOTH breakage gaps — tomb detection = filed network bug on their forge; revocation asymmetry admitted ("operator-generated keys are non-unilaterally-revocable by the funder… revocable-in-name-only") — plus a claim: self-funded buyer paid two distinct sellers in the same hour. Dash replied (387a7100, one comment): confirmed the fixes, admitted boundary (ran onramp probe himself, did NOT post an ask), asked the hinge question — WHICH RAILS did those sellers settle on? If XNO-native, the cross-rail seam (XNO-funded buyer → Base-USDC x402 seller) is unbroken. jarviscooper still silent (principal-on-his-side question unanswered). Phantom 07:36Z comment still absent. Needs Brett: nothing.
- **Radar (buyer-watch):** whale 0x9d3d94… VERY ACTIVE in a 4-vendor circuit (0x9AAC $0.05, 0x66D7 $0.0324→$0.054 escalating, 0x4df6 $0.05→$0.005 descending, e903 NEW $0.003 micro-tier at BlockRun). 0x30a6cb91's 113-transfer ~$2.29 burst ended (one-off eval, now quiet). **Meethos v2 paid 0x66D7 $0.0216 on Sep 17 — two independent buyers → 0x66D7 likely a real vendor; identity hunt worth retry.** 0x260E's $39 funder = Mayan Finance bridge (SwiftDest 0xD78D199f8C…), operator anonymous; best vendor-side lead, no on-chain contact channel. New payer 0xf92892ba: single $0.022922 at e903. 0xfd64 metronome continues. Sweep: buyer-watch-2026-09-23-1725.md.
- **Discovery synthesis:** §6n (nanoswarm admissions + rails-pending; whale circuit; 0x66D7 two-buyer read).
- No code changes; last full local suite 107/107 (16:55).

## 2026-09-23 (15:55) — Whale eval sweep on new vendors ($0.05 tickets); 0xfd64 = bot, no identity; 0x260E $39-funded vendor lead
- **Wallet: no new inbound.** Latest transfer is BSTONK spam dust 01:16Z; only real inbound remains 2.0 USDC from 2026-09-21. PayAPI review-canary not yet landed (window closes ~09-24 02:07Z).
- **Health:** /health ok, mode=live, pay_to=Brett's address, 3 wrappers.
- **Dash (Moltbook):** karma 9, no DMs. Posted nothing this run — 5 x402wrapper comments on the thread today + moderation-hold caution meant zero was the safe call; upvoted 5 substantive replies (nanoswarm ×2, jarviscooper ×3). Phantom jarviscooper reply at 07:36Z 404s (deleted/moderated) — watching whether it reappears. jarviscooper still hasn't answered the principal-on-his-side question. Needs Brett: nothing.
- **Radar (buyer-watch):** THE WHALE MOVED — 0x9d3d… paid 2× $0.03 to new vendor 0x9AAC… and 3× $0.05 to new vendor 0x4df6… (highest tickets ever on it; eval sweep, not volume). 0x30a6… did the same ($0.012394 to e903, then $0.005 to new vendor 0x260E…). Meethos (~6.6d) and 0x2b4e (~12d) silent. **0xfd64 identity: bot confirmed, operator unknown** — EIP-7702 smart account, metronomic to BlockRun e903, no ENS/labels/search hits; watch-list only. **New vendor leads:** 0x9AAC… (7702, 3 payers, $0.03–$0.05), 0x260E… (7702, **$39.008049 inbound** — actively-funded agent service, best new lead), 0x4df6… (EOA settlement, 4 payers incl. 0x4C29Ec4F, $0.01–$0.05).
- **Discovery synthesis:** §6m added — whale eval-sweep pattern (eval bursts, not baselines); EIP-7702 agent wallets proliferating with different implementations; funded vendors are the outreach priority.
- No code changes; last full local suite 102/102 (14:00).

## 2026-09-23 (15:25) — BlockRun vendor identity CLOSED; nanoswarm joins envelope thread; buyers quiet
- **Wallet: no new inbound.** 2.0 USDC balance unchanged; newer transfers all spam dust. PayAPI listing still not live (review window closes ~09-24 02:07Z).
- **Health:** /health ok, mode=live, pay_to=Brett's address; challenge chain valid, no new entries (no paid calls yet); envelope route correctly 404s unknown IDs.
- **Dash (Moltbook):** karma 8, no DMs. New participant nanoswarm replied (07:21/07:23Z) on the envelope thread: convergence + "break my wallet-free onramp" challenge. Posted one honest value-first reply (71de3fbc) naming two failure tests (unrecoverable-key tomb loss; revocation asymmetry). Caution flag: same-day comments render on /agents endpoint but not in the public thread listing — possible Moltbook moderation hold; easing cadence on that thread next run. jarviscooper still silent (principal-on-his-side question unanswered). Needs Brett: nothing.
- **Radar (buyer-watch):** ALL THREE QUIET (whale ~46 min, 0x30a6 ~75 min, Meethos ~6.5 days). $0.025 tier did not persist — eval burst, not baseline. **Vendor identity CLOSED: 0xe9030014F5… = BlockRun treasury (blockrun.ai)** — AI media APIs (Sora-2 ~$0.84/8s), x402-exact via Circle Gateway, 5 independent public sources; scam-taint caveat noted. **New buyer lead: 0xfd644825…** (contract wallet, metronomic $0.0082/15min to e903, active now). Recorded in team/wallet-identity-matches.md.
- **Discovery synthesis:** §6k (nanoswarm onramp + breakage; envelope-on-onramp composition hypothesis), §6l (BlockRun resolves $0.025 mystery; outreach consequences).
- No code changes; last full local suite 102/102 (14:00).

## 2026-09-23 (14:25) — $5 envelope offer made concrete; 0x30a6 buyer escalates to $0.025 tier; no new inbound funds
- **Wallet: no new inbound.** Only USDC transfer ever remains the 2.0 USDC from
  2026-09-21T14:43:15Z; everything since is spam dust. PayAPI review-canary not
  yet landed. NOTE: mainnet.base.org eth_call flaky this run ("odd number of
  digits" on well-formed params, dropped connections) — Blockscout ERC-20 transfer
  history is the reliable new-inbound signal; /token-balances returns a partial set.
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers.
- **Dash (Moltbook):** karma 7, 0 unread, no DMs. Posted the concrete $5 envelope
  follow-up to jarviscooper (comment 8e7f9409-9fed-463a-a66d-1a41b9cfa64e, reply to
  our 9897a9e4): live statement endpoint https://x402-wrapper.onrender.com/v1/envelopes/{id},
  his three authorizability properties, mechanics (principal tops up $5 USDC to
  payout wallet, we verify + credit manually; X-Envelope + X-Reason drawdown;
  ambiguity→no purchase), explicit acknowledgment nothing opens until a principal
  on HIS side authorizes — offer to hand upward, not spend from. He hasn't replied
  yet. Upvoted his 9118863c. PayAPI listing still NOT live (review window closes
  ~09-24 02:07Z). Needs Brett: nothing.
- **Radar (buyer-watch):** whale 0x9d3d9410 ACTIVE (13 new outbound, $0.172661
  total, all → known vendor 0xe9030014F5…, $0.011 eval batches, no rotation).
  **0x30a6cb91 ACTIVE with first order-of-magnitude ticket jump:** 50 new outbound;
  40× A/B pairs drifted $0.002→$0.003099, then 10× at a NEW ~$0.025 TIER
  ($0.025516→$0.024540 decreasing sequence to e903 + 4× flat $0.005 to second
  vendor) — largest tickets this buyer has ever sent. Meethos v2 still quiet
  (~6.5 days). Novel vendors: zero. Lane unchanged: discoverability.
- **Discovery synthesis:** §6i added — jarviscooper's identity-as-optional-input +
  three authorizability properties (full verbatim); context-change expiry is the
  remaining MVP policy gap.
- No code changes; last full local suite 102/102 (14:00).

## 2026-09-23 (14:00) — envelope MVP v1 LIVE in production
- **Deploy:** commit ab8a6bf5 ("Docker: copy envelopes.py into image") deployed to
  Render (manual deploy succeeded); GET /v1 now returns `"envelope_support": true`,
  /health ok mode=live, pay_to Brett's address.
- **Verified live:** `GET /v1/envelopes/{unknown-id}` returns proper envelope-shaped
  error `{"error":"unknown envelope id ..."}` (route live, no envelopes issued yet).
- **Unblocks:** the staged '$5 principal-funded budget' envelope offer to
  jarviscooper on Moltbook — the live statement endpoint
  (https://x402-wrapper.onrender.com/v1/envelopes/{id}) is now real and linkable.
  Operator admin API (`/v1/admin/envelopes`) gated by ADMIN_TOKEN env var (set,
  value never touched).

## 2026-09-23 (13:00) — envelope MVP v1: prepaid spend envelopes (LOCAL ONLY, not deployed)
- **What:** operator-opened prepaid credit envelopes for funded-principal
  agents, built directly from discovery quotes. jarviscooper: "I won't spend
  a principal's funds to generate a data point" (agent under a funded
  principal can't self-authorize — near-free pricing didn't fix onboarding);
  AureliusX: wants "a reversible envelope plus an explicit reason for the
  call"; deepdonorbot: blocked on funding. This makes the staged '$5
  principal-funded budget' Moltbook offer to jarviscooper real.
- **Code:** new `envelopes.py` — envelope record {id, principal_wallet,
  label, balance_atomic, per_call_cap_atomic, allowed_paths, velocity_per_min,
  reason_required, status in active/suspended/closed, timestamps}, persisted
  to `envelopes/envelopes.json` with atomic writes (tmp + rename); ids
  `env_` + 12 hex chars; per-envelope receipt lines in
  `receipts/envelope-<id>.jsonl`; process-local sliding velocity windows.
- **server.py:** admin endpoints behind ADMIN_TOKEN bearer check (all 401 on
  missing/bad token): POST /v1/admin/envelopes (open; validates amount>0,
  per_call_cap>0, allowed_paths ⊆ configured wrappers, velocity 1..120),
  POST /v1/admin/envelopes/{id}/topup (records credit AFTER manual read-only
  on-chain verification of the principal's USDC transfer to Brett's wallet —
  verification itself is manual for v1), POST .../status (suspend/close).
  Agent drawdown via X-Envelope header on the existing /v1/{name} proxy:
  policy check runs BEFORE any payment flow (status active, balance covers
  price, price ≤ per-call cap, wrapper in allowed_paths, velocity cap,
  X-Reason when reason_required → else 400 instructive); passing calls SKIP
  the 402 x402 flow and get an authorization→delivery receipt carrying
  envelope_id, reason, remaining balance. ANY ambiguity (unknown id,
  suspended/closed, cap exceeded, short balance, velocity tripped, missing/
  malformed reason) → 402 ENVELOPE_DECLINED, nothing decremented/charged/
  forwarded (jarviscooper's rule: ambiguity → no purchase). Loop protection
  stays before everything. GET /v1/envelopes/{id} → public statement
  (status, balance, policy summary, receipt lines; no admin token or other
  envelopes' data). GET /v1 now advertises envelope_support:true; llms.txt
  gained an "Envelopes (prepaid budgets)" section with an HONESTY NOTE.
- **Trust design (Brett's constraints):** we track balances but NEVER hold
  customer keys; only Brett can release payouts; no spend, no cards, no paid
  anything, no seed phrases/private keys anywhere in this code. Contract
  escrow deferred to v2 (documented, not built).
- **Deliberately deferred to v2:** principal-signed mandates (EIP-712 —
  jarviscooper's doctrine item #1 requires it, stated honestly in llms.txt as
  not built); automated on-chain top-up verification (manual for now);
  multi-process velocity accounting (process-local windows; single-process
  Render free tier is the target); ledger export/reconciliation tooling.
- **Tests:** 102/102 (was 53/53; 49 new envelope checks). LOCAL ONLY — no
  GitHub push, no Render deploy (deployment goes through the separate
  browser flow; ADMIN_TOKEN must be set as a Render env var on deploy).

## 2026-09-23 (11:55) — hash-chained challenge log DEPLOYED live (clawdsmith loop closed)
- Render manual deploy dep-dapkuhk9v7es738vr4f0 at 12:02 CST (commits 64f12e3
  + 5aa9866, supersedes f4b5eea). Independently verified: /health ok,
  /v1/freshness shows chain:{chain_valid:true}. $0 spent.
- Dash posted closing reply (e90bd58b) on the clawdsmith circuit-breaker
  thread: hash-chaining live, invite to re-run harness + log first real
  chained entry. jarviscooper silent ($5 envelope offer still staged).
- Wallet: no new inbound (2.0 USDC). PayAPI listing still in review
  (~09-24 02:07Z). Buyer-watch: whale 0x9d3d94 resumed ($0.02 eval burst to
  known vendor 0x4df66B6c…); 0x30a6cb91 and Meethos v2 quiet; no new vendors.
- Moltbook claim active, karma 7, clawdsmith now follows x402wrapper.
  PRs #1/#1587/#68 all OPEN, no movement. Value-first comment on
  neo_konsi_s2bw's replayable-approval post.
- No code changes; last local suite 53/53 (11:30).

## 2026-09-23 (11:30) — hash-chained challenge log (fulfills in-thread commitment to clawdsmith)
- Every challenge-log entry now carries prev_hash + entry_hash (SHA-256 chain);
  GET /v1/freshness exposes chain.chain_valid so anyone can verify the log
  hasn't been silently edited. Dash committed this publicly on the clawdsmith
  thread (comment 3a765167) after his honest "NOT hash-chained yet" answer.
- Local suite 53/53 (47 baseline + 6 new chain checks). Deploying via browser
  task: 3 GitHub commits (challenge_log.py, test.sh, CHANGELOG.md) + Render
  manual deploy → verify /health + /v1/freshness chain_valid:true.

## 2026-09-23 (10:56) — quiet run: buyers silent, jarviscooper thread deepens
- **Wallet: no new inbound.** Balance 2.0 USDC, unchanged; recent transfers all spam dust. PayAPI review-canary ($0.001–$0.05) not yet landed; listing still not live (expected ~09-24 02:07).
- **Health:** /health ok, mode=live, pay_to=Brett's address, 3 wrappers; /.well-known/x402 200 (extra.name="USD Coin"); challenge log empty — no paid calls, no independent challenges yet.
- **Buyer-watch (Radar):** ALL THREE QUIET — first silent window of the day. Whale 0x9d3d94 (~36 min silence, eval roster unchanged, no novel vendors); 0x30a6cb91 quiet (A/B loop paused); Meethos v2 still quiet (6 days). Signal: vendor overlap across all three buyers (0xe9030014F5… whale+0x30a6…, 0x66D7C2F9… Meethos+whale) hints at a shared marketplace backend — still bare EOAs, no outreach identity. Lane unchanged: discoverability. Note: hidden_files/buyer-watch-2026-09-23-1100.md.
- **Dash (Moltbook):** claim active, karma 4 (up from 3), 0 unread, no DMs. Substantive reply to jarviscooper's new comment on the liability-wall thread (MPP/fiat-rail question; our seat = raw x402 v2 + circuit breaker; buyer-side policy engine doesn't exist yet; trial invite + mandates feedback ask). clawdsmith thread quiet. Value-first top-level comment on lightningzero's retry/trace post (outcome-laundering framing, cost-so-far-per-attempt proposal). PRs #1/#1587/#68 all OPEN, no movement. skill.json 1.11.0 = baseline.
- No code changes; last full suite 47/47.
- **Wallet: no new inbound.** Balance 2.0 USDC, unchanged. PayAPI review-canary
  ($0.001–$0.05) not yet landed; listing expected live ~2026-09-24 02:07 (~16h left).
- **Health:** /health ok, mode=live, pay_to=Brett's address, 3 wrappers; /.well-known/x402 200.
- **Buyer-watch (Radar):** whale 0x9d3d94 ACTIVE (02:23Z), eval loop continuing
  (no novel vendors); 0x30a6cb91 ACTIVE (02:16Z) — 27 payments in rapid
  alternating bursts, tickets drifting up ($0.002→$0.002982/$0.002067/$0.002324),
  A/B-benchmark pattern. Meethos v2 still quiet. Identity hunt: none this run.
  Note: hidden_files/buyer-watch-2026-09-23-1200.md.
- **Dash (Moltbook):** claim verified (karma 3, up from 2), 0 unread, jarviscooper
  thread quiet; no engagement warranted this run. PayAPI /list (203 live APIs)
  still no x402-wrapper. PRs #1/#1587/#68 all OPEN, no maintainer movement.
- No code changes; last full suite 47/47.

## 2026-09-23 (10:00) — no new inbound funds; discovery signal: funded-principal buyer objection
- **Wallet: no new inbound.** Balance 2.0 USDC, unchanged; latest inbound token
  transfer is spam dust (BSTONK etc.). PayAPI review-canary not yet landed.
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers live.
- **402 challenge verified:** /v1/crypto-price returns extra.name="USD Coin",
  payTo=Brett's address, amount=1000, eip155:8453 — the 02:07 PayAPI fix is live.
- **Buyer-watch (Radar):** whale 0x9d3d94 ACTIVE (09:01 CST), roster ~18 vendors,
  four new $0.01 probes in a 9-min burst (0x987d489fC5…, 0xC529E55760…,
  0x5DCbdC505B…, 0x18bd22279c…) — all EOAs, no identity, no Dash candidate.
  0x30a6cb91 unchanged alternating pattern. Meethos v2 still quiet.
  Note: hidden_files/buyer-watch-2026-09-23-1000.md.
- **Dash (Moltbook):** claim verified (karma 3); handled jarviscooper's reply on
  the liability-wall thread with a substantive threaded reply (483dcf68-51f7-4642-9a8f-75f800e08513).
  Discovery signal: funded-principal agents can't self-authorize trial spend —
  "I won't spend a principal's funds to generate a data point." Barrier is
  AUTHORIZATION, not price → prepaid-envelope / principal-signed-mandate model
  needed. Folded into team/discovery-synthesis.md §6h.
- **PayAPI:** listing NOT live yet (submitted 02:07, review ~24h → expected ~09-24 02:07).
- **PR watch:** Donk338/awesome-x402 #1 OPEN; xpaysh/awesome-x402 #1587 OPEN, dirty
  (rebase needs Brett's GitHub OK); fffilimonov/awesome-x402-servers #68 OPEN, mergeable clean.
- No code changes; last full suite 47/47.

## 2026-09-23 (06:07) — whale roster explosion overnight; no new inbound funds
- **Wallet: no new inbound.** Balance 2.0 USDC, unchanged; PayAPI review-canary not yet landed.
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers live.
- **Buyer-watch (research):** whale 0x9d3d94 ACTIVE (latest 06:01 CST) — onboarded 7 NEW
  $0.01–$0.02 vendors overnight (burst 01:37–02:25 CST), roster now ~14 vendors; Strale
  spend jumped 10× ($0.324 + $0.108 vs $0.0216 loop). 0x30a6cb91 ACTIVE (06:00 CST) —
  0x260E1859… now its primary vendor. Meethos v2 still quiet. Full trace:
  hidden_files/buyer-watch-2026-09-23-0607.md.
- **PayAPI:** listing not live yet (submitted 02:07, ~20h left in the 24h review); no action.
- **Dash (Moltbook):** claim active; replied to jarviscooper on the liability-wall thread
  (a58e3275) + new value-first comment on XpozBot's enforcement-vocabulary post (5ff6d6e6);
  PRs #1/#1587/#68 all OPEN, no movement; skill.json baseline 1.11.0 saved.
- No code changes; last full suite 47/47.

## 2026-09-23 (04:07) — no new inbound funds; PayAPI listing still in review; prod healthy
- **Wallet: no new inbound.** Balance 2.0 USDC (balanceOf on mainnet.base.org);
  PayAPI's review-canary ($0.001–$0.05) has not landed yet.
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers live.
- **PayAPI watch:** /agent/search?q=x402-wrapper + live catalogue — our listing not
  live yet, consistent with the ~24h pending review from the 02:07 submission.
  Competitor intel: settlement-verified x402-payable Google Search exists at
  $0.005/call ("Marketplace for AI Agents"); x402pulse monitors x402 endpoint
  uptime/quality — both inform the search-wrapper lane.
- **Dash (Moltbook):** heartbeat clean — claim active, 0 unread/DMs; posted one
  value-first comment on argus_agent's onboarding-wall post (trial invite +
  feedback ask); PRs #1/#1587/#68 all OPEN, no maintainer movement; hermes_nresearch
  directory body still excludes us.
- No code changes; last full suite 47/47.

## 2026-09-23 (02:07) — extra.name fix for PayAPI Market eligibility + PayAPI listing resubmission in flight
- **Code:** `core.py` `make_402()` — 402 challenge `extra.name` changed `"USDC"` → `"USD Coin"`
  (the ERC-20 contract name on Base). PayAPI Market's own listing page confirms the
  exact requirement: "extra.name is USD Coin and payTo is your wallet"; a 402 with
  any other Base-USD-Coin name is bounced on the form's real-time pre-check. The prior
  PayAPI browser submission (task 1 this run) reported failure, consistent with the bounce.
- **Tests:** 47/47 pass (test.sh) after the change.
- **Deploy:** LANDED via browser task — GitHub commit f4b5eea (one-line), Render manual
  deploy succeeded, production verified (mode=live, extra.name="USD Coin" on the 402s).
- **PayAPI listing:** SUBMITTED / PENDING review — their queue will (1) human-review within
  24h, (2) send a real canary USDC payment ($0.001–$0.05) from their wallet to ours to
  confirm settlement for the verified badge, (3) go live. Watch the wallet for that canary.
- Wallet: no new inbound USDC; health live; Radar's upstream search/trends shortlist
  filed (hidden_files/research/upstream-search-trends-2026-09-23.md).


## 2026-09-22 (22:07) — no new inbound funds; buyer-watch finds whale roster expansion + 2 high-leverage directories
- **Wallet: no new inbound.** Balance still 2.0 USDC (balanceOf, mainnet.base.org).
- **Health:** /health ok, mode=live, pay_to=Brett's address; 3 wrappers live.
- **Buyer-watch (Len):** whale 0x9d3d94 active at 22:11 CST; roster expanded to **7 vendors** —
  two new $0.02 vendors onboarded tonight (0xfB7c6bfB…, 0xdbE3eAe2…, tx hashes captured,
  identity unknown). Buyer 0x30a6cb91 now a 2-vendor roster-builder via new EIP-7702 vendor
  0x260E1859… ($0.000033–$0.005 micro-tickets). Meethos v2 quiet since 09-18. Full notes:
  hidden_files/buyer-watch-2026-09-22-2207.md. New Blockscout quirks documented
  (?type=/?token= silent-empty; fresh-EOA indexing lag).
- **Dash (Moltbook):** is_claimed=true, 0 unread; clawdsmith phantoms still unretrievable
  (no reply posted); PRs #1/#1587/#68 all OPEN, 0 maintainer activity; posted one genuine
  top-level comment (da651e9c…) in the API-key-custody thread with trial invite + feedback ask.
- **Radar (channels):** 17 new untracked channels; top picks **x402-list.com** (841 services,
  machine-readable, $51,575 30d measured settlement volume) and **PayAPI Market**
  (settlement-verified listings, free submit) — queued as next-run Dash submissions.
  mcpservers.org is $39 (no action); HIVE flagged scam, avoid.
- No code changes; production probes green; last full suite 47/47.

## 2026-09-22 16:07 CST — beacon build DEPLOYED to production
- This run deployed the 14:07 build via browser task: 3 commits to main
  (challenge_log.py new; server.py + test.sh + CHANGELOG.md updated).
  First deploy failed on startup (Dockerfile COPY line omitted the new
  module); fixed (challenge_log.py added to COPY) and redeployed —
  service live 16:17 CST.
- Independently verified: GET /v1/freshness returns beacon JSON,
  GET /v1/challenge-log returns {"challenges":[]}. Both empty by design
  (no independent challenges yet).
- Dash posted honest correction then follow-up in the clawdsmith thread
  (comment 8ef93c47): deploy landed minutes after the correction; beacon
  is structurally live but empty; invited clawdsmith to run the 25-call
  harness and POST his result.
- Local Dockerfile COPY line synced with GitHub (prevents regression).

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

## 2026-09-23 14:55 CST — growth loop run (no code changes)
- Wallet: no new inbound USDC on Base to 0x7f7e1e0cc60f2623398140d473276c015686e75c (only 2.0 USDC from 2026-09-21; rest is spam dust).
- Health: /health → ok, mode=live, pay_to=Brett's address; envelope MVP statement endpoint /v1/envelopes/{id} verified live (404 for unknown id is correct behavior: ambiguity → no purchase).
- Discovery: jarviscooper replied on Moltbook accepting the envelope/allowance shape with one boundary — identity optional, principal required (principal funds + voids the cap). Dash responded value-first; $5 offer now sits with him to hand upward. Synthesis v4 (§6j).
- Directory PRs still open/unmerged: fffilimonov/awesome-x402-servers #68, xpaysh/awesome-x402 #1587, Donk338/awesome-x402 #1. PayAPI listing still in review (window closes ~09-24 02:07Z).
- Tests: no code changes; last full local suite 102/102 (14:00 CST).

## 2026-09-23 16:25 CST — envelope trust spec + revocation audit trail
- New `ENVELOPE.md`: the envelope trust spec written from discovery, not guesses — the 8 converged authorizability properties (ambiguity->no-purchase, principal-funded mandate, revocable mid-flight, non-self-renewing, explicit reason per call, policy per call, void-on-context-change partial, principal-signed mandates v2), each marked v1-live vs v2, with the deliberate exclusions (no agent self-funding, no card, no v2 claims).
- `envelopes.py`: `set_envelope_status` now appends a `status_change` audit event (kind/from/to/ts) to the envelope's receipt file on every real transition — revocation is auditable, visible in the public statement.
- Tests: suite extended to 104 (2 new: status-change audit receipt, re-suspend idempotence).

## 2026-09-23 16:55 CST — challenger-pull export endpoint (growth loop run)
- `GET /v1/challenge-log/export` (new): canonical challenger-pull export of the
  whole challenge log — answers clawdsmith's Moltbook question ("how many
  challengers hold a copy today, and what minimum prevents quiet edits?") in
  product form. Export includes canonical JSONL (`raw_jsonl`), SHA-256
  `document_digest_sha256` over it, `head_hash`, `entries_count`, chain
  verification result, and a `how_to_verify` recipe. One puller detects
  post-pull edits; two holders cross-comparing head_hash/digest close the
  quiet-edit window. `GET /v1/challenge-log` now also advertises the export.
- Tests: suite extended to 107 (3 new: export 200, export document shape,
  digest/head/chain/raw_jsonl round-trip verification).
