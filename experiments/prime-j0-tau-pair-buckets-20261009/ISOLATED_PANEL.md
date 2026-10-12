# Isolated U14 versus two-bucket tau fixed-base comparison

The panel holds secp256k1, its fixed generator, the 129-case point fixture,
the native field arithmetic, and the binary constant. It compares the U14
unit-orbit reference with the thirteen-window radix-1021 two-bucket atlas.
Both modes are in one release executable. The frozen subset uses fixture
indices `0,16,32,48,64,80,96,112,128`, five repetitions per index, and
the serial runner's alternating reference/candidate order.

The executable's online timer includes scalar reduction, lattice selection,
signed-limb recoding, atlas lookup, unit actions, bucket mixed additions,
the tau map, projective bucket merge, affine conversion,
and the expected-point assertion. Table construction and process launch are
separate preparation costs. The paired manifest retains source, atlas,
binary, fixture, and correctness-replay hashes.

On a physical Linux host passing [the strict service preflight](../../docs/ISOLATED_BENCHMARKS.md),
rebuild from one immutable source snapshot and run its checker. Replace the
example CPU, NUMA, and cgroup values with that host's verified isolated
partition before submitting.

```sh
cd /workspace/cryptanalysis
CARGO_TARGET_DIR=/workspace/build/tau-pair cargo build --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
python3 experiments/prime-j0-tau-pair-buckets-20261009/verify_candidate.py \
  --binary /workspace/build/tau-pair/release/eisenstein_fixed \
  --target-dir /workspace/build/tau-pair
python3 experiments/prime-j0-tau-pair-buckets-20261009/make_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/tau-pair/release/eisenstein_fixed \
  --checker-receipt /workspace/cryptanalysis/experiments/prime-j0-tau-pair-buckets-20261009/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/tau-pair-panel.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/tau-pair-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/tau-pair-panel.json
```

Submit only after `probe` passes. Preserve all failed and noisy pairs; use
the complete verified online interval for the ratio. The reachable RunPod
CPU Pod currently has Docker/cgroup-v1 host evidence and no reserved
`nohz_full` CPUs, so it does not qualify for this panel's controlled timing.
