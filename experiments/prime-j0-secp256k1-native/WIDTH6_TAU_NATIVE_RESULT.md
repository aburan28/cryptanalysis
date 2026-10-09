# Native width-six tau scalar path

The native fixed-generator `tau^6` path reproduces the frozen 214-scalar
atlas: all output points agree with an independent affine secp256k1
reference, and its 81-orbit recoding matches every saved step and addition
count. The table builder reaches all 81 seed points through a connected
unit-difference graph using 80 mixed point additions, then normalizes them
with one batched inversion. It obtains the other signed unit images through
the curve automorphism and point negation.

The digit construction and termination bound are in
[`WIDTH6_TAU_RESULT.md`](WIDTH6_TAU_RESULT.md). Each nonzero residue class
modulo `tau^6 = -27` selects one of 486 digits. The table stores 81 signed
unit orbits. The native mode `--scalar-w6-fixed` uses the same frozen atlas;
`--check-scalar-w6-fixed-case FIXTURE INDEX` checks one fixture point, and
`--benchmark-scalar-w6-fixed-case FIXTURE INDEX` provides a target-specific
timing entrypoint after the table is prepared.

## Verification

| Frozen panel | Scalars | Tau steps | Mixed additions | Source field-product proxy |
| --- | ---: | ---: | ---: | ---: |
| Edge cases | 22 | 886 | 128 | 5,838 |
| Random design | 64 | 10,116 | 1,546 | 67,586 |
| Random holdout | 128 | 20,243 | 3,107 | 135,392 |

The verifier checks the scalar representative modulo the subgroup order,
all 81 orbit counters, the saved operation counts, and each affine output
against `lazy_tau_screen.point_multiply`. Release tests: **39 passed**,
including independent seed-point comparison for all 81 orbits. The fixture
entrypoint independently verified case 85 of `eisenstein-pair-fixture.json`.

```sh
cd experiments/prime-j0-secp256k1-native
cargo test --release --bin eisenstein_fixed
cargo build --release --bin eisenstein_fixed
PYTHONDONTWRITEBYTECODE=1 python3 check_width6_tau_native.py
target/release/eisenstein_fixed --check-scalar-w6-fixed-case \
  eisenstein-pair-fixture.json 85
```

The release binary SHA-256 is
`2fd4c74857b0ca4302785f14a4fbe9c665f15812cd877fca7501399b073cea7c`.
The native source SHA-256 is
`b3b2a654c06140d10d79b0f164ca3402c84f3705c164ee3f43d95444b2e80250`,
the verifier SHA-256 is
`f7579f85b42cb26166141c1fc61568cefb3263cf89c642a22c641b062856ffb8`,
and the frozen atlas JSON SHA-256 is
`7f81556cd0a4f72e6504894ebac8bf591616f200a37778f2b63cc4e899d9e58c`.

The source field-product proxy charges five units per tau step and eleven
per mixed addition. The table has substantial startup work and memory;
the proxy excludes table preparation, integer recoding, lookup, memory
traffic, and affine output conversion. A complete CPU comparison needs
paired full-operation runs and a passing host-isolation receipt under
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md). The
currently reachable RunPod container has a live serial runner, but its
strict preflight rejects host-wide isolation, so no wall-time speedup is
promoted from it.
