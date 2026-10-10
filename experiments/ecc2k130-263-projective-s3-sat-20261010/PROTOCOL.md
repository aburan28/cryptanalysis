# Frozen full-SAT and sign-decoding control for projective Q1420

The [projective-S3 experiment](../ecc2k130-263-projective-s3-20261010/RESULT.md)
has an independently checked N131 cancellation witness on each equal-size
source/descendant W24 base. This gate asks whether a full CryptoMiniSat model
of the native-XOR circuit can encode that exceptional branch and be decoded
back to an exact group sum. It is a witness-control workload derived from the
archived group points; the four target mux x choices are not the frozen public
Q1420 target. The controls do not estimate ordinary-query relation yield.

Freeze the parent commit and SHA-256 identities in [CONFIG.json](CONFIG.json)
before running. Rebuild one control XCNF per policy with the parent six leaf
equations, ordering, projective S3 tree, and source/descendant constants.
Replace only the four public target x choices with `(witness_x,
witness_x xor 1, witness_x xor 1, witness_x xor 1)`. Record a bijection from
named circuit input bits to DIMACS variables, the exact control formula hash,
and source hashes. The parent input verifier and projective audit must pass
before construction. Build under a 300-second external wall and 4-GiB sampled
RSS cap. Archive the exact base XCNFs losslessly.

Derive three unit-clause deltas from that one base formula per policy:

1. **Positive:** fix all six ordered leaf masks, their x/z words, four
   intermediate x/finite flags, and target selector to choice zero. The
   resulting XCNF must be SAT.
2. **Negative:** fix the same witness inputs but select choice one, flipping
   the target x bit zero. The resulting XCNF must be UNSAT.
3. **Free intermediates:** fix only six leaf masks and target choice zero.
   Leave leaf x/z and intermediate x/finite variables for the solver.

The base formula, unit clauses, and their ordered concatenation define every
exact solver input. Save raw input hashes and sizes; the small unit-delta files
are sufficient to reconstruct each input from the archived base, avoiding six
redundant full-formula archives. For SAT, parse the solver model, independently
check every ordinary clause and native-XOR equation, decode all input words,
enumerate the at most 64 leaf sign assignments, and replay each projective
intermediate and exact target point with the independent binary group law.
Reject any model whose DIMACS or group certificate fails. Preserve raw solver
stdout/stderr losslessly and record a separate result for each cell.

Run the six cells in the order fixed in CONFIG.json, once each. Use one solver
thread and its pinned binary; the fixed positive/negative cells have a
45-second internal and 60-second external wall cap, while free-intermediate
cells have 120/150-second caps. All have a 4-GiB sampled-RSS cap. An explicit
`s INDETERMINATE` or guard stop is `BOUNDED_UNKNOWN`, not UNSAT. Preserve
failed producer attempts, timeouts, and OOMs without replacing a seed or
silently retrying. Any sandbox/producer repair must be documented and frozen
before a new solver launch. The host is unisolated, so timings are diagnostic.

Promote the chart to a complete exceptional-branch extraction control only if
the fixed positive SAT model and exact sign/group replay pass on both curves,
and both bit-mutated controls are explicitly UNSAT. The free-intermediate
cells measure whether this encoding also searches from leaf masks alone.
The next ordinary-query comparison must use the same public point, factor
bases, Gaussian settings, and fully charged resource envelope for finite and
projective charts. `candidate_id`, natural relation yield, rank, online IC
time, and matched rho ratio stay null for this control.
