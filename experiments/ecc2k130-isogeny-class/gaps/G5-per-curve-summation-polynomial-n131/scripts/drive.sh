#!/bin/bash
# Launch W shards of run_grid.py in parallel; each command is capped at 2400 s.
export TMPDIR=/Volumes/SSD990/ecdlp-hardness-work/tmp
W=${1:-8}
EXTRA="${2:-}"
cd "$(dirname "$0")"
mkdir -p ../logs
for i in $(seq 0 $((W-1))); do
  timeout 2400 sage -python run_grid.py --shard $i --nshards $W --budget ${BUDGET:-1500} $EXTRA >> ../logs/shard_${i}_of_${W}.log 2>&1 &
done
wait
echo "drive done"
