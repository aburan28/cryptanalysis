# Incremental hexagonal scalar-candidate construction

The hex4 and hex9 selectors now construct one Eisenstein-lattice
representative and derive every neighboring representative and norm by exact
additions. This preserves their candidate order and final secp256k1 points
while reducing the selector's source-level count of large-by-large `BigInt`
products from **30 to 13** for hex4 and from **65 to 13** for hex9. These are
arithmetic counts, not measured CPU speedups. The parent
[hexagonal result](HEX9_COVER_RESULT.md) supplies the lattice geometry and
point-operation proxy; this change improves its candidate construction.

## Exact update

Write `z=a+b*tau`, `W=U-2V`, and use the parent result's identity
`N(W)=N(V)=N(W+V)=n`, with
`N(a+b*tau)=a^2+3ab+3b^2`. For offsets `d_w,d_v` from the first grid point,

`N(z-d_w W-d_v V) = N(z) - d_w 2<z,W> - d_v 2<z,V>
                    + n(d_w^2+d_v^2-d_w d_v)`.

The implementation computes the first point with four large products, its
norm with three, and the two doubled inner products with four. The two
products used to find the grid center are common to both implementations.
Each further point uses vector subtraction and the displayed norm update;
integer offsets are at most two. The direct version used four coordinate
products and three norm products for each point. Sorting retains the same
norm, max-coordinate, and coordinate tie breaks, so the recoding and point
evaluation stages see exactly the same candidate sequence.

| Selector | Direct large products | Incremental large products | Candidate points |
| --- | ---: | ---: | ---: |
| hex4 | `2 + 7*4 = 30` | `2 + 4 + 3 + 4 = 13` | 4 |
| hex9 | `2 + 7*9 = 65` | `2 + 4 + 3 + 4 = 13` | 9 |

Small-integer multiplication, division for the center, sorting, allocations,
recoding, and point arithmetic remain part of the full online timer. Their
effect on wall time is pending a qualifying isolated-host measurement.

## Correctness and paired-run record

The release suite passed **47 tests**. The new test compares every sorted
candidate against the direct formula for 128 deterministic full-width
scalars in each mode. Test builds also recompute every incremental norm from
its generated coordinates.

The differential checker compared the complete JSON output of the parent
binary and the new binary on 7 boundary cases, 214 frozen cases, and 2,048
fresh scalars generated with seed `2026100979`: **4,538 matching outputs**
across hex4 and hex9. It independently checked **270 point outputs** against
Python secp256k1 multiplication. Its result SHA-256 is
`befc9d587e04db21ddc22d125b5688940c0bb63a4b21e704149296912387a1aa`.

The checker generated one 129-case, seven-repetition isolated benchmark
manifest per mode, pairing the direct and incremental binaries on the same
public scalar and expected point. Both manifests passed the runner's
structural validation. All **516 fixture commands** returned `verified=1`,
the declared input fields, and the expected point. The manifest SHA-256
values are `3493fe19f45f5c6796815e40a82db9a3306ac42457d27c4ec8f3b0049bf16378`
(hex4) and `3981539183d799105c2eca0ef5087e8f7219bbf4371697039adf789d60023a0b`
(hex9). These are correctness checks, without a CPU timing ratio.

| Frozen item | SHA-256 |
| --- | --- |
| Parent source at `257bc6cd6e9c54efc571f5baa4d2760b047c8da4` | `b556ae6b96abfea09602aa333552e9fe93dc41287d408c895146446a7c61c52f` |
| Parent release binary | `4cd41c19436cf7d7e18b1b90e42662ead2b56ba3d22800761eb1d1cd725329e3` |
| Incremental source | `ed24a77a761ccaa9cbf4dfb66724a2783ad2b78ab41578bee84c5a24c0869c8a` |
| Incremental release binary | `b806901d286cc82f0c2af75d6f28e0f27b10fabcc5e77a0fe2adbc012ed52159` |
| Differential checker | `9923c69637c82ed01d9aec3a2379c4c085db67735997216732fc3da0fab0bb65` |

The current RunPod container reports Docker/cgroup-v1 execution, no
host-level isolated CPU partition, and no `nohz_full` CPUs. It also has an
active single-thread CryptoMiniSat experiment. The benchmark service remains
available for serial dispatch, but this Pod cannot produce the isolation
receipt required for a controlled CPU speedup. The paired manifests are
ready to run on a host satisfying
[the CPU isolation gate](../../docs/ISOLATED_BENCHMARKS.md).

## Reproduce the local correctness check

Build the direct binary from the parent commit and this binary from the
current branch with distinct `CARGO_TARGET_DIR` values. Then run:

```sh
cd experiments/prime-j0-secp256k1-native
PYTHONDONTWRITEBYTECODE=1 python3 incremental_lattice_check.py \
  --reference /absolute/path/to/direct/eisenstein_fixed \
  --candidate /absolute/path/to/incremental/eisenstein_fixed \
  --output /absolute/path/to/new-result.json
```

Pass `--manifest-prefix`, `--reference-source`, `--cgroup`, `--cpus`,
`--execution-cpu`, and `--mem-node` to generate the paired manifests. The
last four values must come from the actual isolated host topology before
submitting a timing run.
