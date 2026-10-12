# Exact normal4 selector encoding gate for the equal-B m6 PDP

The balanced four-lift source formula for public query zero has 536,683
variables, 599,988 ordinary clauses, and 300,963 native XORs. This gate
changes only the encoding of its six normal-weight-four source leaves. The
source curve, six-summand pair tree, four exact raw target lifts, ascending
leaf-mask order, and `B=11,743,888` subgroup-usable factor-base points stay
fixed. Query zero is a development input; no held-out query is opened here.

Compare three exactly equivalent leaf-selector policies:

1. `legacy`: the frozen 131-bit selector and two Sinz at-most counters from
   the balanced-S3 parent.
2. `counter`: the same 131-bit selector, Sinz at-most-four, and a four-state
   threshold recurrence for at-least-four.
3. `support_index`: four strictly increasing eight-bit positions in
   `[0,130]`, decoded into the same 131 selector literals.

Eight bits are necessary: 131 distinct positions cannot fit in seven bits.

For the index policy, each selected bit is the OR of four exact index-equality
decoders. Range and strict order give four distinct selected positions; every
four-hot mask has the unique inverse tuple of its sorted support. The counter
policy uses `g[i,k] = g[i-1,k] OR (s[i] AND g[i-1,k-1])` for `1 <= k <= 4`,
with `g[0,0]=1`, `g[0,k>0]=0`, and final `g[131,4]=1`. Together with
at-most-four it is exactly the same four-hot set. Preserve this proof and
check all masks for smaller widths plus the frozen normal4 point controls and
an explicit valid leaf using position 130, the first value that needs eight
bits.

Build one-leaf and balanced six-leaf four-lift XCNFs for both new policies,
using the parent's native-XOR generator. Save SHA-256, exact sizes, build
costs, and deterministic archives. Reuse the parent balanced formula as the
legacy reference. A new policy passes construction only after checked Sage
reconstructs the frozen point controls and a planted balanced group sum, and
pinned native-XOR SAT accepts valid leaves and rejects a changed x bit and
invalid cardinality or index order. If either new policy saves at least 10%
of the legacy full-formula variables or ordinary clauses, run one ordinary
query-zero attempt for each passing material policy under the parent's pinned
CryptoMiniSat 5.14.7 binary, one thread, `--maxtime=120`, external 150-second
wall cap, and 4 GiB RSS guard. Preserve raw transcripts and censored statuses.
SAT assignments require independent signed-point and projected-row replay
before counting a verified relation or rank. Timing on the unisolated host is
exploratory; the decision rests on exact circuit size and verified useful
rows per fully charged query, not a solver-speed ratio. `candidate_id` stays
`null` until the collection, matrix, and target-descent pipeline is fixed.
