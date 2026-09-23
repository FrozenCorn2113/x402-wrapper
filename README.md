# x402 Middleman Wrapper — v1 prototype (local only)

A proxy that wraps ordinary web APIs as agent-payable endpoints. Agents pay
per call in USDC via an x402-style flow; we broker the call and keep a spread.

**v1 is a local prototype:** payment verification is mocked, nothing settles
on-chain, `payTo` is a placeholder. See `../PLAN.md` §4 and §8 for what's
stubbed and what v2 needs (Brett's approval: real wallet + facilitator).

## Layout

- `server.py` — FastAPI proxy (`GET /v1/{wrapper}`, `GET /v1` catalog, `GET /health`)
- `core.py` — shared logic: configs, mock 402/verification, forwarding, receipts
- `mcp_server.py` — MCP server over stdio; each wrapper is a priced tool
- `configs/*.yaml` — wrapper definitions (upstream, pricing, rate limits)
- `receipts/` — JSONL usage logs (created on first paid call)
- `test.sh` — end-to-end curl test of the 402 flow

## Run the proxy

```bash
cd ~/workspace/goals/launch-a-business-from-scratch/wrapper-v1
.venv/bin/python server.py   # http://127.0.0.1:8000
```

## Try it

```bash
# 1. Catalog — machine-readable price list
curl http://127.0.0.1:8000/v1

# 2. No payment -> 402 with x402 payment terms
curl -i "http://127.0.0.1:8000/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"

# 3. Mock-paid call -> 200 with upstream data + receipt
curl -H "X-Payment: mock-demo123" \
  "http://127.0.0.1:8000/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"

curl -H "X-Payment: mock-demo123" \
  "http://127.0.0.1:8000/v1/crypto-price?ids=bitcoin&vs_currencies=usd"
```

Payment uses the standard `X-Payment` header carrying the Base tx hash of a
direct USDC transfer (verified read-only on-chain; each hash spendable once).
The 402 challenge follows the official x402 v2 envelope: `x402Version: 2`,
top-level `resource`, `accepts[]` with CAIP-2 network (`eip155:8453`) and the
USDC contract address, delivered in the body and base64-encoded in the
`PAYMENT-REQUIRED` response header. Legacy `X-Payment-Proof` still works.

## Run the MCP server

```bash
.venv/bin/python mcp_server.py
# then send newline-delimited JSON-RPC, e.g.:
# {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
# {"jsonrpc":"2.0","method":"notifications/initialized"}
# {"jsonrpc":"2.0","id":2,"method":"tools/list"}
# {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"weather-now",
#   "arguments":{"latitude":"43.7","longitude":"-79.4","current":"temperature_2m",
#   "payment_proof":"mock-demo123"}}}
```

## Run tests

```bash
./test.sh
```

## Add a new wrapper

Copy `configs/weather.yaml`, point `upstream` at any GET/POST API, set
`price_usdc` above your upstream cost, restart the server. No code changes.

## Deploy (free)

See [DEPLOY.md](DEPLOY.md) for the full $0 path (Render Docker deploy + Fly.io
alternative). Short version: push this folder to GitHub, deploy as a Docker web
service, set env vars:

| Variable | Default | Notes |
|---|---|---|
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Set to your public URL in prod |
| `PAY_TO_ADDRESS` | `0xREPLACE_ME_BEFORE_DEPLOY` | Brett's Base wallet (public address only) |
| `MOCK_PAYMENTS` | `true` | Auto-flips to `false` once a real wallet is set |
| `NETWORK` | `base` | x402 network label |
| `USDC_ASSET` | Base USDC contract | Token contract the verifier trusts |
| `BASE_RPC_URL` | `https://mainnet.base.org` | Free public Base RPC |
| `PORT` | `8000` | Injected automatically by Render/Railway/Fly |

`verify_onchain.py` is the real payment verifier: in live mode the
`X-Payment` header must be a Base tx hash of a USDC transfer to
`PAY_TO_ADDRESS` covering the call price (spendable once — replay protected).
No private keys anywhere — read-only RPC verification.
