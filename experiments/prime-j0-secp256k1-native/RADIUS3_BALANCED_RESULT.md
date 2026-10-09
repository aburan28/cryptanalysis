# Balanced slots and a 33-edge matching atlas for fixed-generator tau multiplication

Packing balanced affine coordinates into two-limb coefficients made room
for **33 row-pair tables within 90 MiB**. A graph chosen by the frozen
greedy rule saved **4,383 mixed additions** against the 21-edge
radius-two graph on a fresh 4,096-scalar holdout. The declared
point-operation proxy fell from **990,764 to 942,551 field-product
units, a 4.87% reduction**. Both methods used the same nine
Eisenstein representatives and produced the same secp256k1 points.

## Construction

Each affine coordinate is a balanced Montgomery residue in
`Z[omega]/(pi)`. The nearest-lattice bound
`|a|, |b| < 2^128` applies to each of its two signed coefficients.
The [native implementation](src/bin/eisenstein_fixed.rs) packs four
two-limb magnitudes and one shared sign byte into a 72-byte aligned
slot. It checks every coefficient's higher limbs while constructing
all 1,299,078 points; decoding restores the exact signed residue before
the existing common-unit map and mixed addition. No field square root
is needed. The bound and reduction method are documented in the
[Eisenstein Montgomery result](EISENSTEIN_MONTGOMERY_RESULT.md).

The graph contains all 30 edges of distance at most three between the
12 ordinary comb rows, plus `(0,11)`, `(0,8)`, and `(1,11)`. Those
three edges were selected in that order by maximum-matching yield on
the separate 4,096-scalar design panel. An exact dynamic program builds
the 4,096-entry atlas before scalar processing. Each online comb column
forms its active-row mask and adds the corresponding matched pair
points plus unmatched row points. The sparse top-row repair is
unchanged. The method is for public scalars.

The atlas is exact by induction on the active-row mask. For its least
active row, any matching either leaves that row unmatched or pairs it
with one of its active graph neighbors. The builder evaluates every
such smaller mask and chooses the largest matching, using the sorted
edge sequence to resolve ties. Thus the lookup gives the minimum
number of row contributions attainable with the stored pair tables
for each mask.

| Graph | Edges | Retained pair slots | Holdout fusions | Holdout mixed additions | Holdout point proxy |
| --- | ---: | ---: | ---: | ---: | ---: |
| Radius two, balanced-slot budget | 21 | 59,521,392 bytes | 27,331 | 69,309 | 990,764 |
| Radius three | 30 | 85,030,560 bytes | 30,443 | 66,197 | 956,532 |
| **Greedy graph33** | **33** | **93,533,616 bytes** | **31,714** | **64,926** | **942,551** |

The graph33 slots use **89.20 MiB** and the matching atlas uses
28,672 bytes. The original radius-two slots occupied 85,975,344 bytes
at 104 bytes each; balanced packing reduced those same 21 tables to
59,521,392 bytes. The [frozen protocol](RADIUS3_BALANCED_PROTOCOL.md)
set the two scalar seeds, greedy tie rule, 90 MiB cap, 3% holdout gate,
and correctness requirements before the
[screen](radius3-balanced-screen-result.json). The holdout cleared
the gate at 4.87%; every scalar's maximum-matching count was at least
its radius-two count.

## Exact replay and measurement boundary

The [differential verifier](radius3_balanced_verify.py) passed on
**8,540 scalars**: five boundary values, 214 prior frozen values, all
129 expected-point fixtures, and two new 4,096-scalar panels. It
checked exact affine outputs, representatives, tau counts, terminal
repairs, and independently computed fusion counts for every scalar.
An independent Python secp256k1 multiplication checked 261 points;
all fixture points matched their recorded coordinates. Direct native
group-sum checks covered every new edge, and the atlas test checked
disjointness on every active-row mask. All **51 release tests passed**. The
[verification receipt](radius3-balanced-verify-result.json) retains
the per-panel counts and hashes.

The isolated-host comparison uses the same 129 public points and seven
paired repetitions. Its online interval includes nine representative
recodings, atlas and point lookups, two-limb decoding, all point work,
affine output, and the expected-point assertion. Reusable table
construction is recorded separately. The currently available RunPod
Pod fails the host-level isolation preflight in
[the benchmark contract](../../docs/ISOLATED_BENCHMARKS.md), so the
online CPU ratio awaits a qualifying host. The
[manifest generator](make_graph33_isolated_manifest.py) produced a
schema-valid local 129-case, seven-repeat manifest with SHA-256
`4a638336c17c5c68f3500ce0fd9f90e3a1fec55a72023e528c3243b07e25f7e6`.
The candidate benchmark entrypoint returned `verified=1` and the
recorded expected point for fixture 0.

The explicit table-preparation command reported **1,299,078 entries**,
93,533,616 retained slot bytes, and 28,672 atlas bytes. Peak child
resident memory was 316,194,816 bytes on this macOS ARM64 host.
Construction took 67,704.660 ms under local contention; this is a
reusable setup resource observation, outside the online timer.

| Artifact | SHA-256 |
| --- | --- |
| Frozen protocol | `964810804b33d6d4fbca86e9a51a447947d765a7de4f98e5335a6e54afa54d93` |
| Screen receipt | `5a6222e31e8f01d020ae4aecc3caac6714fe8c5f342d61a8aec12e7a1d2f7eee` |
| Verification receipt | `0276b63b6914b0bf428cf590df6f48246774010decc7d1a8588e5d16083a9815` |
| Candidate source | `007205d4697855fab13ed4a0af45e7b199faaa79926f8543b0588cadb69c75ee` |
| Candidate release binary | `a7a43630b2435daee293d9888b76527d345c56dec21bac500a8e91f5712b35e8` |

Structured pair-sum precomputation for fixed-base MSM appears in
[Grigaitis (2026)](https://www.preprints.org/manuscript/202604.0045).
This candidate selects overlapping edges by an explicit workload
objective and evaluates each active row set through a maximum-matching
atlas. A broader priority review is needed before an academic novelty
claim. The next empirical step is the complete paired online panel on
an isolated physical CPU.
