# Envelopes — prepaid spend budgets (spec, v1)

**Status:** v1 MVP live in `envelopes.py` (+ admin API in `server.py`).
**Origin:** customer discovery 2026-09-22/23, not a guess. Three agents
independently described this shape; the trust doctrine below comes from
jarviscooper (Moltbook, verbatim-lean), AureliusX, deepdonorbot, and the
nanoswarm convergence replies.

## The problem it solves

Some agents run under a funded principal that **cannot authorize spend**:
jarviscooper: "I won't spend a principal's funds to generate a data point."
Near-free pricing does not fix onboarding for these agents — the blocker is
*authorization*, not price. The envelope gives the principal a prepaid,
policy-bounded budget the agent draws down without touching the principal's
wallet per call.

## The converged trust doctrine (from discovery)

Every property below was stated by at least one agent as a requirement.
Each is marked **v1 (live)** or **v2 (documented, not built)**.

### 1. Ambiguity resolves to NO purchase — v1 LIVE
`try_spend()`: ANY ambiguity — unknown envelope id, suspended/closed status,
cap exceeded, short balance, velocity tripped, missing or malformed reason —
returns HTTP 402 `ENVELOPE_DECLINED` and **never** decrements, charges, or
forwards. Verified by 49 envelope tests (102/102 suite).

### 2. The mandate is issued against the principal's money, not the agent's word — v1 LIVE
Operator opens/tops up envelopes ONLY after read-only on-chain verification
that the principal sent USDC on Base to the business wallet
`0x7f7e1e0cc60f2623398140d473276c015686e75c`. v1 verification is manual
(Len reads the transfer on Base, then calls the admin API); the code records
only what the operator attests. **We never hold customer keys and cannot move
customer funds.** Only Brett can release payouts. Contract escrow is v2.

### 3. Revocable mid-flight — v1 LIVE
Principal (via the operator) can suspend or close an envelope at any time:
`POST /v1/admin/envelopes/{id}/status` with `{status: "suspended"|"closed"}`.
Suspension is enforced inside `try_spend()` on the very next call — a
suspended envelope declines instantly, no drain path. Status changes are
appended to the envelope's receipt line as an audit event.

### 4. Non-self-renewing — v1 LIVE
The agent holding the envelope **cannot top it up**. Top-up is an
operator-only admin endpoint (`POST /v1/admin/envelopes/{id}/topup`), backed
only by a verified on-chain top-up from the principal's wallet. An envelope
cannot be refilled from spend, from calls, or from the agent side — ever.

### 5. Explicit reason per call — v1 LIVE
Principal policy can require `X-Reason` on every call (≤500 chars).
Missing or malformed reason when required → `ENVELOPE_DECLINED`
(per AureliusX: "a reversible envelope plus an explicit reason for the call,
not just a hard ceiling"). The reason is stored on the receipt line — the
agent's spend is auditable spend, not blind drawdown.

### 6. Policy envelope per call — v1 LIVE
Every call is checked against the principal's spend policy BEFORE anything
moves: envelope active, balance covers the price, price within the per-call
cap, endpoint in the approved allowlist, per-envelope velocity cap
(per-minute sliding window). Envelope calls skip the 402 x402 flow entirely.

### 7. Void on context change — v1 partial, v2 full
v1: the operator can suspend/close on context change, and status is checked
per call (no long-lived grants). What is NOT in v1: cryptographic binding of
the mandate to a context hash, so the envelope cannot *self-void* when the
task context shifts — that needs the EIP-712 principal-signed mandate (v2),
which carries a context/digest field that stales on change.

### 8. Principal-signed mandates — v2 (NOT BUILT)
jarviscooper's first doctrine point: the mandate must be signed by the
PRINCIPAL, not the agent. v1 is honest about this gap — llms.txt carries the
HONESTY NOTE in plain words: v1 envelopes are OPERATOR-ISSUED mandates;
principal-signed (EIP-712) mandates are v2. The signed-style receipt emitted
today is an operator attestation, labeled as such in code.

## Admin API (operator only)

| Method | Endpoint | Effect |
|---|---|---|
| POST | `/v1/admin/envelopes` | Open envelope (after verified on-chain top-up) |
| POST | `/v1/admin/envelopes/{id}/topup` | Record credit (after verified on-chain top-up) |
| POST | `/v1/admin/envelopes/{id}/status` | `active` / `suspended` (revoke) / `closed` |
| GET | `/v1/envelopes/{id}` | Public statement: balance, policy, receipts |

Envelope calls: `X-Envelope: <id>` on any `/v1/{wrapper}` route (+
`X-Reason` when policy requires).

## v2 roadmap (only when real volume justifies it)

1. EIP-712 principal-signed mandates with context-hash staleness (self-void).
2. Contract escrow for invalidation "where the money is" (Brett's trust
   design today: Len tracks balances, Brett alone releases payouts —
   the business structurally cannot run with customer money).
3. Automated on-chain top-up detection (replace manual verification).

## What's deliberately NOT here

- No agent self-service funding. No credit cards. No per-call wallet
  signatures. No claims about v2 features being live.
