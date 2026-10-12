# Unit-orbit fused digit pairs for public double-scalar multiplication

## Frozen question

Can a target-dependent table of joint τ digits replace the two mixed point
additions made at overlapping nonzero positions in the joint prime-field
τ stream? The control is the same-table joint evaluator from PR #419. The
workload is the already frozen 1,024-pair fixture on each study curve.
This is an algorithmic operation experiment; local wall times remain
exploratory until host-level isolation is proved.

## Algebra and table

Every width-four nonzero digit denotes `u A_s`, where `s` is one of nine
base seeds and `u` is a sign plus a power of the order-three automorphism.
For simultaneous digits `u A_s` and `v B_t`, factor the common unit:

`u A_s + v B_t = u (A_s + (u^-1 v) B_t)`.

There are at most `9 × 9 × 6 = 486` relative entries, rather than
`54 × 54 = 2,916` ordered signed pairs. Prepare the 486 affine sums after
the shared 18-seed preparation. Normalize the 486 projective sums in one
additional batch inversion. At an overlap, apply `u` to the selected sum
and add it to the Horner accumulator once. If a table sum is the identity,
skip the addition. Singleton positions retain the PR #419 path. The table
is tied to the exact ordered `(P,Q)` pair and cannot be shared across
targets. Its entire preparation cost is target-dependent in a rho solve.

## Gates

First test both methods against ordinary `aP+bQ` on zero, identity,
equal-point, opposite-point, cancellation, order-boundary and maximal
64-bit inputs. Keep the shared-table joint stream as the control. Freeze
source and checker before running the prospective panel; keep every raw
failure. Report preparation point additions, inversions and bytes, overlap
count, fused hits, mixed additions, τ maps, rotations and exact output.
The panel must not report a CPU speedup. Evaluate preparation break-even
in point-addition equivalents for the frozen 1,024-pair workload, and
state the number of evaluations needed to repay table construction.

Academic novelty is unproved; double-scalar joint recoding and endomorphism
orbit techniques have prior art. No automatic rho routing follows from
this operation experiment. A one-target rho comparison and host-level
isolation receipt are required for a wall-time promotion.
