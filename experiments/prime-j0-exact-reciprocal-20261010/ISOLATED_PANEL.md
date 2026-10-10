# Exact reciprocal selector versus divided U14 selector

The primary panel pairs the original signed-word U14 evaluator with the
exact reciprocal selector in the same release executable. Both use the
same fourteen window widths, residue atlas, 78,470,208-byte point table,
unit actions, and point formulas. Nine fixture indices
`0,16,32,48,64,80,96,112,128` run five times each in alternating order.

The executable's online timer starts after fixture loading, scalar
decoding, reciprocal verification, and reusable table preparation. It
charges scalar reduction, either the two BigInt divisions or two
fixed-limb reciprocal products, four-corner scoring, signed-word
recoding, table lookup, unit action, mixed additions, affine conversion,
and expected-point assertion.

On a physical Linux host that passes
[the isolation gate](../../docs/ISOLATED_BENCHMARKS.md), rebuild from
the frozen snapshot, run the full native suite, and verify that host's
binary. Use the host's measured CPU and NUMA resources in place of the
example values:

```sh
cd /workspace/cryptanalysis
export CARGO_TARGET_DIR=/workspace/build/exact-reciprocal
cargo test --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed -- --test-threads=2 \
  > experiments/prime-j0-exact-reciprocal-20261010/native-tests.log 2>&1
printf '%s\n' "$?" \
  > experiments/prime-j0-exact-reciprocal-20261010/native-tests.exit
cargo build --offline --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml \
  --bin eisenstein_fixed
python3 experiments/prime-j0-exact-reciprocal-20261010/verify_candidate.py \
  --binary /workspace/build/exact-reciprocal/release/eisenstein_fixed \
  --native-test-log experiments/prime-j0-exact-reciprocal-20261010/native-tests.log \
  --native-test-exit experiments/prime-j0-exact-reciprocal-20261010/native-tests.exit
python3 experiments/prime-j0-exact-reciprocal-20261010/make_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --binary /workspace/build/exact-reciprocal/release/eisenstein_fixed \
  --checker-receipt /workspace/cryptanalysis/experiments/prime-j0-exact-reciprocal-20261010/verification.json \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-node 0 \
  --output /workspace/isolated-bench/exact-reciprocal-panel.json
python3 scripts/isolated_bench.py probe \
  /workspace/isolated-bench/exact-reciprocal-panel.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit \
  /workspace/isolated-bench/exact-reciprocal-panel.json
```

Submit only after the strict probe passes. Retain all failed and noisy
pairs. The reachable RunPod CPU Pod remains a correctness host because
its container allocation lacks the host-wide CPU isolation state.
