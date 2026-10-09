# Linear batching of the exact N131 d13 pair inverse

**The complete 8,191-sum inverse now needs 14 explicit field products per
proposed pair output instead of 8,191.** The batched method returned exactly
the same pair sets as the direct-product method on 32 signed pair outputs and
32 independently seeded uniform field controls, twice each. The 32 recovered
pairs passed an independent curve-addition replay. The sequential table was
the faster of two batched layouts in this local experiment.

For the exact same-rotation d13 policy in the [source inverse](../n131_d13_same_rotation_pairs_20261009/RESULT.md), write
`A(t)=t²+t`, `s=Σ s_i v_i`, and `z` for a proposed pair-output phi coordinate.
The source solver asks whether

`R_s(z)=(s²+z²)/A(z)`

lies in the rank-12 image of the cached map `L_s`. Since squaring and
multiplication by the fixed `A(z)⁻¹` are binary linear,

`R_s(z)=z²/A(z) + Σ s_i·(v_i²/A(z))`.

Thus one denominator inversion, one offset product, and 13 basis products
generate every right-hand side by XOR. `linear_dense` fills the 8,192-entry
right-hand-side table in increasing seed-sum order; `linear_gray` visits all
nonzero sums in Gray order with one XOR update. Both retain the source pivot
index, usable-selector filter, and exact pair result. Inputs with `A(z)=0`
return the empty set in all three methods.

The [frozen protocol](protocol.json) binds the exact source pivot index,
valid selectors, prior controls, checked-Sage runtime, implementation hashes,
and 64 output masks. Each of the three methods scanned all 8,191 nonzero
seed sums for each mask in two interleaved repetitions. Index loading and
field setup were outside each query interval. The [run receipt](result.json)
retains all 384 timed method calls and complete output sets; the
[independent audit](audit.json) replays every accepted pair as a signed curve
sum and checks every raw timing cell.

| Exact full-sum stage, 128 calls per method | Median wall | 10th–90th percentile | Explicit field products per call |
| --- | ---: | ---: | ---: |
| Direct product for every sum | 457.0 ms | 172.2–932.0 ms | 8,191 |
| Linear sequential table | 13.20 ms | 6.73–87.89 ms | 14 |
| Linear Gray walk | 16.12 ms | 7.25–86.91 ms | 14 |

Within each input and repetition, the median paired direct/sequential ratio
was **19.36×** (10th–90th percentile of paired ratios 7.07–65.78×); the
direct/Gray ratio was 17.29× (7.57–65.25×). These are exploratory
single-host stage measurements: the host has no CPU isolation receipt, and
its wide raw timing spread prevents promotion to a controlled speedup.
Peak process RSS was 43,155,456 bytes. The candidate and run IDs are null
because this is a pair-inverse proposal, not a complete IC pipeline.

The sequential table is the input to the [sparse-dual follow-up](../n131_d13_syndrome_pair_inverse_20261009/RESULT.md). A six-pair target solver
still has to propose target-compatible pair outputs before this inverse can
contribute to an ordinary relation. The next end-to-end gate is an unpinned
target-coupled N41 relation with at least two pair domains left free during
pruning, followed by a source-bound N131 public-target query.
