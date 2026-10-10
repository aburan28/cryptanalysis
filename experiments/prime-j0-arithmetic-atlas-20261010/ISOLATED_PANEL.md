# Isolated online panel for the arithmetic U14 orbit index

The Linux host replay pairs mode 127's stored residue-code atlas with
mode 128's arithmetic orbit rank. Both modes use the same U14 affine
point table, four-limb field backend, scalar representative, and grouped
accumulator gauge. The primary nine fixture cases have indices
`0,16,32,48,64,80,96,112,128`; the default is five paired repetitions.

Build and verify this branch on a qualifying isolated Linux host:

```sh
python3 experiments/prime-j0-host-replay-20261010/host_replay.py verify \
  --comparison arithmetic --output-dir /absolute/path/to/arithmetic-host-replay
python3 experiments/prime-j0-host-replay-20261010/host_replay.py manifest \
  --receipt /absolute/path/to/arithmetic-host-replay/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/arithmetic-paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/arithmetic-paired-manifest.json
```

Replace the example CPU, NUMA, and cgroup values with that host's
audited exclusive partition. The replay requires 83 passing native
release tests, both 129-case fixture arms, local executable and source
hashes, raw process outputs, and retained table sizes of 70,430,960 and
65,188,008 bytes. The service's strict host preflight, paired result
checks, and noise gates determine whether an online wall-time ratio is
interpretable. The shared RunPod container is available for physical
x86 correctness checks through the serial runner; its container-level
affinity does not satisfy the host isolation gate.
