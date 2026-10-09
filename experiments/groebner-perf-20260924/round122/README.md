# Cached bitset eligibility for certified F4 normalization

The bounded 4096-bit grevlex F4 path in round119 scans every term of every
installed reducer on each call to `normal()` before using the bitset kernel.
This opt-in candidate counts installed rows with a term outside the low 12
variables. Installation and final interreduction update that count; every
query still checks its fresh value row. A nonzero count selects the original
sparse path. The existing fallback for a non-basis reducer vector remains a
full scan. No target coefficient, proof node, or answer is cached.

The semantic invariant is
`basis_wide_rows == number of rows in basis containing a term outside 0..4095`.
The counter changes only when `install()` appends a row or final
interreduction erases/replaces one. Reducer priority, arithmetic operations,
proof-node order, work charges, resource caps, and final independent
certification remain unchanged.

The frozen comparison is the five `pdp-12-seed-{1..5}` queries from the
round112 independently audited panel, with the round119 bitset engine as the
reference. The input is `GF(2^31)` under modulus `2147483657`, curve
coefficient `b=1`, three summands, and four factor-base coordinates per
summand. Both arms receive identical target-dependent coefficients, matrix
and continuation caps, complete-query timing boundaries, equation checks,
proof checking, and curve replay. An optimized and UBSan correctness panel
must match the reference reduced basis, assignment, work counters and exact
serialized proof bytes on all five cases. Controls at 13, 21, 32 and 64
variables cross the 12-bit guard and must reject corrupted proof outputs.

Only after the candidate source is committed and built from pinned reference
hashes may `profile.py` run one warmup and five alternating AB/BA pairs per
case. The complete-query timer includes fresh coefficient descent, matrix
production, native F4, independent proof, original-equation and curve checks,
and lease teardown. Reusable setup and fixture construction stay separate.
All failures and timeouts remain rows. Local CPU timings are diagnostics;
a controlled speedup requires the isolated physical-host receipt described
in [the benchmark contract](../../../docs/ISOLATED_BENCHMARKS.md).

The reference worktree must have the source-matched round119 optimized and
UBSan builds. Reproduction commands, frozen hashes and raw outcomes will be
recorded with the completed experiment.
