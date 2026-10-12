# Carry the unit gauge through paired τ strides

## Frozen hypothesis

The paired-τ evaluator in `prime-j0-paired-tau` uses the existing
free-gauge digit choice. A two-step stride is represented by the
optimized tripling core. Its final Jacobian Z scale is
`-beta^(delta+1)` for gauge transition `delta`. A transition of two
needs only Z negation; the other transitions each cost one field
multiplication. The digit-only gauge choice often misses that saving,
especially when the stride ends at an empty digit position.

Add an opt-in three-state, thirteen-pattern lookup that minimizes the
local count of Z-scale field multiplications plus digit rotations,
including the final correction on the last nonzero digit. Pattern 12
represents an empty destination position. Ties retain the original
free-gauge choice. The table is exhaustively reconstructed and
checked by `ca_ec_tau4_pair_steer_verify_map`. A steered stride may
change gauge at an empty position; the next step and any later digit
are interpreted in that carried gauge.

The frozen operation objective is the **net field-multiplication
count** under the current formulas. Both arms must preserve scalar
recoding, pair scores, τ steps, fused-pair count, mixed additions,
inversions, prepared table, and independent affine outputs. The
steered arm may change rotations and gauge transitions. Its exact
net saving against the unsteered paired arm is

`(steered_cheap_z - baseline_cheap_z) -
 (steered_rotations - baseline_rotations)`.

The gate requires that quantity to be positive on each study curve.
The table lookup itself has CPU cost, so a lower multiplication count
does not establish lower wall time. This local choice is not claimed
globally optimal across the whole gauge path.

## Held-out gate

Commit implementation, tests, this protocol, independent affine
fixture generator, and serial checker before generating fresh
1,024-pair fixtures on `glv-j0-32` and `j0-56`. Freeze fixture bytes,
seeds, and output digests in a second commit. Run unsteered, steered,
steered, unsteered serially for each curve in Release and UBSan.
Retain every raw result, including failures, source and binary hashes,
exact counters, and correctness digests. The host has no verified
exclusive CPU and NUMA partition; set `cpu_speedup_claim: null` and
`isolation_receipt: null` regardless of local timing.

This is a batch scalar-stage diagnostic, not the primary one-target
online comparison. The τ and tripling identities derive from the
Xu–Yu–Han–Lu paper supplied by the user; academic novelty of this
gauge-carrying combination has not been established.
