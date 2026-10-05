# Unit-orbit folding of fused eight-digit τ points

## Prospective question

Does a sixfold smaller point table improve complete prepared-scalar
throughput over the full fused eight-digit table? The candidate preserves
the same Eisenstein representative, eight-digit block decomposition, number
of point additions, block-normalized output, and portable positional
fallback. It trades a unit rotation or sign change at lookup time for a
smaller table and cheaper target-dependent preparation. This protocol is
committed before the orbit map, C implementation, new held-out scalar files,
or timing receipt. It is an implementation experiment, with no academic
novelty or CPU speedup claim.

## Exact orbit representation

For each valid ordered pair `(u,v)` of four-digit atlas patterns, multiply
both digit contributions by the same unit in
`{+1,+ω,+ω²,−1,−ω,−ω²}`. Units commute with τ, so this maps valid pairs to
valid pairs and sends their prepared points through the cheap curve
automorphism `ω(x,y)=(βx,y)` and sign negation `(x,y)↦(x,−y)`.
The zero pair has one element; all 29,592 nonzero pairs have six-element
orbits. Choose the lexicographically first ordered pair as each orbit's
representative. This gives **4,933** orbit representatives: zero, 72
single-digit orbits, and 4,860 two-digit orbits.

Generate two 47,089-entry maps in pair order: a `uint16_t` representative
ID (`65535` for an invalid pair), and a `uint8_t` unit code (`255` for an
invalid pair). Code `0,1,2` means `+1,+ω,+ω²`; code `3,4,5` means their
negatives. The unit code must transform the stored representative point
into the exact requested pair point. Generate inverse arrays of 4,933
representative pair IDs for preparation. Exhaustively verify every map
entry against exact τ digit recoding and the unit action on both coefficient
pairs; regenerate byte for byte and retain hashes.

At each eight-digit position, prepare only the 4,933 representative affine
points. This costs 4,860 two-digit pair additions per position, followed by
one batch normalization inversion. At 32 bytes per point, the affine table
uses 157,856 bytes per position: 631,424 bytes for the four-block 32-bit
candidate and 947,136 bytes for the six-block 56-bit candidate. Count the
orbit maps, inverse IDs, positional seed table, and temporary scratch
separately. The complete online operation includes any field multiplication
for `ω` or `ω²` and any sign negation before its mixed addition. Preserve
all fallback and output-inversion accounting.

## Frozen workload and promotion gate

After this protocol is committed and its PR opened, generate four new
4,096-scalar files on the same curves and generator/`37P` points as the
full fused panel. Use SplitMix64 state
`20261011 XOR (curve_index << 32) XOR point_index`; freeze little-endian
`u64` scalar files, their SHA-256, and independent generic point-output
digests before any timing. Pair `fused-batch128` as reference with
`fused-orbit-batch128` on each exact file. Preserve raw failures, source,
binary, compiler and workload hashes, table bytes, setup time/operations,
online additions/rotations, fallbacks, output inversions, replay, and
memory. Verify every point against generic multiplication and exhaustively
verify every orbit map entry; test identity, small-order curves, boundary
scalars, and span overflow fallback. The online interval begins before the
first scalar reduction and ends after the last affine output is stored.

The panel asks about repeated fixed-base throughput. A one-target rho
comparison must charge preparation of a table for a newly supplied target
point and report the same public target and resource envelope. Report
prepared throughput, setup-inclusive cost, and measured break-even count
separately. Promote a CPU speedup only after five AB/BA pairs pass the
repository's host-level CPU/NUMA isolation and noise gates. Ordinary-host
timings and operation-count savings remain exploratory diagnostics.
