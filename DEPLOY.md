# DEPLOY.md — ship the x402 wrapper for $0

Local prep is done: `Dockerfile`, `.dockerignore`, `requirements.txt`, env-driven
config, and a real on-chain USDC verifier (`verify_onchain.py`) are all in this
folder. Nothing here creates accounts or spends money — the steps below are for
a human (or a browser session) to execute.

## 0. What you need first

- This folder's contents pushed to a GitHub repo (Render/Railway read from git).
- Brett's **Base mainnet USDC wallet address** (public address only — never a
  private key or seed phrase; the service only *receives*).

## 1. Environment variables

Set these in the host dashboard (Render: Environment tab; Railway/Fly: their
variables UI). Only `PUBLIC_BASE_URL` is needed for a first smoke test.

| Variable | Required | Default | What it does |
|---|---|---|---|
| `PUBLIC_BASE_URL` | yes (prod) | `http://localhost:8000` | Your public URL, e.g. `https://x402-wrap.onrender.com`. Used in 402 `resource` fields and the `/v1` catalog. |
| `PAY_TO_ADDRESS` | yes (to earn) | `0xREPLACE_ME_BEFORE_DEPLOY` | Brett's Base wallet. The 402 `payTo` agents pay into. |
| `MOCK_PAYMENTS` | no | `true` | Mock mode until a real wallet is set. Auto-flips to `false` once `PAY_TO_ADDRESS` is a real `0x…` address; can also be set explicitly. |
| `NETWORK` | no | `base` | x402 network label in 402 responses. |
| `USDC_ASSET` | no | `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913` | USDC token contract on Base mainnet. The on-chain verifier only trusts Transfer events from this contract. |
| `BASE_RPC_URL` | no | `https://mainnet.base.org` | Free public Base RPC for receipt lookups. Rate-limited; fine for low volume. |
| `PORT` | no | `8000` | Render/Railway inject this automatically. |

## 2. Render (free tier) — recommended $0 path

1. [render.com](https://render.com) → New → **Web Service** → connect your GitHub repo.
2. If the repo root isn't this folder, set **Root Directory** to `wrapper-v1`.
3. Runtime: **Docker** (uses the `Dockerfile` here). Or Native: Build `pip install -r requirements.txt`, Start `uvicorn server:app --host 0.0.0.0 --port $PORT`.
4. Plan: **Free**. (Free services sleep after inactivity and wake on request — fine for an experiment; first call after idle takes ~30s.)
5. Add the env vars from §1.
6. Deploy. Note the public URL, e.g. `https://x402-wrap.onrender.com`.

## 3. Fly.io — alternative

1. Install `flyctl`, run `fly launch` inside this folder (it will detect the Dockerfile).
2. `fly secrets set PAY_TO_ADDRESS=0x… PUBLIC_BASE_URL=https://<app>.fly.dev`
3. `fly deploy`. Check Fly's current free allowances before deploying — they change.

## 4. Test the live 402 flow

Replace `APP` with your public URL:

```bash
APP=https://x402-wrap.onrender.com

# health: expect mode "mock" until the wallet is set
curl $APP/health

# catalog: machine-readable price list
curl $APP/v1

# no payment -> 402 with x402 payment terms (payTo = your wallet)
curl -i "$APP/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"

# mock-paid call (works while MOCK_PAYMENTS=true)
curl -H "X-Payment: mock-smoke1" \
  "$APP/v1/crypto-price?ids=bitcoin&vs_currencies=usd"
```

## 5. Going live (real money)

1. Brett creates a Base-network wallet and gives you the **public address**.
2. Set `PAY_TO_ADDRESS=0x…` (and `PUBLIC_BASE_URL`) in the host dashboard, redeploy.
3. `GET /health` should now report `"mode": "live"` and your address.
4. Real payment flow for an agent:
   - `GET $APP/v1/weather-now?...` → `402` with `accepts[0].payTo`, `.amount`, `.asset`.
   - Agent sends that USDC amount on Base to `payTo` from its own wallet.
   - Agent retries with `-H "X-Payment: 0x<tx-hash>"`.
   - Server fetches the tx receipt from Base RPC, finds the USDC `Transfer`
     event to `payTo` for ≥ the price, then forwards upstream and logs a receipt
     with `"mock_settlement": false`.
5. Watch `receipts/*.jsonl` (or add a log drain later) for real revenue.

## 6. Notes / limits

- **No private keys anywhere.** The service never signs or holds funds; it only
  verifies incoming transfers read-only.
- The free public RPC (`mainnet.base.org`) is rate-limited. If volume grows,
  get a dedicated RPC endpoint (many have free tiers).
- Verification trusts the RPC response; a compromised/malicious RPC could lie.
  For real revenue, pin a reputable RPC provider.
- Same-tx reuse: currently a tx hash can be replayed for repeat calls (each use
  is logged with a fingerprint). Add a spent-tx-hash store before scaling —
  flagged as the next daily-improve item.
- Free-tier hosts sleep when idle; agent clients should retry once on wake-up.
