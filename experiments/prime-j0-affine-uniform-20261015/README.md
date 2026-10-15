# Uniform-derived scalar stream for affine rotation tables

This experiment tests the full two-x affine table against the ordinary
affine-layer table on 12,288 unique SHAKE256-derived scalars. The candidate
stores `(x, x+βx, y)` and reconstructs the two nontrivial x rotations using
field subtraction and negation. The reference stores ordinary affine
`(x,y)` points and applies the constant field multiplication on demand.
Both use the same radix-14 recoding and four-layer batch-affine sum.

[generate_uniform_fixture.py](generate_uniform_fixture.py) derives a seed
from the frozen 128-point base fixture digest, then hashes a domain-separated
64-bit counter with SHAKE256. It accepts 32-byte candidates only when they
are nonzero, below the secp256k1 subgroup order, and unseen. Each accepted
point is computed by an independent Python binary scalar multiplication and
checked against the curve equation. The [fixture](mixed640_uniform_fixture.json)
contains the exact input law, seed, counter count, all scalars, and all
points; SHA-256
`a1c4964f174e36ea26f6a1897128f651a2ce7251e4bf4ffd532ff09221e721d3`.
The generator used 12,288 counters for 12,288 accepted unique scalars. Its
first attempt completed the computation but failed to write to a full SSD;
[the failure receipt](fixture-generation-attempt1.json) and
[successful rerun log](fixture-generation-success.log) retain both states.

The hash-guarded [native overlay](native_uniform_overlay.py) was applied to
the final distinct-input source. Its front source SHA-256 is
`3dead29b00d7c5bd84851bd59b29eb477480daf05e008debaffbfb002c7b8f6b`;
its windows source SHA-256 is
`71136ada79d64d136344c8649fe59a07ceb6cbcc03f30a1e66c3f1bc4848bf5d`;
the Linux release executable SHA-256 is
`44a6b7f0d9e1460e55da985e4e122c2b5d36fc384b9ead7ecdafeb4756350434`.
Both native paths passed 128-scalar independent binary replay tests on this
source snapshot. Their uniform modes checked every fixture point after
timing. A sequential exploratory A/B/A screen measured ordinary affine
71.829202 ms, full two-x 65.771592 ms, ordinary affine 71.665661 ms for
the same 12,288 outputs.

The [Tier 1 manifest](tier1-affine-uniform-cpu40-manifest.json) and
[predeclared rules](tier1-affine-uniform-cpu40-rules.json) freeze 16
alternating repetitions with adjacent A/A calibrations on CPU 40 in the
serial RunPod service. The timed interval begins after fixture parsing and
table construction and ends after 96 batches of 128 scalar multiplications
and affine recovery. All 12,288 point checks follow the interval. The
container reports affinity, cgroup, frequency, throttling, steal time,
interrupts, and memory placement; physical-host exclusivity is unverified.

The completed [RunPod panel](ef8bb2bbba6e405a9565859ce83ae7a4/summary.json)
contains 96 valid arms and all 48 planned pairs. Every adjacent A/A ratio
passed its frozen `[0.90, 1.11]` gate; the runner reported stable artifacts.
The [independent audit](tier1-affine-uniform-cpu40-audit.json) regenerated
the complete fixture, matched the source and binary hashes in the
[provenance archive](prime-j0-affine-uniform-native-provenance.tar.gz),
checked every recorded output and pair, and reproduced the predeclared
comparison gate. The raw [result archive](ef8bb2bbba6e405a9565859ce83ae7a4.tar.gz)
has SHA-256 `5be227fb97831edd32e6cc820253a04791048a8f8addca3aab3836dc517b7016`;
the provenance archive has SHA-256
`1902de487be00533ef34e1362e114863c529af2d34bb5c86a7ccbb93d4a00384`.

| Tier 1 same-input batch result | Ordinary affine | Full two-x |
| --- | ---: | ---: |
| Mean online time, 12,288 outputs | 70.737837 ms | 62.137246 ms |
| Mean online time per scalar | 5.756660 µs | 5.056742 µs |
| Retained table bytes | 26,035,988 | 37,192,948 |
| Mean table preparation | 3,950.829 ms | 3,967.026 ms |

The median paired ordinary/full-two-x online ratio is **1.155612×** across
16 comparison pairs; the predeclared bootstrap 95% interval is
`[1.101903, 1.178301]`. This measures batch throughput for one stream of
12,288 distinct SHAKE256-derived scalars on the observed RunPod Tier 1
instance. Table preparation and output verification are recorded separately
from the online interval. The extra retained table footprint is 11,156,960
bytes. The short sequential A/B/A screen above remains an exploratory
receipt, separate from this qualified panel.
