# Three-image atlas crosses the reported 64 MiB cache boundary

The radix-1024 three-image cover reduces the fixed-generator table from
1,058,657 to **890,292 affine slots** while retaining twelve signed
shift windows and the exact terminal residual. The full-window atlas has
73,417 seeds, the terminal atlas has 9,288, and the independent verifier
replayed all 1,048,576 residue codes and 80,521 terminal pairs. It also
recomputed the minimum seed counts for the declared three-image policy.

A new 4,096-scalar full-range panel was frozen after the atlas and input
law. It is disjoint from the panels listed in
[fresh-inputs.json](fresh-inputs.json). Both the three-image evaluator
and the two-image radix-1024 control recovered the same point for every
scalar. The group replay checks integer reconstruction, each selected
term, the three tau buckets, grouped-unit gauge, and independent binary
scalar multiplication. The native test pairs both modes on all 4,096
scalars and checks the first 128 against its separate binary point path.

| Same-panel operation and storage record | Two-image control | Three-image candidate |
| --- | ---: | ---: |
| Scalars | 4,096 | 4,096 |
| Affine slots | 1,058,657 | 890,292 |
| Native retained bytes | 72,663,424 | 61,829,108 |
| Mixed additions | 49,151 | 49,151 |
| Grouped gauge rotations | 14,882 | 18,186 |
| Scheduled outer tau calls | 4,096 | 8,192 |
| Output SHA-256 | `c6eb1aceac8811a6634ba34e0f387f7c55169f9413f4ba7ca7bf3dc3d6842e02` | same |

The three-image table saves **10,834,316 retained bytes**. The current
RunPod CPU [reports](host-cache-observation.json) a 64 MiB L3 cache, or
67,108,864 bytes: this table is
5,279,756 bytes below that nominal capacity, while the two-image table
is 5,554,560 bytes above it. The cache is shared and its occupancy is
uncontrolled on that pod. This comparison motivates a controlled paired
runtime test; it does not itself establish a wall-time gain. The extra
tau work and 3,304 additional grouped rotations are included in that
test. The three-image group replay counted 7,734 outer tau calls with a
nonidentity input; the native `tau` method returns early on identity.

The [construction proof](PROOF.md), its
[partition detail](PROOF_NOTE.md), [atlas receipt](atlas-receipt.json),
[independent check](independent-check.json),
[group replay](group-check.json), [paired control](control-group.json),
and [native materializer](materialize_native.py) specify the complete
candidate and its correctness evidence. CPU timing requires the
host-level isolation receipt in `docs/ISOLATED_BENCHMARKS.md`.
