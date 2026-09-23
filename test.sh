#!/bin/bash
# End-to-end test of the x402 v2 flow. Run from wrapper-v1/:  ./test.sh
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
BASE=http://127.0.0.1:8000

$PY server.py & SRV=$!
trap "kill $SRV 2>/dev/null" EXIT
sleep 3
# Replay-protection state persists across runs; reset for a hermetic test.
rm -f receipts/spent_hashes.json challenge-log/challenge_log.jsonl challenge-log/challenge_log.jsonl.bak

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
check "freshness reports chain_valid" 200 "$BASE/v1/freshness"
grep -q '"chain_valid":true' /tmp/wrap_test.json && echo "PASS: freshness chain_valid:true" && pass=$((pass+1)) || { echo "FAIL: freshness chain_valid"; fail=$((fail+1)); }
check "bad submit (missing fields) -> 422" 422 -X POST -H 'Content-Type: application/json' -d '{"result":"pass"}' "$BASE/v1/challenge-log"
check "bad submit (bad result) -> 422" 422 -X POST -H 'Content-Type: application/json' -d '{"challenged_by":"x","challenge_type":"y","result":"maybe","details":"z"}' "$BASE/v1/challenge-log"
check "freshness beacon reflects submission" 200 "$BASE/v1/freshness"
grep -q '"challenged_by":"harness-ci v1"' /tmp/wrap_test.json && grep -q '"last_result":"pass"' /tmp/wrap_test.json && grep -qv '"staleness_seconds":null' /tmp/wrap_test.json && echo "PASS: beacon shows latest independent challenge" && pass=$((pass+1)) || { echo "FAIL: beacon after submit"; fail=$((fail+1)); }
grep -q '"target_interval_seconds": *3600' /tmp/wrap_test.json && echo "PASS: week-1 hourly cadence" && pass=$((pass+1)) || { echo "FAIL: cadence"; fail=$((fail+1)); }

echo ""
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
