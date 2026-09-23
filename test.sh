#!/bin/bash
# End-to-end test of the x402 v2 flow. Run from wrapper-v1/:  ./test.sh
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
BASE=http://127.0.0.1:8000

# Admin auth for envelope tests (test-only token; real deployments set their own).
export ADMIN_TOKEN=test-admin-token

$PY server.py & SRV=$!
trap "kill $SRV 2>/dev/null" EXIT
sleep 3
# Replay-protection state persists across runs; reset for a hermetic test.
rm -f receipts/spent_hashes.json challenge-log/challenge_log.jsonl challenge-log/challenge_log.jsonl.bak
# Envelope ledger state persists too; reset for hermetic tests.
rm -f envelopes/envelopes.json receipts/envelope-*.jsonl

pass=0; fail=0
check() { # check <label> <expected_code> <curl args...>
  local label="$1" want="$2"; shift 2
  code=$(curl -s -o /tmp/wrap_test.json -D /tmp/wrap_headers.txt -w "%{http_code}" "$@")
  if [ "$code" = "$want" ]; then echo "PASS: $label (HTTP $code)"; pass=$((pass+1));
  else echo "FAIL: $label (want $want, got $code)"; fail=$((fail+1)); fi
}

echo "--- health ---"
check "health" 200 "$BASE/health"

echo "--- catalog ---"
check "catalog lists 3 wrappers" 200 "$BASE/v1"
grep -q weather-now /tmp/wrap_test.json && grep -q crypto-price /tmp/wrap_test.json && echo "PASS: catalog content" && pass=$((pass+1)) || { echo "FAIL: catalog content"; fail=$((fail+1)); }

echo "--- discovery manifest ---"
check "well-known x402" 200 "$BASE/.well-known/x402"
grep -q '"x402Version"' /tmp/wrap_test.json && grep -q 'weather-now' /tmp/wrap_test.json && grep -q 'payTo' /tmp/wrap_test.json && echo "PASS: discovery manifest content" && pass=$((pass+1)) || { echo "FAIL: discovery manifest"; fail=$((fail+1)); }

echo "--- llms.txt ---"
check "llms.txt" 200 "$BASE/llms.txt"
grep -q 'How to pay' /tmp/wrap_test.json && grep -q 'X-Payment' /tmp/wrap_test.json && echo "PASS: llms.txt content" && pass=$((pass+1)) || { echo "FAIL: llms.txt"; fail=$((fail+1)); }

echo "--- 402 without payment (v2 envelope) ---"
check "no proof -> 402" 402 "$BASE/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"
grep -q '"x402Version":2' /tmp/wrap_test.json && grep -q '"resource"' /tmp/wrap_test.json && grep -q '"accepts"' /tmp/wrap_test.json && echo "PASS: 402 body is v2 PaymentRequired" && pass=$((pass+1)) || { echo "FAIL: 402 body shape"; fail=$((fail+1)); }
grep -q '"network":"eip155:8453"' /tmp/wrap_test.json && grep -q '"asset":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"' /tmp/wrap_test.json && echo "PASS: 402 uses CAIP-2 network + asset address" && pass=$((pass+1)) || { echo "FAIL: 402 network/asset"; fail=$((fail+1)); }
grep -qi '^payment-required:' /tmp/wrap_headers.txt && echo "PASS: PAYMENT-REQUIRED header present" && pass=$((pass+1)) || { echo "FAIL: PAYMENT-REQUIRED header"; fail=$((fail+1)); }
hdr=$(grep -i '^payment-required:' /tmp/wrap_headers.txt | sed 's/^[Pp][Aa][Yy][Mm][Ee][Nn][Tt]-//' | tr -d ' \r\n' | cut -d: -f2-)
echo "$hdr" | $PY -c "import sys,base64,json; d=json.loads(base64.b64decode(sys.stdin.read().strip())); assert d['x402Version']==2 and d['accepts'][0]['scheme']=='exact', 'bad challenge'; print('PASS: PAYMENT-REQUIRED header decodes to valid v2 challenge')" && pass=$((pass+1)) || { echo "FAIL: header challenge decode"; fail=$((fail+1)); }

echo "--- 402 with bad proof ---"
check "bad proof -> 402" 402 -H "X-Payment: nope" "$BASE/v1/weather-now?latitude=43.7"

echo "--- EIP-3009 payload gets instructive 402 ---"
payload=$(echo -n '{"x402Version":2,"scheme":"exact","network":"eip155:8453","payload":{"signature":"0xabc","authorization":{"from":"0x1","to":"0x2","value":"5000"}}}' | base64 -w0)
check "payment payload -> 402 w/ direct-transfer note" 402 -H "X-Payment: $payload" "$BASE/v1/weather-now?latitude=43.7"
grep -q 'direct-transfer' /tmp/wrap_test.json && echo "PASS: instructive settlement note" && pass=$((pass+1)) || { echo "FAIL: settlement note"; fail=$((fail+1)); }

echo "--- paid call (mock, X-Payment) ---"
check "mock proof -> 200" 200 -H "X-Payment: mock-v2test1" \
  "$BASE/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"
grep -q 'temperature_2m' /tmp/wrap_test.json && echo "PASS: upstream data forwarded" && pass=$((pass+1)) || { echo "FAIL: upstream data"; fail=$((fail+1)); }
grep -q 'mock_settlement' /tmp/wrap_test.json && echo "PASS: receipt attached" && pass=$((pass+1)) || { echo "FAIL: receipt"; fail=$((fail+1)); }

echo "--- legacy X-Payment-Proof header still works ---"
check "legacy header -> 200" 200 -H "X-Payment-Proof: mock-v2legacy1" \
  "$BASE/v1/echo?msg=hello"
grep -q 'hello' /tmp/wrap_test.json && echo "PASS: legacy header accepted" && pass=$((pass+1)) || { echo "FAIL: legacy header"; fail=$((fail+1)); }

echo "--- replay protection ---"
check "reuse of spent proof -> 402" 402 -H "X-Payment: mock-v2test1" \
  "$BASE/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"

echo "--- crypto wrapper ---"
check "crypto-price paid -> 200" 200 -H "X-Payment: mock-v2crypto1" \
  "$BASE/v1/crypto-price?ids=bitcoin&vs_currencies=usd"
grep -qi 'bitcoin' /tmp/wrap_test.json && echo "PASS: coingecko data" && pass=$((pass+1)) || { echo "FAIL: coingecko data"; fail=$((fail+1)); }

echo "--- receipts log ---"
# NB: cat the glob instead of redirecting it — "< receipts/*.jsonl" breaks
# with "ambiguous redirect" once more than one daily jsonl exists.
ls receipts/*.jsonl >/dev/null 2>&1 && [ "$(cat receipts/*.jsonl | wc -l)" -ge 2 ] \
  && echo "PASS: receipts logged" && pass=$((pass+1)) || { echo "FAIL: receipts"; fail=$((fail+1)); }

echo "--- unknown wrapper ---"
check "unknown -> 404" 404 -H "X-Payment: mock-x" "$BASE/v1/nope"

echo "--- loop protection (circuit breaker) ---"
# 30 identical unpaid calls from one client: threshold is 25/60s.
for i in $(seq 1 30); do
  curl -s -o /dev/null "$BASE/v1/echo?msg=looptest-shape-A" || true
done
check "identical loop trips -> 429" 429 "$BASE/v1/echo?msg=looptest-shape-A"
grep -q 'AGENT_LOOP_DETECTED' /tmp/wrap_test.json && echo "PASS: loop payload code" && pass=$((pass+1)) || { echo "FAIL: loop payload code"; fail=$((fail+1)); }
grep -qi '^retry-after:' /tmp/wrap_headers.txt && echo "PASS: Retry-After header present" && pass=$((pass+1)) || { echo "FAIL: Retry-After header"; fail=$((fail+1)); }
grep -qi '^x-loop-protection: tripped' /tmp/wrap_headers.txt && echo "PASS: X-Loop-Protection header" && pass=$((pass+1)) || { echo "FAIL: X-Loop-Protection header"; fail=$((fail+1)); }
# Cooldown is per request shape: different params from the same client pass.
check "different params not tripped" 402 "$BASE/v1/echo?msg=looptest-shape-B"
# Identity isolation: a different client sending the same looping shape passes.
check "different client not tripped" 402 -H "X-Forwarded-For: 203.0.113.9" "$BASE/v1/echo?msg=looptest-shape-A"
# Catalog advertises the breaker config.
check "catalog exposes loop_protection" 200 "$BASE/v1"
grep -q 'loop_protection' /tmp/wrap_test.json && grep -q 'identical_threshold' /tmp/wrap_test.json && echo "PASS: catalog loop_protection content" && pass=$((pass+1)) || { echo "FAIL: catalog loop_protection"; fail=$((fail+1)); }

# Pollable loop-protection report (buyer-verifiability counter).
check "loop-protection report -> 200" 200 "$BASE/v1/loop-protection"
grep -q '"loops_tripped":[ ]\?[1-9]' /tmp/wrap_test.json && grep -q '"loop_blocked_calls":[ ]\?[1-9]' /tmp/wrap_test.json && echo "PASS: report counters reflect the tripped loop" && pass=$((pass+1)) || { echo "FAIL: report counters"; fail=$((fail+1)); }
grep -q '"honesty"' /tmp/wrap_test.json && grep -q '"identical_threshold"' /tmp/wrap_test.json && echo "PASS: report honesty + policy fields" && pass=$((pass+1)) || { echo "FAIL: report honesty/policy"; fail=$((fail+1)); }

echo "--- freshness beacon + challenge log ---"
check "freshness beacon -> 200" 200 "$BASE/v1/freshness"
grep -q 'last_independently_challenged_at' /tmp/wrap_test.json && grep -q 'challenged_by' /tmp/wrap_test.json && grep -q '"staleness_seconds":null' /tmp/wrap_test.json && echo "PASS: empty beacon shape (no challenges yet)" && pass=$((pass+1)) || { echo "FAIL: empty beacon shape"; fail=$((fail+1)); }
check "challenge log (empty) -> 200" 200 "$BASE/v1/challenge-log"
grep -q '"challenges":\[\]' /tmp/wrap_test.json && echo "PASS: empty log" && pass=$((pass+1)) || { echo "FAIL: empty log"; fail=$((fail+1)); }
check "submit challenge -> 201" 201 -X POST -H 'Content-Type: application/json' -d '{"challenged_by":"harness-ci v1","challenge_type":"identical-loop-harness","result":"pass","details":"25 identical unpaid calls to /v1/echo all returned 429 AGENT_LOOP_DETECTED"}' "$BASE/v1/challenge-log"
grep -q '"id":1' /tmp/wrap_test.json && grep -q '"result":"pass"' /tmp/wrap_test.json && echo "PASS: stored entry shape" && pass=$((pass+1)) || { echo "FAIL: stored entry shape"; fail=$((fail+1)); }
grep -q '"prev_hash":"0\{64\}"' /tmp/wrap_test.json && grep -q '"entry_hash":"[0-9a-f]\{64\}"' /tmp/wrap_test.json && echo "PASS: entry hash-chained (genesis prev)" && pass=$((pass+1)) || { echo "FAIL: hash chain fields"; fail=$((fail+1)); }
check "submit second challenge -> 201" 201 -X POST -H 'Content-Type: application/json' -d '{"challenged_by":"harness-ci v1","challenge_type":"identical-loop-harness","result":"pass","details":"repeat run 2"}' "$BASE/v1/challenge-log"
check "challenge log lists 2 chained entries" 200 "$BASE/v1/challenge-log"
$PY - <<'PYEOF'
import json
rows = json.load(open('/tmp/wrap_test.json'))['challenges']
assert len(rows) == 2, rows
assert rows[1]['prev_hash'] == rows[0]['entry_hash'], 'chain link broken'
import hashlib
for r in rows:
    body = {k: v for k, v in r.items() if k != 'entry_hash'}
    canon = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(canon).hexdigest() == r['entry_hash'], f"bad entry_hash id={r['id']}"
print('PASS: chain links + entry hashes verify')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: chain verification"; fail=$((fail+1)); }
check "challenge-log export -> 200" 200 "$BASE/v1/challenge-log/export"
grep -q '"format":"x402wrapper-challenge-export"' /tmp/wrap_test.json && grep -q '"head_hash":"[0-9a-f]\{64\}"' /tmp/wrap_test.json && grep -q '"document_digest_sha256":"[0-9a-f]\{64\}"' /tmp/wrap_test.json && echo "PASS: export document shape" && pass=$((pass+1)) || { echo "FAIL: export shape"; fail=$((fail+1)); }
$PY - <<'PYEOF'
import json, hashlib
doc = json.load(open('/tmp/wrap_test.json'))
rows = doc['entries']
assert doc['entries_count'] == 2 == len(rows), doc['entries_count']
assert doc['head_hash'] == rows[-1]['entry_hash'], 'head_hash mismatch'
# digest recomputes from the raw canonical JSONL
assert hashlib.sha256(doc['raw_jsonl'].encode()).hexdigest() == doc['document_digest_sha256'], 'document digest mismatch'
assert doc['chain_valid'] is True, 'chain_valid false'
# raw_jsonl round-trips: parse -> rows equal entries
raw_rows = [json.loads(line) for line in doc['raw_jsonl'].splitlines() if line.strip()]
assert raw_rows == rows, 'raw_jsonl round-trip mismatch'
print('PASS: export digest/head/chain/raw_jsonl verify')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: export verification"; fail=$((fail+1)); }
check "freshness reports chain_valid" 200 "$BASE/v1/freshness"
grep -q '"chain_valid":true' /tmp/wrap_test.json && echo "PASS: freshness chain_valid:true" && pass=$((pass+1)) || { echo "FAIL: freshness chain_valid"; fail=$((fail+1)); }
check "bad submit (missing fields) -> 422" 422 -X POST -H 'Content-Type: application/json' -d '{"result":"pass"}' "$BASE/v1/challenge-log"
check "bad submit (bad result) -> 422" 422 -X POST -H 'Content-Type: application/json' -d '{"challenged_by":"x","challenge_type":"y","result":"maybe","details":"z"}' "$BASE/v1/challenge-log"
check "freshness beacon reflects submission" 200 "$BASE/v1/freshness"
grep -q '"challenged_by":"harness-ci v1"' /tmp/wrap_test.json && grep -q '"last_result":"pass"' /tmp/wrap_test.json && grep -qv '"staleness_seconds":null' /tmp/wrap_test.json && echo "PASS: beacon shows latest independent challenge" && pass=$((pass+1)) || { echo "FAIL: beacon after submit"; fail=$((fail+1)); }
grep -q '"target_interval_seconds": *3600' /tmp/wrap_test.json && echo "PASS: week-1 hourly cadence" && pass=$((pass+1)) || { echo "FAIL: cadence"; fail=$((fail+1)); }

echo "--- envelopes (prepaid budgets) ---"
WALLET=0x1234567890abcdef1234567890abcdef12345678
AUTH="Authorization: Bearer $ADMIN_TOKEN"
CREATE_BODY="{\"principal_wallet\":\"$WALLET\",\"label\":\"jarviscooper trial\",\"usd_amount\":5,\"per_call_cap\":0.001,\"allowed_paths\":[\"weather-now\",\"crypto-price\",\"echo\"],\"velocity_per_min\":60,\"reason_required\":false}"

echo "--- envelope admin auth + create ---"
check "admin create without token -> 401" 401 -X POST -H 'Content-Type: application/json' -d "$CREATE_BODY" "$BASE/v1/admin/envelopes"
check "admin create with token -> 201" 201 -X POST -H "$AUTH" -H 'Content-Type: application/json' -d "$CREATE_BODY" "$BASE/v1/admin/envelopes"
ENV_ID=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['envelope']['id'])")
[ -n "$ENV_ID" ] && echo "PASS: envelope id $ENV_ID captured" && pass=$((pass+1)) || { echo "FAIL: envelope id capture"; fail=$((fail+1)); }
grep -q '"balance_atomic": *5000000' /tmp/wrap_test.json && grep -q '"status": *"active"' /tmp/wrap_test.json && echo "PASS: create response balance/status" && pass=$((pass+1)) || { echo "FAIL: create response"; fail=$((fail+1)); }

echo "--- envelope drawdown spends balance ---"
check "envelope drawdown echo -> 200" 200 -H "X-Envelope: $ENV_ID" "$BASE/v1/echo?msg=env-draw-1"
grep -q '"type": *"envelope"' /tmp/wrap_test.json && grep -q "$ENV_ID" /tmp/wrap_test.json && echo "PASS: envelope receipt attached" && pass=$((pass+1)) || { echo "FAIL: envelope receipt"; fail=$((fail+1)); }
grep -q '"balance_remaining_atomic": *4999900' /tmp/wrap_test.json && echo "PASS: receipt shows remaining balance" && pass=$((pass+1)) || { echo "FAIL: receipt balance"; fail=$((fail+1)); }

echo "--- envelope statement ---"
check "statement -> 200" 200 "$BASE/v1/envelopes/$ENV_ID"
grep -q '"balance_atomic": *4999900' /tmp/wrap_test.json && grep -q '"per_call_cap_atomic": *1000' /tmp/wrap_test.json && grep -q '"reason_required": *false' /tmp/wrap_test.json && echo "PASS: statement balance + policy" && pass=$((pass+1)) || { echo "FAIL: statement contents"; fail=$((fail+1)); }
grep -q '"call_id"' /tmp/wrap_test.json && echo "PASS: statement includes receipt lines" && pass=$((pass+1)) || { echo "FAIL: statement receipts"; fail=$((fail+1)); }
check "catalog advertises envelope_support" 200 "$BASE/v1"
grep -q '"envelope_support": *true' /tmp/wrap_test.json && echo "PASS: envelope_support:true in /v1" && pass=$((pass+1)) || { echo "FAIL: envelope_support"; fail=$((fail+1)); }
check "unknown envelope statement -> 404" 404 "$BASE/v1/envelopes/env_abcdef012345"
check "unknown envelope drawdown -> 402" 402 -H "X-Envelope: env_abcdef012345" "$BASE/v1/echo?msg=env-unk"
grep -q 'ENVELOPE_DECLINED' /tmp/wrap_test.json && echo "PASS: unknown envelope -> ENVELOPE_DECLINED" && pass=$((pass+1)) || { echo "FAIL: unknown envelope code"; fail=$((fail+1)); }

echo "--- per-call cap enforcement ---"
check "create low-cap envelope -> 201" 201 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"cap test\",\"usd_amount\":1,\"per_call_cap\":0.00005,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":60,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
ENV_CAP=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['envelope']['id'])")
check "cap-exceeded drawdown -> 402" 402 -H "X-Envelope: $ENV_CAP" "$BASE/v1/echo?msg=env-cap"
grep -q 'ENVELOPE_DECLINED' /tmp/wrap_test.json && grep -q 'per-call cap' /tmp/wrap_test.json && echo "PASS: cap enforced w/ ENVELOPE_DECLINED" && pass=$((pass+1)) || { echo "FAIL: cap enforcement"; fail=$((fail+1)); }
# Nothing was decremented: statement still shows full balance.
check "capped envelope untouched" 200 "$BASE/v1/envelopes/$ENV_CAP"
grep -q '"balance_atomic": *1000000' /tmp/wrap_test.json && echo "PASS: no decrement on decline" && pass=$((pass+1)) || { echo "FAIL: decrement on decline"; fail=$((fail+1)); }

echo "--- reason-required policy ---"
check "create reason-required envelope -> 201" 201 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"reason test\",\"usd_amount\":1,\"per_call_cap\":0.001,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":60,\"reason_required\":true}" \
  "$BASE/v1/admin/envelopes"
ENV_REASON=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['envelope']['id'])")
check "missing X-Reason -> 400" 400 -H "X-Envelope: $ENV_REASON" "$BASE/v1/echo?msg=env-reason"
grep -q 'REASON_REQUIRED' /tmp/wrap_test.json && grep -q 'X-Reason' /tmp/wrap_test.json && echo "PASS: reason-required rejection" && pass=$((pass+1)) || { echo "FAIL: reason-required"; fail=$((fail+1)); }
check "with X-Reason -> 200" 200 -H "X-Envelope: $ENV_REASON" -H "X-Reason: smoke test of envelope policy" "$BASE/v1/echo?msg=env-reason-ok"
grep -q 'smoke test of envelope policy' /tmp/wrap_test.json && echo "PASS: reason recorded on receipt" && pass=$((pass+1)) || { echo "FAIL: reason on receipt"; fail=$((fail+1)); }

echo "--- velocity cap ---"
check "create velocity-2 envelope -> 201" 201 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"velocity test\",\"usd_amount\":1,\"per_call_cap\":0.001,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":2,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
ENV_VEL=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['envelope']['id'])")
check "velocity call 1 -> 200" 200 -H "X-Envelope: $ENV_VEL" "$BASE/v1/echo?msg=env-vel-1"
check "velocity call 2 -> 200" 200 -H "X-Envelope: $ENV_VEL" "$BASE/v1/echo?msg=env-vel-2"
check "velocity call 3 -> 402" 402 -H "X-Envelope: $ENV_VEL" "$BASE/v1/echo?msg=env-vel-3"
grep -q 'ENVELOPE_DECLINED' /tmp/wrap_test.json && grep -q 'velocity cap' /tmp/wrap_test.json && echo "PASS: velocity cap trips" && pass=$((pass+1)) || { echo "FAIL: velocity cap"; fail=$((fail+1)); }

echo "--- insufficient balance + topup + suspend ---"
check "create dust envelope -> 201" 201 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"dust test\",\"usd_amount\":0.0001,\"per_call_cap\":0.001,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":60,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
ENV_DUST=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['envelope']['id'])")
check "dust call 1 (exact balance) -> 200" 200 -H "X-Envelope: $ENV_DUST" "$BASE/v1/echo?msg=env-dust-1"
check "dust call 2 (short) -> 402" 402 -H "X-Envelope: $ENV_DUST" "$BASE/v1/echo?msg=env-dust-2"
grep -q 'ENVELOPE_DECLINED' /tmp/wrap_test.json && echo "PASS: insufficient balance refused" && pass=$((pass+1)) || { echo "FAIL: insufficient balance"; fail=$((fail+1)); }
check "topup -> 200" 200 -X POST -H "$AUTH" -H 'Content-Type: application/json' -d '{"usd_amount":0.001,"tx_hash":"0xmanualverification"}' "$BASE/v1/admin/envelopes/$ENV_DUST/topup"
grep -q '"balance_atomic": *1000' /tmp/wrap_test.json && echo "PASS: topup recorded" && pass=$((pass+1)) || { echo "FAIL: topup"; fail=$((fail+1)); }
check "post-topup drawdown -> 200" 200 -H "X-Envelope: $ENV_DUST" "$BASE/v1/echo?msg=env-dust-3"
check "suspend -> 200" 200 -X POST -H "$AUTH" -H 'Content-Type: application/json' -d '{"status":"suspended"}' "$BASE/v1/admin/envelopes/$ENV_DUST/status"
check "suspended drawdown -> 402" 402 -H "X-Envelope: $ENV_DUST" "$BASE/v1/echo?msg=env-dust-4"
grep -q 'ENVELOPE_DECLINED' /tmp/wrap_test.json && echo "PASS: suspended envelope refused" && pass=$((pass+1)) || { echo "FAIL: suspended refusal"; fail=$((fail+1)); }
check "statement shows suspended" 200 "$BASE/v1/envelopes/$ENV_DUST"
grep -q '"status": *"suspended"' /tmp/wrap_test.json && echo "PASS: statement status suspended" && pass=$((pass+1)) || { echo "FAIL: statement status"; fail=$((fail+1)); }
grep -q '"kind": *"status_change"' /tmp/wrap_test.json && grep -q '"from": *"active"' /tmp/wrap_test.json && grep -q '"to": *"suspended"' /tmp/wrap_test.json && echo "PASS: status change wrote audit receipt" && pass=$((pass+1)) || { echo "FAIL: status-change audit receipt"; fail=$((fail+1)); }
check "re-suspend (no change) -> 200" 200 -X POST -H "$AUTH" -H 'Content-Type: application/json' -d '{"status":"suspended"}' "$BASE/v1/admin/envelopes/$ENV_DUST/status"

echo "--- admin validation ---"
check "zero amount -> 400" 400 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"bad\",\"usd_amount\":0,\"per_call_cap\":0.001,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":60,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
check "unknown wrapper in paths -> 400" 400 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"bad\",\"usd_amount\":1,\"per_call_cap\":0.001,\"allowed_paths\":[\"nope\"],\"velocity_per_min\":60,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
check "velocity out of range -> 400" 400 -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"principal_wallet\":\"$WALLET\",\"label\":\"bad\",\"usd_amount\":1,\"per_call_cap\":0.001,\"allowed_paths\":[\"echo\"],\"velocity_per_min\":500,\"reason_required\":false}" \
  "$BASE/v1/admin/envelopes"
check "bad status value -> 400" 400 -X POST -H "$AUTH" -H 'Content-Type: application/json' -d '{"status":"deleted"}' "$BASE/v1/admin/envelopes/$ENV_DUST/status"
check "topup without token -> 401" 401 -X POST -H 'Content-Type: application/json' -d '{"usd_amount":1}' "$BASE/v1/admin/envelopes/$ENV_DUST/topup"

echo "--- llms.txt advertises envelopes ---"
check "llms.txt envelope section" 200 "$BASE/llms.txt"
grep -q 'Envelopes (prepaid budgets)' /tmp/wrap_test.json && grep -q 'HONESTY NOTE' /tmp/wrap_test.json && grep -q 'X-Envelope' /tmp/wrap_test.json && echo "PASS: llms.txt envelope copy + honesty note" && pass=$((pass+1)) || { echo "FAIL: llms.txt envelopes"; fail=$((fail+1)); }

echo ""
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
