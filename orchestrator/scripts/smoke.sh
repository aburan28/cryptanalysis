#!/usr/bin/env bash
# One control plane, two agents, one small instance, one real answer.
#
# This is the closest thing to a deployment that fits in a test: the same
# binaries, started the same way, talking over a real socket.  Everything the
# Go tests exercise in-process is exercised here as separate processes, which
# is where the interesting failures live -- a flag that does not exist, a
# token that is not read, a signal that is not handled.
#
#   orchestrator/scripts/smoke.sh [build-dir]
set -euo pipefail

root=$(cd "$(dirname "$0")/../.." && pwd)
build=${1:-$root/build}
work=${CA_SMOKE_DIR:-/tmp/ca-smoke}
token="smoke-$$"

ca=$build/ca
control=$build/ca-control
agent=$build/ca-agent

for bin in "$ca" "$control" "$agent"; do
    [ -x "$bin" ] || { echo "missing $bin; build it first" >&2; exit 1; }
done

rm -rf "$work"
mkdir -p "$work"
pids=()
cleanup() {
    for pid in "${pids[@]:-}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
}
trap cleanup EXIT

# A small instance with a known answer.  The answer is kept here and never
# given to the fleet: the point of the exercise is that the fleet finds it.
instance=$("$ca" gen --group zp --p 2000000579 --order 1000000289 --seed 42)
g=$(echo "$instance" | sed 's/.*"g":"\([0-9]*\)".*/\1/')
h=$(echo "$instance" | sed 's/.*"h":"\([0-9]*\)".*/\1/')
want=$(echo "$instance" | sed 's/.*"x":\([0-9]*\).*/\1/')
echo "instance: g=$g h=$h (the answer is $want, and nothing below is told it)"

port=${CA_SMOKE_PORT:-18080}
CA_TOKEN=$token "$control" serve \
    --listen "127.0.0.1:$port" --state "$work/state" --log-level warn \
    >"$work/control.log" 2>&1 &
pids+=($!)

for _ in $(seq 50); do
    if curl -fsS "http://127.0.0.1:$port/healthz" >/dev/null 2>&1; then break; fi
    sleep 0.2
done
curl -fsS "http://127.0.0.1:$port/healthz" >/dev/null

CA_TOKEN=$token "$control" create \
    --server "http://127.0.0.1:$port" --name smoke --group zp \
    --p 2000000579 --order 1000000289 --g "$g" --h "$h" \
    --dp-bits 6 --unit-steps 2000 --unit-walks 16 >"$work/campaign.json"
echo "campaign: $(tr -d '\n' <"$work/campaign.json" | head -c 200)"

for i in 0 1; do
    CA_TOKEN=$token "$agent" \
        --server "http://127.0.0.1:$port" --ca "$ca" --id "smoke-$i" \
        --health-listen "" --log-level warn --idle-backoff 200ms \
        >"$work/agent-$i.log" 2>&1 &
    pids+=($!)
done

solved=""
for _ in $(seq 120); do
    status=$(curl -fsS -H "Authorization: Bearer $token" \
        "http://127.0.0.1:$port/v1/status" || true)
    if echo "$status" | grep -q '"solved": true'; then
        solved=$(echo "$status" | sed -n 's/.*"x": \([0-9]*\).*/\1/p' | head -1)
        break
    fi
    sleep 0.5
done

if [ -z "$solved" ]; then
    echo "the fleet did not solve the instance in time" >&2
    curl -fsS -H "Authorization: Bearer $token" "http://127.0.0.1:$port/v1/status" >&2 || true
    exit 1
fi
if [ "$solved" != "$want" ]; then
    echo "the fleet reported x=$solved, the planted value was $want" >&2
    exit 1
fi

# An unauthenticated request must be refused: the token is the only thing
# between the corpus and anyone who can reach the port.
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/v1/status")
if [ "$code" != "401" ]; then
    echo "an unauthenticated status request returned $code, expected 401" >&2
    exit 1
fi

# And the metrics a dashboard would scrape are there.
curl -fsS -H "Authorization: Bearer $token" "http://127.0.0.1:$port/metrics" \
    | grep -q ca_campaign_solved

echo "smoke: solved x=$solved (matches the planted value)"
