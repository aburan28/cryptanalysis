# Linux host replay for U14 scalar multiplication comparisons

This workflow makes a fresh correctness and resource receipt from a Linux
host's own release binary. It uses the frozen 129-case secp256k1 fixture and
checks both modes against every expected point before producing a paired
manifest. Select `--comparison point` for direct limbs versus four-limb
points, `--comparison gauge` for four-limb points versus the grouped
accumulator gauge, `--comparison arithmetic` for the stored-code atlas
versus arithmetic orbit indexing, `--comparison formula` for the
digit-array atlas versus a point-only table, or `--comparison sector`
for the four-corner nearest-digit rule versus the piecewise canonical
sector rule. The original macOS receipts remain bound to their own
binaries.

On the Linux host with the source tree at its final path, run:

```sh
python3 experiments/prime-j0-host-replay-20261010/host_replay.py verify \
  --comparison sector --output-dir /absolute/path/to/host-replay-sector-result
python3 experiments/prime-j0-host-replay-20261010/host_replay.py manifest \
  --receipt /absolute/path/to/host-replay-sector-result/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA values above are examples. Use the actual host's verified
isolated partition. `verify` requires GNU `/usr/bin/time -v`, Rust/Cargo, and
the native release build dependencies. Use a fresh directory per comparison.
It creates a new output directory,
records the release test/build logs, all fixture outputs, one process-level
resource run per mode, source hashes, and the local binary hash. It never
reads the archived macOS resource files. A failed build or check leaves raw
files for diagnosis and produces no passing receipt.

The manifest command selects the pair from the receipt and rejects changed
source, binary, or raw host outputs. With the sector branch included,
the release suite must report 87 passing tests. The sector comparison
requires 64,314,112 retained bytes in both modes, and all 129 paired
fixture points must match.
Submit it to the serial [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md)
only after its strict preflight passes. CPU speedup is determined by that
service's paired verified results and noise gates, not by the two preparatory
resource runs. The existing RunPod container fails the strict isolation gate;
its serialized job checks remote Linux correctness separately.
