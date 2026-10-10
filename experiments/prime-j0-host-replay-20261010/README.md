# Linux host replay for the U14 four-limb point backend

This workflow makes a fresh correctness and resource receipt from a Linux
host's own release binary. It uses the frozen 129-case secp256k1 fixture and
checks both modes against every expected point before producing a paired
manifest. The original macOS receipt remains bound to its original binary.

On the Linux host with the source tree at its final path, run:

```sh
python3 experiments/prime-j0-host-replay-20261010/host_replay.py verify \
  --output-dir /absolute/path/to/host-replay-result
python3 experiments/prime-j0-host-replay-20261010/host_replay.py manifest \
  --receipt /absolute/path/to/host-replay-result/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /absolute/path/to/paired-manifest.json
python3 scripts/isolated_bench.py probe /absolute/path/to/paired-manifest.json
```

The CPU and NUMA values above are examples. Use the actual host's verified
isolated partition. `verify` requires GNU `/usr/bin/time -v`, Rust/Cargo, and
the native release build dependencies. It creates a new output directory,
records the release test/build logs, all fixture outputs, one process-level
resource run per mode, source hashes, and the local binary hash. It never
reads the archived macOS resource files. A failed build or check leaves raw
files for diagnosis and produces no passing receipt.

The manifest command rejects changed source, binary, or raw host outputs.
Submit it to the serial [isolated benchmark service](../../docs/ISOLATED_BENCHMARKS.md)
only after its strict preflight passes. CPU speedup is determined by that
service's paired verified results and noise gates, not by the two preparatory
resource runs. The existing RunPod container fails the strict isolation gate;
its queued correctness job remains a separate physical x86 check.
