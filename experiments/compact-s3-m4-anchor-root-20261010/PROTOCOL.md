# Q1427: early anchored pair roots before ordinary four-summand SAT search

Q1425 and Q1426 reach no first SAT model on their ordinary four-variable-
leaf formulas under the frozen caps, so their model-triggered exact S3
oracle never fires. Q1427 makes the oracle part of the search entry point:
fix an exact-base pair of raw leaf x coordinates, compute its exact zero,
one, or two S3 intermediate roots, and solve the remaining two-variable-
leaf S3 chain under one root assumption at a time. CryptoMiniSat keeps
learned clauses between root branches and rejected models for a fixed
target lift. The code does not expand S5.

This is a complete four-summand decomposition *method family*: an eventual
collector would enumerate or guide the anchored pair choices and charge
every anchor and failed solve. The bounded experiment runs one known-
solution control and two witness-independent ordinary anchor choices at
each degree. N53 scans two of its 428 target lifts per ordinary anchor;
N83 scans all four. The N53 subset is a diagnostic, not a complete query.

The exact curve IDs, bases, and ordinary workloads are the Q1425/Q1426
records. N53 is `EC1N53Ckb1hf77aab617904`, Q1301 W≤3 with B=24,062
usable subgroup points and K=227 signed-Frobenius columns, workload
`74f2979b3e68`. N83 is `EC1N83Ckb1h876c2921cb64`, Q1325 W≤5 with
B=30,977,592 and K=186,612, workload `bab50a1e5f66`. Q1427 remains
a proposal with null candidate and run IDs and `isogeny: "none"` (`ISO0`).

The ordinary anchor generator uses a SHA-256 stream keyed by proposal,
curve, workload, anchor number, and candidate ordinal. It un-ranks exact-
weight normal-basis masks, constructs rational curve points, projects by
the cofactor, checks subgroup order and membership in the exact archived
base, rejects duplicate folded columns, and keeps the first pair with
nonzero exact S3 roots. The generator is rerun in each measured anchor
cell; its target-dependent selection time, failed candidates, group-law
calls, and oracle-field API calls are charged. Base-index loading and
curve setup are recorded separately as reusable preparation. The
controls use an archived known pair and lift only to test correctness.

The solver has one SAT thread. A per-anchor run permits 90 target-
dependent wall seconds, 17 SAT calls, and at most 16 rejected complete
models. Each SAT call has configured limits of 100,000 conflicts and 25
CPU seconds. A small C++ shim exposes CryptoMiniSat's exact last-call
conflict, propagation, and decision counters, which its C API omits.
The shim and linked library hashes are frozen. `BOUNDED_UNKNOWN` preserves
unresolved branches; the exact counter and stop status are recorded for
every call. Any model is checked against the CNF/XOR rows, its root
assumptions, exact base membership, four distinct quotient columns, and
the public group sum. A new N83 ordinary relation requires independent
checked-Sage replay and a rank-novelty measurement before promotion.
The 33-KiB macOS shim is built from `cmsat_stats.cpp` by the frozen
`build_shim.sh`; its binary is archived because the measured counter ABI
must match this host's CryptoMiniSat build.

The primary empirical objective remains one public target. A complete
one-target cost must include all attempted anchors and all relevant
target lifts, then relation collection, matrix construction and final
linear algebra, target descent, and scalar replay. A censored anchor
sample cannot be fitted as ordinary yield or a complete N131 `2^x`
estimate. CPU wall-time comparisons are exploratory without a host-
isolation receipt.
