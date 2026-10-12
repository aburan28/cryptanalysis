# Gauge-aware lattice representative search

## Frozen hypothesis

The existing paired τ evaluator chooses two nearby lattice
representatives for each scalar using their standalone digit rotation
counts. The subsequent free-gauge evaluator can absorb unit changes
into the already required τ Z multiplication, so those standalone
rotation counts are not its actual cost.

Add two opt-in recoders that score a candidate pair by
`6 * tau_steps + 11 * mixed_adds + actual_free_gauge_rotations`.
The first retains the existing two representatives per scalar; the
second searches the five axial neighbors per scalar. The weights are
the existing heuristic, not a measured field-operation count. The
actual rotation term counts positions where both streams have
different unit powers, plus the final correction. Three power masks
per stream and population counts evaluate this term; a nonnegative
lower bound skips pairs that cannot beat the incumbent score.
Both arms retain the same point formulas, prepared table, and
independent free-gauge choices as the baseline.

The two-neighbor arm must preserve recoding and pair-score counts and
not increase the weighted objective. The five-neighbor arm must not
increase that objective relative to the two-neighbor arm, while
reporting its extra recoding and pair scores. All outputs must match an
independent affine oracle. A lower weighted objective is a diagnostic;
the extra recoding may erase its CPU benefit. No automatic routing or
CPU speedup claim follows from this panel.

## Held-out gate

Commit the implementation, tests, this protocol, independent affine
fixture generator, and panel checker before generating fresh 1,024
pair fixtures on `glv-j0-32` and `j0-56`. Freeze both fixture bytes,
seeds, and output digests in a second commit before running any arm.
Run baseline, scored two, scored five, scored five, scored two,
baseline serially for each curve under both Release and UBSan.
Retain all raw successes and failures, source and binary hashes,
operation counters, output replay, and local timing. The local host
has no verified exclusive CPU partition; timing stays exploratory
with `cpu_speedup_claim: null` and `isolation_receipt: null`.

This is a scalar-stage batch diagnostic. A fresh one-target rho solve
on the same public point as generic rho and a host-level isolation
receipt are separate gates for an online CPU speedup claim.
Unit-digit and τ-adic recoding have extensive prior art, including
[symmetric digit sets for elliptic-curve scalar multiplication](https://doi.org/10.1016/j.tcs.2014.06.010); academic novelty of this
combined scoring method has not been established.
