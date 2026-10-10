# Isolated online panel for the point-only U14 table

The Linux host replay pairs mode 128's canonical digit array with mode
129's computed digit. Both modes use the same fourteen four-limb affine
point windows, certified scalar representative, and grouped accumulator
gauge. The nine frozen fixture cases have indices
`0,16,32,48,64,80,96,112,128`; the default is five paired repetitions.

Build and verify the exact branch source on a qualifying isolated Linux
host:

```sh
python3 experiments/prime-j0-host-replay-20261010/host_replay.py verify \
  --comparison formula --output-dir /absolute/path/to/formula-host-replay
python3 experiments/prime-j0-host-replay-20261010/host_replay.py manifest \
  --receipt /absolute/path/to/formula-host-replay/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/formula-paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/formula-paired-manifest.json
```

Replace the example CPU, NUMA, and cgroup values with the audited
exclusive partition. The replay requires 85 passing native release
tests, both 129-case fixture arms, local source and executable hashes,
raw process outputs, and retained table sizes of 65,188,008 and
64,314,112 bytes. The service's host preflight, paired correctness
checks, and noise gates control interpretation of online wall-time
ratios. The serialized RunPod container can check physical x86
correctness; its container affinity does not provide host isolation.
