# Exact N131 d13 batch pair-output pilot

**Checked Sage batch arithmetic produced 524,992 signed pair-output x
coordinates from 262,496 unordered pairs on the exact degree-131 d13
factor-base geometry.** All output x values were distinct within this
frozen 64-left-code pilot. Independent scalar Sage and source ONB group
arithmetic agreed on 96 saved outputs. This supplies an exact,
challenge-width pair-output generation primitive for a future
target-coupled solver; it does not supply the six-pair search rule.

The [protocol](protocol.json) fixes the exact valid-code list of 4,134
selectors, source curve geometry, ONB-to-polynomial conversion header,
accepted Sage runtime, source hashes, the first 64 left codes, a 300-second
wall cap, and a 2-GiB process RSS cap. Each pair `(a,b)` with `a<b` emits
the x coordinates of `P_a+P_b` and `P_a-P_b`. The installed
`binary_batch.add_pairs` performs each left-code batch with amortized
inversion. The output stream is hashed in canonical left-code, right-code,
branch order; the [run receipt](result.json) preserves the digest, samples,
counts, and exclusive setup, batch-addition, and key-conversion times.

| Pilot stage | Observation |
| --- | ---: |
| Usable left codes / unordered pairs | 64 / 262,496 |
| Signed output x coordinates / distinct x values | 524,992 / 524,992 |
| Exceptional `x=1` outputs | 0 |
| Point and field setup | 9.041 s |
| Installed native batch addition | 1.754 s |
| Polynomial-basis integer key conversion and hashing | 50.084 s |
| Total wall / peak process RSS | 60.883 s / 332,169,216 B |
| Independent exact output replays | 96 |

The [independent audit](audit.json) recomputes the exact pair and payload
counts, verifies the resource and phase receipt, and replays 96 saved x
coordinates both by scalar Sage addition and by the separate source ONB
curve implementation. The replay compares the same polynomial-basis x
encoding along both paths. The checked runtime is
[saved here](sage_runtime_info.json).

The full 4,134-code domain contains `C(4134,2)=8,542,911` unordered
descriptors and at most 17,085,822 signed x outputs. Packing one 131-bit x
value, both 13-bit codes, and a branch bit into 21 bytes uses 17 bytes for
x and four bytes for the two codes plus branch. It needs **358,802,262
bytes of raw payload** before sorting, indexing, allocator overhead, or
collision handling. The pilot digest uses a separate branch byte; the
21-byte layout is a format calculation, not a measured full index.
Extrapolating the pilot's phase rates to the full domain would give
about 57 seconds of batch additions and 1,630 seconds of Python key
conversion, plus setup; these are unisolated-host projections, not a full
enumeration measurement or an IC online timing result.

The [six-pair density frontier](../n131_d13_six_pair_prefix_frontier_20261009/RESULT.md)
still rules out using faster terminal pair membership alone as the method:
two target-independent fixed pairs require at least 249,560,561 complete
four-free-pair completion probes for 50% success under its stated uniform
target law. The next constructive gate remains an implicit, public-target
joint solver that constrains multiple free pair blocks and generates
compatible outputs before querying this primitive. Candidate and run IDs
remain null; no IC/rho speedup is inferred from this target-independent
stage.
