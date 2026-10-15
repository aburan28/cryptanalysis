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
The short screen is a sizing signal pending the full panel.
