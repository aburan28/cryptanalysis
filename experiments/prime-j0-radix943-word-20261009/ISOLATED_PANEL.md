# Isolated radix-943 word-recoder comparison

The opt-in comparison holds the radix-943 atlas, all thirteen point tables,
fixture scalars, expected points, point formulas, and binary constant while
changing the online coefficient recoder. The frozen panel uses fixture
indices `0,16,32,48,64,80,96,112,128`, five repetitions per index, and
the isolated runner's alternating reference/candidate order. Its internal
timer includes scalar reduction, lattice selection, recoding, lookup, unit
actions, additions, final affine conversion, and the expected-point check.
Table construction and process launch remain separate preparation costs.

On a physical Linux host satisfying
[the service preflight](../../docs/ISOLATED_BENCHMARKS.md), rebuild from one
immutable source snapshot and run the source-bound checker before manifest
generation. Use that host's actual exclusive CPU partition, logical
execution CPU, and NUMA node in place of the example resource values below.

```sh
cd /workspace/cryptanalysis
CARGO_TARGET_DIR=/workspace/build/radix943-word cargo build --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
python3 experiments/prime-j0-radix943-word-20261009/verify_candidate.py \
  --binary /workspace/build/radix943-word/release/eisenstein_fixed \
  --target-dir /workspace/build/radix943-word
python3 experiments/prime-j0-radix943-word-20261009/make_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/radix943-word/release/eisenstein_fixed \
  --checker-receipt /workspace/cryptanalysis/experiments/prime-j0-radix943-word-20261009/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/radix943-word-panel.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/radix943-word-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/radix943-word-panel.json
```

Submit only when the strict probe passes. Preserve every pair and raw failure;
promote an online wall-time ratio only when all correctness and noise gates
pass. The current RunPod CPU Pod has Docker/cgroup-v1 host evidence and fails
this preflight, so its diagnostic timings do not answer this comparison.
