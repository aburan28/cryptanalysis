# Unit-orbit online panel: dispatch-ready receipt

The U14/U15/U16 benchmark CLI passed all **129 fixture points per
format** through the exact timed code path, plus one independent
single-case dispatch per format. Its [checker
receipt](unit-orbit-isolated-cli-check.json) binds the release binary,
both Rust source files, fixture, timing protocol, and prior native
correctness receipt by SHA-256. The local timing values were discarded;
this check established output and interval wiring only.

The [frozen protocol](UNIT_ORBIT_ISOLATED_TIMING_PROTOCOL.md) uses nine
public scalars and five AB/BA paired repetitions for each comparison,
U14 versus U15 and U14 versus U16. The [manifest
generator](make_unit_orbit_isolated_manifest.py) produced schema-valid
dry-run manifests with nine cases and five repetitions each. Their
local hashes were `1117c5f586026e2fc3b90743a45c7f8c498ed0a0ba059078366a94223a33a276`
and `4480a55727739eb66f0d765600dc1d84c11d4fdc7ec7831d77f8307075a4eef2`,
respectively. These hashes identify local path-bound dry runs, not
portable host manifests or measurements.

On a qualifying Linux host, build the branch's release binary and run
the checker there to produce a host-specific binary and receipt. Then
generate each manifest using that receipt and the host's verified
isolated cgroup, CPU, and NUMA IDs:

```sh
cd /workspace/cryptanalysis
CARGO_TARGET_DIR=/workspace/build/unit-orbit cargo build --release --locked \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
python3 experiments/prime-j0-secp256k1-native/check_unit_orbit_isolated_cli.py \
  --binary /workspace/build/unit-orbit/release/eisenstein_fixed \
  --output /workspace/isolated-bench/unit-orbit-cli-check.json
python3 experiments/prime-j0-secp256k1-native/make_unit_orbit_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/unit-orbit/release/eisenstein_fixed \
  --checker-receipt /workspace/isolated-bench/unit-orbit-cli-check.json \
  --candidate-format 15 \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/u14-vs-u15.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/u14-vs-u15.json
```

Repeat the manifest-generation and probe commands with format `16`.
The CPU, NUMA, and cgroup values above are examples and must be replaced
with the host's verified isolated partition. Submit each passing
manifest to the existing serial service with its `submit` command;
the service preserves paired order, raw outputs, failures, noise
counters, and binary/source hashes. The current RunPod CPU Pod fails
the strict preflight and remains a correctness host only.
