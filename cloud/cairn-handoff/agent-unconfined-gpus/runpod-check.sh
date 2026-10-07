#!/usr/bin/env bash
# Run on a Runpod GPU pod: cairn 1.17.0 against this branch's agent
# (/root/cairn-pr) on GPU visibility and unconfined GPU jobs.
set -uo pipefail
cd /root
ver=1.17.0
t=cairn-v$ver-x86_64-unknown-linux-musl.tar.gz
curl -fsSLO "https://github.com/aburan28/cairn/releases/download/v$ver/$t"
curl -fsSLO "https://github.com/aburan28/cairn/releases/download/v$ver/$t.sha256"
sha256sum -c "$t.sha256" && tar -xzf "$t" && install -m 755 cairn /usr/local/bin/cairn

echo "== nvidia-smi (what this pod was given)"
nvidia-smi --query-gpu=pci.bus_id,name,memory.total --format=csv,noheader
echo "== cairn 1.17.0 probe"
cairn agent probe | sed -n '1,12p'
echo "== branch probe"
/root/cairn-pr agent probe | sed -n '1,12p'

(CAIRN_DATA=/root/node CAIRN_SEEDS=off CAIRN_BEACON_PORT=off CAIRN_PORTMAP=off \
  cairn run --no-mcp --listen 127.0.0.1:9000 --serve 127.0.0.1:8080 >/root/node.log 2>&1 &)
for _ in $(seq 60); do curl -fs -o /dev/null http://127.0.0.1:8080/hosts && break; sleep 1; done

echo "== cairn 1.17.0: a GPU job under none"
cairn agent exec --rootfs / --sandbox none --gpus 1 --id release --data-dir /root/agent-release \
  --json -- nvidia-smi -L
echo "exit $?"
echo "== branch, without --unconfined-gpus"
/root/cairn-pr agent exec --rootfs / --sandbox none --gpus 1 --id without --data-dir /root/agent \
  --json -- nvidia-smi -L
echo "exit $?"
echo "== branch, --unconfined-gpus on a host that jails its jobs"
/root/cairn-pr agent exec --rootfs / --gpus 1 --unconfined-gpus --id jailed --data-dir /root/agent \
  -- nvidia-smi -L
echo "exit $?"
echo "== branch, a queued GPU job with --unconfined-gpus, registered with the node"
cat >/root/gpu.json <<'JSON'
{"id":"gpu-job","rootfs":"/","argv":["nvidia-smi","-L"],"sandbox":"none","gpus":1,"timeout_seconds":60}
JSON
/root/cairn-pr agent submit /root/gpu.json --data-dir /root/agent
/root/cairn-pr agent run --node http://127.0.0.1:8080 --name runpod-check --sandbox none \
  --unconfined-gpus --once --data-dir /root/agent
echo "exit $?"
echo "-- receipt"
cat /root/agent/jobs/done/gpu-job/receipt.json
echo
echo "-- stdout"
cat /root/agent/jobs/done/gpu-job/stdout
echo "-- the node's roster"
curl -fsS http://127.0.0.1:8080/hosts | python3 -c '
import json, sys
host = json.load(sys.stdin)["hosts"][0]
print(json.dumps({"host": host["host"], "jobs": host["jobs"],
                  "gpus": [[g["vendor"], g.get("model"), g.get("bus")] for g in host["hardware"]["gpus"]]},
                 indent=1))'
