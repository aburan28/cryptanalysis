# Gauge-trellis joint τ stream

## Frozen hypothesis

The j=0 unit action `phi(x,y)=(beta*x,y)` commutes with τ and the group
law. A joint τ accumulator can therefore carry one of three equivalent
unit orientations at each nonzero digit position. Rotating the accumulator
to a new orientation costs one Montgomery field multiplication of its
Jacobian x-coordinate when it is nonidentity. Digits in the new orientation
cost one coordinate rotation each when their shifted unit power is nonzero.
At the end, undo a nonzero orientation with one more rotation.

Add an opt-in `paired2-trellis` arm. Keep the same two-neighbor lattice
representatives, four pair scores, 18 prepared seed points, and chosen
digit streams as `paired2`. After choosing that stream pair, use a
three-state dynamic program over nonempty positions to minimize

`digit_rotations + gauge_transitions + final_correction`.

The initial gauge is free while the accumulator is the identity. Each
later change costs one, and a nonzero final gauge costs one. Choose the
lowest gauge on ties. Backtrack the winning schedule, then evaluate it
exactly, counting actual digit rotations, accumulator transitions and
final correction. If an intermediate accumulator is identity, a planned
transition is free and the actual rotation count may be lower than the
dynamic-program score. Never omit transition or final-correction work.

Normalize the three path costs after each position. Their offsets fit in
two bits apiece, giving a 64-state automaton. The checked-in 64-by-12
table and 12-entry start table encode the next cost state, minimum-cost
increment, and predecessor gauges. Regenerate with `make_trellis_table.py`
or verify byte-for-byte with `make_trellis_table.py --check`; the C test
also recomputes every transition from the direct recurrence.

The existing `paired2` and one-gauge `paired2-gauge` arms remain controls.
This is a scalar-stage correctness and operation-count experiment, not an
automatic rho routing change or CPU speedup claim.

## Held-out gate

Use the earlier paired-lattice and global-gauge fixtures for development
only. Commit implementation, tests, fixture generator, and checker before
creating fresh 1,024-pair fixtures on `glv-j0-32` and `j0-56`. Freeze
input bytes and independent Python affine output digests before evaluating
any τ arm. Run `joint,paired2,paired2-gauge,paired2-trellis,
paired2-trellis,paired2-gauge,paired2,joint` serially on each curve.
Retain every raw trial and failure, preparation, bytes, recodings, pair
scores, τ steps, additions, digit rotations, gauge transitions, final
corrections, inversions, and exact replay. Cover zero and order boundaries,
identity, equal/opposite points, and cancellation in unit tests.

Only a host-level isolation receipt under AGENTS.md can support a CPU
wall-time speedup. A lower rotation count does not establish speed, and
academic novelty remains to be checked against prior work.
