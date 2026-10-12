# Isolated online panel for canonical-sector U14 digits

The Linux host replay pairs mode 129's four-corner nearest-digit rule
with mode 130's piecewise canonical-sector rule. Both retain the same
fourteen four-limb affine point windows and use the same scalar
representative and grouped accumulator gauge. The frozen fixture case
indices are `0,16,32,48,64,80,96,112,128`, with five paired
repetitions by default.

Build and verify the exact source on a qualifying isolated Linux host:

```sh
python3 experiments/prime-j0-host-replay-20261010/host_replay.py verify \
  --comparison sector --output-dir /absolute/path/to/sector-host-replay
python3 experiments/prime-j0-host-replay-20261010/host_replay.py manifest \
  --receipt /absolute/path/to/sector-host-replay/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/sector-paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/sector-paired-manifest.json
```

Replace example CPUs, NUMA node, and cgroup with the audited exclusive
host partition. The replay requires 87 passing native release tests,
both 129-case fixture arms, source and executable hashes, raw outputs,
and 64,314,112 retained table bytes in both modes. Interpret an online
wall-time ratio only after the service's host preflight, paired
correctness checks, and noise gates pass. The serialized RunPod
container checks remote Linux correctness; it does not establish
host-wide CPU isolation.
