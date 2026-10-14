# Three-bucket unit-orbit evaluator for the norm-4,831 radix

The three-bucket evaluator retains **1,425,154 bytes** while computing the
same 20-step fixed-base secp256k1 multiplication as the direct two-x format.
It stores one 64-byte affine point for each of 806 canonical seeds at each
step. The direct two-x format stores 96 bytes per entry, so the digit payload
falls from 1,547,520 to 1,031,680 bytes and the complete retained table falls
by 515,840 bytes (26.6%).

For a nonzero digit with unit code `u = 2j + sign`, add its plain affine table
point with the selected sign to bucket `B_j`. After all 20 digits, compute
`B_0 + omega(B_1) + omega²(B_2)`, then add the same fused terminal point.
On this j=0 curve the order-three `omega` action multiplies the projective
`x` coordinate by a cube root of unity and leaves `y` and the scale
coordinates fixed. This moves the unit action from every selected digit to
at most two aggregate points. It requires up to two projective bucket joins.
For a scalar with 20 nonzero digits, all three buckets occupied, and a
nonzero terminal, the path performs 18 mixed additions and two projective
joins; the direct two-x path performs 20 mixed additions. The changed memory
traffic and operation mix require an isolated paired timing experiment.

[SplitPrime4831Buckets.lean](SplitPrime4831Buckets.lean) proves the
coefficient identity for arbitrary lists in all three unit classes. The
proof uses only additivity of the explicit `omegaMul` map; the concrete
curve bridge is checked by the native unit-image and scalar tests. Lean
4.34.1 reports `propext` and `Quot.sound` as the theorem's axioms.

[three_bucket_overlay.py](three_bucket_overlay.py) builds on the norm-4,831
generator and changes the digit row type, unit selection, bucket aggregation,
and retained-memory accounting. The [validation receipt](validation.json)
pins source and binary hashes and the raw [native](native-test.log) and
[Lean](lean-check.log) logs. The release native evaluator passed five test
families: all 4,831 residue codes and 43,479 quotient cases; all 96,720
unit images; all 5,680 terminal indices; the frozen 128-scalar fixture; and
518 additional deterministic or boundary scalars against independent binary
multiplication. These are correctness and memory results. CPU timing is open.
The benchmark entry point now emits separate counts for nontrivial mixed
additions, projective joins, bucket `x`-constant multiplications, affine
point reads, and sign flips after its verification step. On frozen fixture
case 0 it reports 18 mixed additions, two projective joins, two bucket
`x` multiplications, 20 digit reads, one terminal read, and 12 sign flips.
This local execution is an operation-profile check; its wall time is not a
controlled CPU measurement.

Reproduce from the repository root, using a checkout with the referenced
atlas inputs available:

```sh
python3 experiments/prime-j0-three-bucket-20261014/three_bucket_overlay.py /private/tmp/prime-j0-three-bucket-replay
CARGO_TARGET_DIR=/private/tmp/prime-j0-three-bucket-replay-target cargo test --manifest-path /private/tmp/prime-j0-three-bucket-replay/Cargo.toml --offline --locked --release --bin eisenstein_fixed split_prime_ -- --test-threads=1 --nocapture
LEAN_PATH=/private/tmp/lean-split-prime /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean experiments/prime-j0-three-bucket-20261014/SplitPrime4831Buckets.lean
```

The recorded sparse-worktree build used 31 temporary include shims. Their
manifest hash and both the generated source hash and the compiled source
hash are in the receipt; the shims affect unrelated atlas inputs, not the
norm-4,831 evaluator. For performance, pair this candidate against the
direct two-x evaluator on the same frozen scalar panel, with an A/A control
and the Tier 0 or Tier 1 receipts required by
[the benchmark tier contract](../../docs/IC_BENCHMARK_TIERS.md).
