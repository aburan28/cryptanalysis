# Isolated U14 versus staged-prefetch scalar comparison

The panel pairs the signed-word U14 reference with the staged-prefetch
candidate in one release executable. Both select the same fourteen
digits and 78,470,208-byte table, perform the same unit actions and
mixed additions, and verify the same output point. The only intended
online difference is the timing of table prefetch hints and point loads.

The frozen panel uses fixture indices `0,16,32,48,64,80,96,112,128`,
five repetitions each, and the serial service's alternating pair order.
The executable timer starts after reusable table preparation and scalar
fixture decoding. It charges scalar reduction, lattice selection,
signed-word recoding, prefetch hints, table loads, unit actions, point
additions, final affine conversion, and expected-point assertion.

On a physical Linux host that passes the strict
[isolation gate](../../docs/ISOLATED_BENCHMARKS.md), rebuild and replay
the candidate from the same immutable source snapshot. Use that host's
actual isolated partition instead of the example resource values:

```sh
cd /workspace/cryptanalysis
CARGO_TARGET_DIR=/workspace/build/staged cargo build --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
python3 experiments/prime-j0-staged-prefetch-20261010/verify_candidate.py \
  --binary /workspace/build/staged/release/eisenstein_fixed \
  --target-dir /workspace/build/staged
python3 experiments/prime-j0-staged-prefetch-20261010/make_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/staged/release/eisenstein_fixed \
  --checker-receipt /workspace/cryptanalysis/experiments/prime-j0-staged-prefetch-20261010/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/staged-u14-panel.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/staged-u14-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/staged-u14-panel.json
```

Submit only after the probe passes. Retain all failed and noisy pairs.
The reachable RunPod CPU Pod remains a correctness host because its
container allocation lacks the required host-wide CPU isolation state.
