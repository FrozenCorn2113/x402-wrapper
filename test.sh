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
# Holder-roster state persists too; reset for hermetic tests.
rm -f holder-roster/roster.json

pass=0; fail=0
check() { # check <label> <expected_code> <curl args...>
  local label="$1" want="$2"; shift 2
  # --max-time caps any single check: a wedged server or hung upstream must
  # fail the check, never stall the suite forever (2026-09-24: a lock
  # deadlock in new code hung a POST and stalled the whole run).
  code=$(curl -s --max-time 60 -o /tmp/wrap_test.json -D /tmp/wrap_headers.txt -w "%{http_code}" "$@")
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
grep -q '"extensions"' /tmp/wrap_test.json && grep -q '"bazaar"' /tmp/wrap_test.json && echo "PASS: manifest has extensions.bazaar block" && pass=$((pass+1)) || { echo "FAIL: extensions.bazaar"; fail=$((fail+1)); }
grep -q '"network":"eip155:8453"' /tmp/wrap_test.json && grep -q '"asset":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"' /tmp/wrap_test.json && echo "PASS: manifest network CAIP-2 + asset contract" && pass=$((pass+1)) || { echo "FAIL: manifest network/asset"; fail=$((fail+1)); }
grep -q 'fractions of a cent' /tmp/wrap_test.json && echo "PASS: price copy truthful (fractions of a cent)" && pass=$((pass+1)) || { echo "FAIL: price copy"; fail=$((fail+1)); }
$PY - <<'PYEOF'
import json
d = json.load(open('/tmp/wrap_test.json'))
bz = d['extensions']['bazaar']
ep = bz['info']['endpoints']
assert set(ep) == {'weather-now', 'crypto-price', 'echo'}, ep.keys()
assert bz['info']['pricing']['per_call_prices']['crypto-price'] == '0.001'
props = bz['schema']['properties']['info']['properties']
assert 'pricing' in props and 'endpoints' in props, 'schema incomplete'
print('PASS: bazaar endpoints + pricing + schema verify')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: bazaar structure"; fail=$((fail+1)); }

echo "--- llms.txt ---"
check "llms.txt" 200 "$BASE/llms.txt"
grep -q 'How to pay' /tmp/wrap_test.json && grep -q 'X-Payment' /tmp/wrap_test.json && echo "PASS: llms.txt content" && pass=$((pass+1)) || { echo "FAIL: llms.txt"; fail=$((fail+1)); }
grep -q 'Discovery shape' /tmp/wrap_test.json && grep -q 'extensions.bazaar' /tmp/wrap_test.json && echo "PASS: llms.txt advertises bazaar discovery shape" && pass=$((pass+1)) || { echo "FAIL: llms.txt discovery shape"; fail=$((fail+1)); }
grep -q 'skill.md' /tmp/wrap_test.json && echo "PASS: llms.txt advertises skill.md" && pass=$((pass+1)) || { echo "FAIL: llms.txt skill.md"; fail=$((fail+1)); }

echo "--- skill.md + agent-card aliases ---"
check "skill.md -> 200" 200 "$BASE/skill.md"
grep -q 'SKILL: x402-wrapper' /tmp/wrap_test.json && grep -q 'X-Envelope' /tmp/wrap_test.json && grep -q '0.0001' /tmp/wrap_test.json && echo "PASS: skill.md content" && pass=$((pass+1)) || { echo "FAIL: skill.md content"; fail=$((fail+1)); }
check "agent-card root alias -> 200" 200 "$BASE/agent-card.json"
grep -q '"skill_md"' /tmp/wrap_test.json && echo "PASS: root alias card advertises skill_md" && pass=$((pass+1)) || { echo "FAIL: root alias card"; fail=$((fail+1)); }
check "agent-card A2A alias -> 200" 200 "$BASE/.well-known/agent.json"
grep -q '"envelope_support": *true' /tmp/wrap_test.json && echo "PASS: A2A alias card content" && pass=$((pass+1)) || { echo "FAIL: A2A alias card"; fail=$((fail+1)); }

echo "--- 402 without payment (v2 envelope) ---"
check "no proof -> 402" 402 "$BASE/v1/weather-now?latitude=43.7&longitude=-79.4&current=temperature_2m"
grep -q '"x402Version":2' /tmp/wrap_test.json && grep -q '"resource"' /tmp/wrap_test.json && grep -q '"accepts"' /tmp/wrap_test.json && echo "PASS: 402 body is v2 PaymentRequired" && pass=$((pass+1)) || { echo "FAIL: 402 body shape"; fail=$((fail+1)); }
grep -q '"network":"eip155:8453"' /tmp/wrap_test.json && grep -q '"asset":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"' /tmp/wrap_test.json && echo "PASS: 402 uses CAIP-2 network + asset address" && pass=$((pass+1)) || { echo "FAIL: 402 network/asset"; fail=$((fail+1)); }
grep -qi '^payment-required:' /tmp/wrap_headers.txt && echo "PASS: PAYMENT-REQUIRED header present" && pass=$((pass+1)) || { echo "FAIL: PAYMENT-REQUIRED header"; fail=$((fail+1)); }
grep -qi '^x-payment-required:' /tmp/wrap_headers.txt && echo "PASS: X-Payment-Required header mirror present" && pass=$((pass+1)) || { echo "FAIL: X-Payment-Required mirror"; fail=$((fail+1)); }
grep -qi '^www-authenticate: X402 requirements="' /tmp/wrap_headers.txt && echo "PASS: WWW-Authenticate X402 variant present (BlockRun pattern)" && pass=$((pass+1)) || { echo "FAIL: WWW-Authenticate X402 variant"; fail=$((fail+1)); }
grep -q '"price":{"amount":"0.0005","currency":"USD"}' /tmp/wrap_test.json && echo "PASS: 402 body repeats price at top level (BlockRun pattern)" && pass=$((pass+1)) || { echo "FAIL: 402 top-level price"; fail=$((fail+1)); }
grep -q '"error":"Payment required. weather-now costs $0.0005 USDC per call."' /tmp/wrap_test.json && echo "PASS: 402 error carries plain-English price sentence (Strale pattern)" && pass=$((pass+1)) || { echo "FAIL: 402 error price sentence"; fail=$((fail+1)); }
grep -qi '^link:.*agent-card' /tmp/wrap_headers.txt && echo "PASS: 402 carries Link header to agent-card (Strale pattern)" && pass=$((pass+1)) || { echo "FAIL: 402 Link agent-card"; fail=$((fail+1)); }
grep -qi '^access-control-expose-headers:.*payment-required' /tmp/wrap_headers.txt && echo "PASS: 402 exposes payment headers for CORS (Strale pattern)" && pass=$((pass+1)) || { echo "FAIL: 402 CORS expose headers"; fail=$((fail+1)); }
grep -qi '^access-control-expose-headers:.*www-authenticate' /tmp/wrap_headers.txt && echo "PASS: 402 CORS expose list includes WWW-Authenticate mirror" && pass=$((pass+1)) || { echo "FAIL: 402 CORS expose includes WWW-Authenticate"; fail=$((fail+1)); }
$PY - <<'PYEOF'
import re, base64, json
hdrs = open('/tmp/wrap_headers.txt').read()
a = re.search(r'(?im)^payment-required:\s*(\S+)', hdrs).group(1)
b = re.search(r'(?im)^x-payment-required:\s*(\S+)', hdrs).group(1)
w = re.search(r'(?im)^www-authenticate:\s*X402 requirements="([^"]+)"', hdrs).group(1)
assert a == b == w, 'header values differ'
d = json.loads(base64.b64decode(a.strip()))
assert d['price'] == {'amount': '0.0005', 'currency': 'USD'}, d.get('price')
print('PASS: all 3 header mirrors identical; decoded challenge carries top-level price')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: header mirror verification"; fail=$((fail+1)); }
hdr=$(grep -i '^payment-required:' /tmp/wrap_headers.txt | sed 's/^[Pp][Aa][Yy][Mm][Ee][Nn][Tt]-//' | tr -d ' \r\n' | cut -d: -f2-)
echo "$hdr" | $PY -c "import sys,base64,json; d=json.loads(base64.b64decode(sys.stdin.read().strip())); assert d['x402Version']==2 and d['accepts'][0]['scheme']=='exact', 'bad challenge'; print('PASS: PAYMENT-REQUIRED header decodes to valid v2 challenge')" && pass=$((pass+1)) || { echo "FAIL: header challenge decode"; fail=$((fail+1)); }

echo "--- x402scan OpenAPI compatibility ---"
check "openapi.json serves" 200 "$BASE/openapi.json"
$PY - <<'PYEOF' && echo "PASS: openapi.json lists only the three explicit paid endpoints (GET+POST each)" && pass=$((pass+1)) || { echo "FAIL: openapi paid-endpoint shape"; fail=$((fail+1)); }
import json
spec = json.load(open('/tmp/wrap_test.json'))
paths = set(spec['paths'])
assert paths == {'/v1/weather-now', '/v1/crypto-price', '/v1/echo'}, f"openapi paths: {sorted(paths)}"
for p in paths:
    assert set(spec['paths'][p]) == {'get', 'post'}, f"{p} methods: {set(spec['paths'][p])}"
    ids = [spec['paths'][p][m].get('operationId') for m in ('get', 'post')]
    assert len(set(ids)) == 2, f"{p} duplicate operationIds"
PYEOF
check "explicit route 402 without params (paywall before validation)" 402 "$BASE/v1/weather-now"
check "explicit echo 402 with params" 402 "$BASE/v1/echo?message=hi"
check "explicit crypto-price POST 402" 402 -X POST "$BASE/v1/crypto-price"
check "template route still serves (unknown wrapper -> 404)" 404 "$BASE/v1/nope"
check "free /health still serves (hidden from schema only)" 200 "$BASE/health"

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

echo "--- agent-card + x402/catalog discovery (Strale surface mirror) ---"
check "agent-card.json -> 200" 200 "$BASE/.well-known/agent-card.json"
grep -q '"protocol": *"x402 v2"' /tmp/wrap_test.json && grep -q '"envelope_support": *true' /tmp/wrap_test.json && grep -q 'eip155:8453' /tmp/wrap_test.json && echo "PASS: agent-card content (protocol, envelopes, CAIP-2)" && pass=$((pass+1)) || { echo "FAIL: agent-card content"; fail=$((fail+1)); }
grep -q 'weather-now' /tmp/wrap_test.json && grep -q 'crypto-price' /tmp/wrap_test.json && grep -q 'echo' /tmp/wrap_test.json && echo "PASS: agent-card lists all 3 capabilities" && pass=$((pass+1)) || { echo "FAIL: agent-card capabilities"; fail=$((fail+1)); }
check "x402/catalog -> 200" 200 "$BASE/x402/catalog"
grep -q '"endpoints"' /tmp/wrap_test.json && grep -q 'weather-now' /tmp/wrap_test.json && grep -q '"x402Version"' /tmp/wrap_test.json && echo "PASS: x402/catalog content" && pass=$((pass+1)) || { echo "FAIL: x402/catalog content"; fail=$((fail+1)); }

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

echo "--- holder roster (public copy-holder set) ---"
check "holder roster -> 200" 200 "$BASE/v1/holder-roster"
$PY - <<'PYEOF' && echo "PASS: roster shows announced holder #1 (clawdsmith)" && pass=$((pass+1)) || { echo "FAIL: announced roster content"; fail=$((fail+1)); }
import json, re
d = json.load(open('/tmp/wrap_test.json'))
assert d['format'] == 'x402wrapper-holder-roster', d.get('format')
assert d['holders_count'] == 1, d['holders_count']
h = d['holders'][0]
assert h['handle'] == 'clawdsmith' and h['status'] == 'announced', h
assert h['first_pull_head_hash'] is None and h['last_tip_hash'] is None, 'announced record must not fake a pull'
assert re.fullmatch(r'[0-9a-f]{64}', d['roster_digest_sha256']), 'bad digest'
assert d['announced_count'] == 1 and d['holding_count'] == 0, 'counts'
assert 'how_to_verify' in d and 'honesty' in d, 'docs'
print('PASS')
PYEOF
export DIGEST1=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['roster_digest_sha256'])")
check "register with fake head_hash -> 422" 422 -X POST -H 'Content-Type: application/json' \
  -d '{"handle":"roster-ci","head_hash":"ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00"}' "$BASE/v1/holder-roster"
check "register missing handle -> 422" 422 -X POST -H 'Content-Type: application/json' \
  -d '{"head_hash":"ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00ff00"}' "$BASE/v1/holder-roster"
curl -s "$BASE/v1/challenge-log" -o /tmp/wrap_test.json
HEAD2=$($PY -c "import json; rows=json.load(open('/tmp/wrap_test.json'))['challenges']; print([r['entry_hash'] for r in rows if r['id']==2][0])")
check "register holder -> 201" 201 -X POST -H 'Content-Type: application/json' \
  -d "{\"handle\":\"roster-ci\",\"head_hash\":\"$HEAD2\",\"evidence_url\":\"https://example.com/tip\",\"note\":\"ci test pull\"}" "$BASE/v1/holder-roster"
$PY - <<'PYEOF' && echo "PASS: registration stored w/ checkpoint ref" && pass=$((pass+1)) || { echo "FAIL: registration record"; fail=$((fail+1)); }
import json, re
d = json.load(open('/tmp/wrap_test.json'))
h, ref = d['holder'], d['checkpoint_ref']
assert h['handle'] == 'roster-ci' and h['status'] == 'holding', h
assert h['first_pull_height'] == 2 and h['last_tip_height'] == 2, h
assert h['last_tip_hash'] == h['first_pull_head_hash'], 'tip hashes'
assert h['evidence_url'] == 'https://example.com/tip', 'evidence'
assert ref['entry_id'] == 3 and re.fullmatch(r'[0-9a-f]{64}', ref['entry_hash']), ref
print('PASS')
PYEOF
check "roster lists 2 holders, digest changed" 200 "$BASE/v1/holder-roster"
$PY - <<'PYEOF' && echo "PASS: roster set grew, digest rotated" && pass=$((pass+1)) || { echo "FAIL: roster after registration"; fail=$((fail+1)); }
import json, os
d = json.load(open('/tmp/wrap_test.json'))
assert d['holders_count'] == 2, d['holders_count']
assert d['announced_count'] == 1 and d['holding_count'] == 1, 'counts'
assert d['roster_digest_sha256'] != os.environ['DIGEST1'], 'digest must change with the set'
holding = [h for h in d['holders'] if h['status'] == 'holding'][0]
assert holding['checkpoint_refs'] and holding['checkpoint_refs'][0]['entry_id'] == 3, 'checkpoint refs'
print('PASS')
PYEOF
# clawdsmith's last-pull-age proposal: ages computed server-side from logged pull events.
$PY - <<'PYEOF' && echo "PASS: age fields present, server-side deltas" && pass=$((pass+1)) || { echo "FAIL: age fields"; fail=$((fail+1)); }
import json, time
d = json.load(open('/tmp/wrap_test.json'))
now = int(time.time())
ann = [h for h in d['holders'] if h['status'] == 'announced'][0]
assert abs(ann['announced_age_seconds'] - (now - 1790216111)) <= 1, 'announced age must be server-computed delta'
hold = [h for h in d['holders'] if h['status'] == 'holding'][0]
assert hold['last_updated_unix'] <= now, 'server-side pull time'
assert 0 <= hold['last_pull_age_seconds'] <= now - hold['last_updated_unix'] + 1, 'age must be the server-computed delta'
assert 'last_pull_age_seconds' in d['how_to_verify'], 'verify docs must describe the age field'
print('PASS')
PYEOF
# Age fields must be EXCLUDED from the digest: it covers the committed set only.
export DIGEST2=$($PY -c "import json; print(json.load(open('/tmp/wrap_test.json'))['roster_digest_sha256'])")
sleep 2
check "roster still 200 (digest-stability check)" 200 "$BASE/v1/holder-roster"
$PY - <<'PYEOF' && echo "PASS: digest stable across requests despite ticking ages" && pass=$((pass+1)) || { echo "FAIL: digest stability"; fail=$((fail+1)); }
import json, os, time
d = json.load(open('/tmp/wrap_test.json'))
now = int(time.time())
assert d['roster_digest_sha256'] == os.environ['DIGEST2'], 'digest must not rotate while the SET is unchanged'
hold = [h for h in d['holders'] if h['status'] == 'holding'][0]
assert hold['last_pull_age_seconds'] >= 2, 'ages tick while digest stays put'
print('PASS')
PYEOF
# Re-register with a newer head hash: first_pull stays, last_tip moves.
check "submit third challenge -> 201" 201 -X POST -H 'Content-Type: application/json' -d '{"challenged_by":"harness-ci v1","challenge_type":"identical-loop-harness","result":"pass","details":"run 3"}' "$BASE/v1/challenge-log"
curl -s "$BASE/v1/challenge-log" -o /tmp/wrap_test.json
HEAD4=$($PY -c "import json; rows=json.load(open('/tmp/wrap_test.json'))['challenges']; print([r['entry_hash'] for r in rows if r['id']==4][0])")
check "tip update -> 201" 201 -X POST -H 'Content-Type: application/json' \
  -d "{\"handle\":\"roster-ci\",\"head_hash\":\"$HEAD4\"}" "$BASE/v1/holder-roster"
$PY - <<'PYEOF' && echo "PASS: tip update keeps first-pull anchor" && pass=$((pass+1)) || { echo "FAIL: tip update"; fail=$((fail+1)); }
import json
h = json.load(open('/tmp/wrap_test.json'))['holder']
assert h['first_pull_height'] == 2, 'first-pull anchor must not move'
assert h['last_tip_height'] == 4, h
assert h['last_tip_hash'] != h['first_pull_head_hash'], 'tip must move'
print('PASS')
PYEOF
# Roster registrations must NOT reset the freshness beacon.
check "freshness ignores roster registrations" 200 "$BASE/v1/freshness"
grep -q '"challenged_by":"harness-ci v1"' /tmp/wrap_test.json && grep -q '"last_result":"pass"' /tmp/wrap_test.json && echo "PASS: beacon still shows latest independent challenge" && pass=$((pass+1)) || { echo "FAIL: beacon after roster activity"; fail=$((fail+1)); }
grep -q '"holder_registrations_recorded": *2' /tmp/wrap_test.json && grep -q '"challenges_recorded": *3' /tmp/wrap_test.json && echo "PASS: beacon counts challenges vs registrations separately" && pass=$((pass+1)) || { echo "FAIL: beacon counts"; fail=$((fail+1)); }
# Registration entry is visible in the public log, chain intact.
check "challenge log carries registration entries" 200 "$BASE/v1/challenge-log"
$PY - <<'PYEOF' && echo "PASS: roster commits visible in hash-chained log" && pass=$((pass+1)) || { echo "FAIL: log registration entries"; fail=$((fail+1)); }
import json, hashlib
rows = json.load(open('/tmp/wrap_test.json'))['challenges']
regs = [r for r in rows if r.get('challenge_type') == 'copy-holder-registration']
assert len(regs) == 2, len(regs)
for r in rows:
    body = {k: v for k, v in r.items() if k != 'entry_hash'}
    assert hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == r['entry_hash'], 'chain break'
print('PASS')
PYEOF

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
grep -q '"funded_rail": *"base-usdc"' /tmp/wrap_test.json && echo "PASS: statement publishes funded_rail" && pass=$((pass+1)) || { echo "FAIL: statement funded_rail"; fail=$((fail+1)); }
# Credit-observability rule (2026-09-24, jarviscooper's buyer-side feedback):
# every credit is an observable row with on-chain provenance, exposed on the
# public statement so a principal reconciles against Base directly.
grep -q '"credit_history"' /tmp/wrap_test.json && echo "PASS: statement exposes credit_history" && pass=$((pass+1)) || { echo "FAIL: statement credit_history"; fail=$((fail+1)); }
$PY - <<'PYEOF'
import json
d = json.load(open('/tmp/wrap_test.json'))
hist = d['credit_history']
assert isinstance(hist, list) and len(hist) >= 1, 'credit_history must list initial credit'
c = hist[0]
assert c['amount_atomic'] > 0, 'credit amount must be > 0'
assert 'amount_usdc' in c and 'ts' in c and 'rail' in c and 'credited_by' in c and 'verification' in c, 'credit row missing provenance fields'
assert 'tx_hash' in c, 'credit row missing tx_hash'
print('PASS: credit row carries full on-chain provenance')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: credit provenance"; fail=$((fail+1)); }
grep -q '"settled_rail": *"base-usdc"' /tmp/wrap_test.json && grep -q '"buyer_rail": *"base-usdc"' /tmp/wrap_test.json && echo "PASS: receipt lines carry settled_rail + buyer_rail" && pass=$((pass+1)) || { echo "FAIL: receipt rail fields"; fail=$((fail+1)); }
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
check "statement after topup -> 200" 200 "$BASE/v1/envelopes/$ENV_DUST"
$PY - <<'PYEOF'
import json
d = json.load(open('/tmp/wrap_test.json'))
hist = d['credit_history']
assert len(hist) == 2, f'expect 2 credit rows (initial + topup), got {len(hist)}'
top = hist[-1]
assert top['tx_hash'] == '0xmanualverification', 'topup tx hash must be observable'
assert top['amount_atomic'] == 1000, 'topup amount must be 1000 atomic'
assert 'basescan.org/tx/0xmanualverification' in top['verification'], 'verification must link to chain'
recs = d['receipts']
assert any(r.get('type') == 'credit' for r in recs), 'credit must also appear in receipt lines'
print('PASS: topup appended observable credit row (history + receipts)')
PYEOF
[ "$?" -eq 0 ] && pass=$((pass+1)) || { echo "FAIL: topup credit observability"; fail=$((fail+1)); }
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
