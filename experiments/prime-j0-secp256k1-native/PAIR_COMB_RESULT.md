# Orbit-quotiented paired-row tau comb

Pairing adjacent rows of the 13-column, fixed-generator tau comb reduced the
complete point-evaluation proxy from **645,329 to 564,765 field-product
units (12.48%)** on 2,048 fresh public secp256k1 scalars. It replaced
**7,324 mixed additions** with precomputed pair points while retaining the
same nine-representative scalar selector, tau-map count, and output point.
The online CPU wall-time effect remains to be measured on an isolated host.

## Construction

The six row pairs are `(0,1),...,(10,11)`. For a pair with shifted bases
`P,Q`, store `D_o(P) + v D_p(Q)` for 81 first digit orbits, 81 second digit
orbits, and six relative units `v`. At lookup, two row digits `uD_o,wD_p`
become the single point

`u (D_o(P) + (u^-1 w) D_p(Q)) = uD_o(P) + wD_p(Q)`.

This quotients the 486-by-486 signed digit-pair space by its common sixfold
unit action. It takes **39,366 points per row pair**, or **236,196 points**
for the six pairs. A single active row uses the parent point table. The
sparse thirteenth row and its terminal repair keep the parent behavior.
The implementation is for public scalars and has input-dependent lookup.

The parent [incremental hex9 result](INCREMENTAL_LATTICE_RESULT.md) is the
reference: both binaries use the same candidate construction and recoding.
The pair table changes only point evaluation. Pair table preparation is
reusable fixed-generator setup and occurs before the online timer.

## Frozen operation and correctness record

| Panel | Scalars | Reference mixed adds | Paired mixed adds | Fusions | Reference proxy | Paired proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Boundary values | 5 | 0 | 0 | 0 | 0 | 0 |
| Parent frozen | 214 | 4,655 | 3,969 | 686 | 62,310 | 54,764 |
| Benchmark fixtures | 129 | 3,043 | 2,596 | 447 | 40,663 | 35,746 |
| Fresh seed `20261009113` | 2,048 | 48,309 | **40,985** | **7,324** | 645,329 | **564,765** |

Every one of the **2,396** paired scalar outputs had the same selected
representative, tau count, top-repair status, and affine point. For each,
the reference mixed-addition count equaled the paired count plus the
independently predicted number of row-pair co-occurrences. An independent
Python secp256k1 calculation checked 261 boundary/fresh outputs, and all
129 benchmark fixture points matched their frozen expected coordinates.
The native release suite passed **48 tests**, including 324 direct point-sum
comparisons across the six pair tables and 19 additional scalar replays.

The 129-case, seven-repetition isolated benchmark manifest passed structural
validation. Its reference and candidate fixture entrypoints were checked
on cases 0, 64, and 128. The streamed replay above independently checked
every fixture point. The manifest SHA-256 is
`7d9198cbd1aabb613d4649150b5780baab9fc0623a314beb37b9366f5fb18e84`.

## Preparation and memory

On this macOS ARM64 host, the explicit preparation entrypoint reported
**2,296.478 ms** for the pair table. It reported **236,196 entries** and
**102,036,672 table bytes** (`432` bytes per stored Jacobian). The child
process peak resident set was **129,024,000 bytes**. These are setup/resource
observations on the local host, outside the scalar online interval and not a
CPU speedup comparison. The preparation receipt SHA-256 is
`85cf121f6766bf82ecc3e2a18abb6507a045cbeb274cd65d516e41299c6d30e8`.

| Receipt | SHA-256 |
| --- | --- |
| Parent source | `ed24a77a761ccaa9cbf4dfb66724a2783ad2b78ab41578bee84c5a24c0869c8a` |
| Parent release binary | `b806901d286cc82f0c2af75d6f28e0f27b10fabcc5e77a0fe2adbc012ed52159` |
| Paired source | `280de1b3ff243c21e3e6b77d15128aba65491b62022402d2045f6a1f2d5d7fd3` |
| Paired release binary | `285e29a661105e63a290c9c45d9df63b36d6cf6f4f65fed27e9a9d4250d4a236` |
| Differential checker | `8eba5191df21ecd105b2ec2046e624017e18e30f8068854334b60400c94481a3` |
| Differential result | `76a08de53c973d7abe1918f8e23a22019259e9bd8c4eec5c935bc06ad8d2c675` |

The core fresh input law, resource cap, and acceptance gates were recorded in
[the protocol](PAIR_COMB_PROTOCOL.md) before implementation. The 129-case
fixture panel was added to the final replay after checking its coverage
against the parent frozen panel. The next
evaluation is a complete online run on a host satisfying
[the isolation gate](../../docs/ISOLATED_BENCHMARKS.md), with table memory
and preparation reported separately. Pair precomputation is an established
fixed-base technique; a literature audit must assess the specific sixfold
orbit quotient and row schedule before an academic priority statement.

## Reproduce

```sh
cd experiments/prime-j0-secp256k1-native
export CARGO_TARGET_DIR=/absolute/path/to/paired-build
cargo test --offline --locked --release --bin eisenstein_fixed
cargo build --offline --locked --release --bin eisenstein_fixed
"$CARGO_TARGET_DIR/release/eisenstein_fixed" --prepare-w6-comb13-hex9-paired
PYTHONDONTWRITEBYTECODE=1 python3 pair_comb_screen.py \
  --reference /absolute/path/to/parent/eisenstein_fixed \
  --candidate "$CARGO_TARGET_DIR/release/eisenstein_fixed" \
  --output /absolute/path/to/new-result.json
```
