# Target-split half-trace for reciprocal S3 inversion

The mixed-rotation four-atom inverse now moves the repeated binary-field
half-trace out of its target query. On the frozen **N131 seed-one
constructed output**, the source-matched paired queries returned the same
product witness while the new query used **12.822 and 16.450 ms**, versus
**246.905 and 251.789 ms** for the baseline quadratic solver. The
trace-zero control returned zero hits under both implementations. These
are exploratory single-host stage intervals; the exact improvement is
that one target half-trace and one batch inversion replace one half-trace
and two inversions for each of 4,124 left output coordinates. Reusable
setup increased from roughly 0.26–0.27 s to 0.41–0.42 s in the positive
N131 pair.

## Identity and algorithm

For nonzero reciprocal pair-output coordinates `c,z` in `GF(2^n)` with
odd `n`, the third summation equation in the unknown right coordinate
`d` is

`(1+cz)^2 d^2 + cz d + (c+z)^2 = 0`.

Set `u=cz`, `k=1+u`, and, when `k!=0`, write
`d=(u/k²)v`. Substitution gives

`v²+v = (c+1/c+z+1/z)²`.

The half-trace `H(a)=Σ_(i=0)^((n−1)/2) a^(2^(2i))` is `GF(2)`-linear and
satisfies `H(a)²+H(a)=a+Tr(a)`. Thus setup stores
`h_c=H((c+1/c)²)` and its trace bit for each indexed left coordinate.
At query time it computes `h_z=H((z+1/z)²)` once. Unequal trace bits
reject a coordinate exactly; equal bits give the two roots

`d=(u/k²)(h_c+h_z)` and `d+(u/k²)`.

When `k=0`, the original equation is linear and has one root, handled
separately. The [implementation](native.cpp) batches all needed `1/k`
values with one field inversion and prefix products. It retains the
baseline pair-output tables, source products, target query inputs, and
right-table lookup. The [direct root audit](identity_audit.json) compared
the baseline and split root sets for **1,026** field inputs in each of
four N41/N131 positive/control panels, including `cz=1`; every root set
agreed. The [paired run](result.json) also matched the exact product-hit
lists on all 16 frozen trials.

## Frozen paired panel

The [protocol](protocol.json) hashes both binaries, both sources, compiler
version, archived mixed-rotation inputs, support, and run order before
measurement. Each case ran in `baseline, split, split, baseline` order,
with one worker, a 30-second executable cap, and 4-GiB RSS cap.
`candidate_id: null` because this is a point-decomposition component.
The [terminal audit](terminal_audit.json) checks each raw result, stdout,
stderr, terminal status, exact hits, caps, and the direct root audit.

| Field / proposed output | Baseline query, two runs | Split query, two runs | Split setup, two runs | Hits |
| --- | ---: | ---: | ---: | ---: |
| N41 constructed | 0.286 / 0.310 ms | 0.024 / 0.118 ms | 0.653 / 0.633 ms | 1 |
| N41 trace-zero | 0.247 / 0.286 ms | 0.023 / 0.026 ms | 0.631 / 0.732 ms | 0 |
| N131 constructed | 246.905 / 251.789 ms | **12.822 / 16.450 ms** | 414.479 / 413.147 ms | 1 |
| N131 trace-zero | 246.662 / 608.233 ms | 64.176 / 11.041 ms | 422.733 / 1069.718 ms | 0 |

The N131 constructed queries checked 4,124 left coordinates and used
4,124 batch-inversion terms. Process peaks in the panel were below
5 MiB. The large spread in the later control runs shows host contention;
no CPU wall-time speedup is promoted without the repository's isolation
receipt. Setup, all failed coordinate attempts, lookup, and hit checks
are retained separately from this component's query interval. The
component does not supply proposed outputs from the public point.

## Challenge-width streaming gate

The archived exact W14 mask-pair census has **33,780,028** usable
unordered pairs over all 16,383 nonzero seeds. At two reciprocal outputs
per pair, each rotated table has at most **67,560,056** entries. A proposed
packed record layout with a 17-byte field coordinate, 17-byte left
half-trace, and four-byte mask-pair witness uses at most
**3,986,043,304 bytes** for both tables together. This is a disk-backed
streaming proposal, not a constructed index or measured all-seed scan;
in-memory indexes and decoding need additional space. Multiplying the
larger positive split-query interval by 16,383 gives about **269.5 s**
of fixed-seed compute as a source-bound extrapolation, before disk I/O,
per-seed variation, and index management. The old quadratic solver's
same calculation exceeds 4,000 s.

The next experiment should build and query a compact streamed index for
a frozen sample of seeds, measure all target-dependent I/O and lookup,
and use the exact seed-count distribution to bound a complete all-seed
query below 600 s and 4 GiB. That would make the four-atom inverse usable
for a proposed output. A separate public-target constraint must still
produce useful outputs while other blocks remain free; its N41 gate is
an unpinned ordinary relation with independent group replay before the
N131 public-point run.
