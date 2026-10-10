# Fused orbit and tau table for fixed-generator secp256k1 multiplication

The fused table removes **8,185 field multiplications** from the point kernel over a fresh 4,096-scalar panel relative to the tau-expanded table. It precomputes both degree-three tau images and their three cube-root x images, then selects each term directly into one accumulator. All 4,096 outputs match independently computed secp256k1 points. The retained table grows by **2,809,472 bytes**.

The nineteen-window recoder expresses its exact Eisenstein representative as

`a + b tau = sum_j 2^h_j u_j tau^e_j d_j`,

where `u_j` is one of six units, `e_j` is zero or one, and `d_j` is a stored seed. This format retains both `P_j = [2^h_j d_j]G` and `tau(P_j)`, with all three cube-root x images for each point. A sign bit negates the selected y coordinate. Each selected image is added to one Jacobian accumulator, so the online point path has no tau map, cube-root rotation, second bucket, or final projective merge.

The point identity follows directly from endomorphism linearity: the selected table entry is `u_j tau^e_j P_j`, and their sum is `[a+b lambda_tau]G = [k]G` in the secp256k1 subgroup. The table construction uses the same nineteen-window atlas and exact recoder as the tau-expanded mode. The cube-root action changes x by a stored multiplier and leaves y fixed; negation changes only y. The full table holds 21,949 slots and retains **5,726,228 bytes** including atlas data and vector storage. Its table entries are 256 bytes each, compared with 128 bytes for the tau-expanded pair.

This is an opt-in public-scalar research path. Table accesses depend on scalar digits. The extra 2,809,472 retained bytes buy direct selection of both endomorphism images and their cube-root orbits. The source-level operation count and isolated wall-time effects are separate measurements; a lower count alone is not a measured speedup.

## Exact point-kernel diagnostic

Both modes use the same post-freeze scalar panel and one source-instrumented binary. Tables are warmed before resetting counters for each scalar and mode.

| Mode | Field adds | Field subs | Field muls | Field squares | Gauge rotations | Retained bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tau-expanded | 73,716 | 481,359 | 597,913 | 221,148 | 8,185 | 2,916,756 |
| Fused orbit-tau | 73,716 | 481,359 | 589,728 | 221,148 | 0 | 5,726,228 |

The counters cover `u256_add`, `u256_sub`, `u256_mul`, and `u256_square` wrappers during point evaluation. They include point addition and gauge rotation, and exclude table construction, scalar recoding outside those wrappers, final inversion, output conversion, and hardware time. [The counter patch](ops-diagnostic.patch), [raw log](ops-diagnostic.log), [hash receipt](ops-diagnostic.json), and [verifier](verify_ops.py) bind this diagnostic to source commit `e9327a6616c2e04ff7e1f4c6c546c58574b55125`.

## Verification

The 108-test release suite checks every one of the 263,160 nonzero `(window, seed, tau exponent, unit)` selections against the established tau-expanded table, then compares 4,096 scalar outputs and 128 independent binary multiplications. After source freeze, `make_inputs.py` draws a disjoint 4,096-scalar panel, `make_fresh_fixture.py` computes independent binary points, and `run_fresh.py` replays both formats. `verify_fresh.py` binds the result to the frozen source, input law, fixture, and complete output streams. The fresh run and operation-count diagnostic are correctness evidence until a host passes the isolated timing preflight.

From a full checkout, build and replay with:

```sh
TMPDIR=/private/tmp CARGO_TARGET_DIR=/private/tmp/prime-j0-orbit-tau-fusion-target cargo test --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml --bin eisenstein_fixed
TMPDIR=/private/tmp CARGO_TARGET_DIR=/private/tmp/prime-j0-orbit-tau-fusion-target cargo build --locked --release \
  --manifest-path experiments/prime-j0-secp256k1-native/Cargo.toml --bin eisenstein_fixed
python3 experiments/prime-j0-orbit-tau-fusion-20261010/verify_fresh.py
python3 experiments/prime-j0-orbit-tau-fusion-20261010/verify_ops.py
```
