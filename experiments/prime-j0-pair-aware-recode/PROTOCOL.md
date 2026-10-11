# Pair-aware scoring of adjacent τ-adic streams

## Question and cost boundary

The opt-in gauge-carrying paired-τ evaluator currently chooses one of
four combinations of two nearby lattice representatives using
`6 * τ steps + 11 * mixed adds + rotations`. This heuristic does not
reward an adjacent empty position that can use a fused τ pair, nor the
multiplication-free Z scale chosen by the three-state gauge table.

This candidate keeps the same two representatives per scalar, same
four pair scores, same 1,104-byte preparation, and same evaluator. It
scores each decoded stream pair with the frozen nominal formula

`4 * τ steps + 8 * mixed adds + rotations - fused τ pairs
 - cheap-Z fused pairs`.

The scorer follows the evaluator's digit order and gauge transitions,
then picks the smallest formula count. Ties prefer fewer τ steps,
mixed additions, rotations, and lattice L1 norm. It records the number
of inspected positions and the selected model score. The model assumes
nonidentity intermediate points; a transient identity can skip work,
so evaluation counters are authoritative for actual formula execution.
The operation formula excludes squarings, exceptional additions,
recoding, scorer traversal, table lookup, inversion, and batch
normalization. It is a stage diagnostic, not a CPU speed metric.

Development checks on the previously used `prime-j0-taupair-steer`
fixtures saved only 291/106,990 and 520/243,676 nominal M on the two
curves, with 39,728 and 88,191 extra scoring positions. Those inputs
are not held-out evidence for this candidate. This prospective panel
tests whether the small operation gain is stable on new scalar pairs.

## Held-out procedure

Commit implementation, tests, this protocol, independent affine
fixture generator, and serial checker before generating new
1,024-pair inputs on `glv-j0-32` and `j0-56`. Freeze the input bytes,
seeds, and independently computed output digests in a second commit
before running either arm. Run control, candidate, candidate, control
serially on each curve in Release and UBSan. Preserve raw successes,
failures, source and binary hashes, counters, preparation, online
intervals, and post-run scalar replay.

The checker requires exact output digests, verified replay, unchanged
preparation and recoding counts, internally consistent formula
counters, and a positive nominal M saving per curve. A passing result
does not route the candidate into rho. The scorer's CPU overhead and
single-target online effect require separate evidence. The host lacks
verified exclusive CPU/NUMA isolation, so local wall times are
exploratory and both panels set `cpu_speedup_claim: null` and
`isolation_receipt: null`. Academic novelty of the combination is
unestablished; τ-adic recoding and tripling come from the supplied
Xu–Yu–Han–Lu paper.
