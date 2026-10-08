# Packed monomial-order keys

The frozen four-arm experiment changes only sorting inside `ordered_multiple`.
`baseline` is the unchanged producer; `compare` instruments its existing
comparator; `keys` encodes eligible rows; `threshold` encodes only rows with at
least 32 terms. The threshold is fixed before measurements. No arm uses the
round97 scratch optimization, so the sorting effect is isolated.

For masks confined to bits 0–56, encode
`((uint64_t(64 - popcount(mask))) << 57) | mask` and sort unsigned keys ascending.
The prefix decreases as degree increases; within equal degree the suffix is
the original integer mask. This is exactly the producer's descending grevlex
order. Prefix and mask do not overlap, including degree zero (key `1 << 63`).
All words are decoded before duplicate parity cancellation and proof emission.
Any row containing a bit at position 57 or above uses the original comparator.
The fallback retains full 64-bit mask support. This changes constant factors,
not the comparison sort complexity or the asymptotic Gröbner algorithm.

Charges, proof emission, reducer priority, failure behavior, coefficient descent,
independent certificate checking, equation/curve replay and query teardown are
unchanged. Per-thread counters reset for every producer invocation. Setup is
separate and no numeric row or answer is reused across targets.

Freeze executable sources and the panel before one diagnostic run. Validate
optimized and UBSan builds, exhaustive small order pairs, randomized boundary
masks, unchanged-source native multiplication traces, budget/node failures,
complete changed-target calls and concurrency. Audit proofs independently without
loading archived native code; retain failures and corruption controls.

The panel keeps the prior 23 algebra/planted-PDP fixtures, four paired arms,
two warmup rounds and four observation rounds. All raw costs and inconclusive
results remain rows. A local host without an isolation receipt is diagnostic;
qualified/aggregate/online speedups stay null. Do not change automatic dispatch
or make IC/rho, GPU, globally fastest or F6 claims from this experiment.
