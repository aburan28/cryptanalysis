# Exact radix-384 tau matching for fixed-base secp256k1 multiplication

The composite-radix atlas reduces the fifteen-window six-unit table from
24,578 to **18,074 stored points per window**. Its exact forest matching
uses 6,504 admissible degree-three endomorphism edges and saves
**6,269,864 retained bytes (25.82%)** against mode 134. The native
two-bucket evaluator reconstructs all 4,096 points in a new disjoint
scalar panel, with 128 independent binary point checks.

The [protocol](PROTOCOL.md) was frozen in commit `b2e5a8326` before the
reproducible screen. The [construction and native source](PROOF.md) were
frozen in commit `b00c3940456a6112fc6b9ea88a32757556b898d6` before
the new panel was drawn. The scalar stream SHA-256 is
`85402c9aef71dd954d08ebba2359e2a94d087fc621e061dbb1c22512f2a66312`;
the file and preceding-panel hashes are in [fresh-inputs.json](fresh-inputs.json).

| Format | Windows | Stored points per row | Point slots | Retained bytes | Online fold |
| --- | ---: | ---: | ---: | ---: | --- |
| Mode 132, mixed-width U16 | 16 | mixed | mixed | 13,283,616 | none |
| Mode 134, radix-384 | 15 | 24,578 | 368,670 | 24,283,336 | none |
| Mode 135, tau384 matching | 15 | 18,074 | 271,110 | **18,013,472** | at most one tau and one projective merge |

The [screen receipt](screen-result.json) checks all **147,456** residues,
the exact forest recurrence, and digit norm at most `253²`. It finds
12,900 eligible edges, 3,889 nontrivial tree components, and a maximum
matching of 6,504. The 662,128-byte [atlas](atlas.bin) has SHA-256
`c9e4896587bccf1368701821bfce6ea056eff54a3dbee81c13d4e240b10ebb56`.
The exact fifteen-window termination inequality holds for every certified
subgroup representative; 8,192 previously frozen scalars and the new
4,096-scalar panel also reconstructed exactly.

| Native correctness gate | Result |
| --- | --- |
| New full-range panel, disjoint from prior panels | 4,096 point matches with mode 134 |
| Independent binary evaluator | First 128 new points match |
| Fixed generator fixture | 129 expected points match |
| Stored point table | All 271,110 slots match independently formed group sums |
| Tau and projective addition formulas | Independent small-scalar checks pass |
| Complete release suite | 98 passed, zero failed |

On the new panel, bucket zero selected 45,439 nonidentity points and
bucket one selected 16,001. The bucket sums used 53,281 nominal mixed
additions; 4,063 scalars occupied both buckets and therefore used a tau
map and a projective merge. The corresponding direct radix-384 schedule
has 57,344 nominal mixed additions on this panel. The native grouped
unit gauge used four field products in 2,999 of the 4,096 cases, three
in 874, two in 221, and one in 2. Exact raw results, platform identity,
source/input/binary hashes, and failures are in the [local receipt](evidence/local/receipt.json)
and its adjacent logs.

The next controlled experiment pairs modes 132, 134, and 135 on the same
public scalars and one host satisfying the CPU partition, NUMA, frequency,
IRQ, and noise gates in [ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md).
The current RunPod container performs serialized Linux correctness replays
but does not pass that host gate. The additional tau, merge, and gauge
work is charged to mode 135's online interval; the storage reduction by
itself does not determine its online wall time.
The current research evaluator uses scalar-dependent table indices and
bucket schedules; use with secret scalars requires a constant-time
lookup and control-flow design.

Unit-based digit sets on ordinary prime curves appear in
[Heuberger and Mazzoli, 2013](https://eprint.iacr.org/2013/705), and
endomorphism-based table compression appears in
[Aardal and Aranha, 2022](https://eprint.iacr.org/2022/748).
The contribution here is the exact finite forest matching for a
composite radix divisible by the endomorphism degree, its maximal
certified digit radius, and the resulting source-bound secp256k1
implementation. A broader priority review is needed before an academic
novelty claim for that combination.
