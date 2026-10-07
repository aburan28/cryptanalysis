# Global unit gauge for the paired prime-field τ stream

## Frozen hypothesis

The j=0 order-three unit action `phi(x,y)=(beta*x,y)` commutes with the
Jacobian τ map and group addition. Therefore, for a digit stream evaluating
`aP+bQ`, applying the same `phi^k` to every nonzero digit evaluates
`phi^k(aP+bQ)`. Undoing `phi^k` once on the final affine x coordinate
returns the original point. This gives three equivalent orientations of
the same joint stream, with no new prepared points or scalar recodings.

Add a separate `paired2-gauge` research arm. It uses the paired2 search's
same two axial lattice representatives per nonzero scalar and scores up
to four stream pairs. For each pair, count the digits whose unit power is
0, 1, or 2. For `k=0,1,2`, the modeled rotations are the number of digits
whose shifted power `(power+k) mod 3` is nonzero, plus one final inverse
rotation if `k` is nonzero. Choose the lowest fixed point-work score
`6*tau_steps + 11*mixed_adds + rotations`; retain the paired2 tie rules,
with the smallest `k` winning an exact tie. The final inverse rotation is
charged in the measured rotation counter when the output is nonidentity.

This is a correctness and operation-count hypothesis, not a CPU speedup
or academic novelty claim. The existing `joint` and `paired2` arms remain
unchanged. Reuse the 1,104-byte joint table. Count recodings, pair scores,
selected representatives, selected nonzero gauges, τ steps, mixed adds,
rotations, and output inversions.

## Experiment order and claim gate

Use the prior paired-lattice held-out panel only for development. Freeze
the new source and checker before generating a different 1,024-pair
fixture per study curve (`glv-j0-32`, `j0-56`). First record independent
generic input and output digests; then run `joint, paired2,
paired2-gauge, paired2-gauge, paired2, joint` serially on each curve.
Preserve failures, exact output replay, source and fixture hashes, and
all point-work counters. Include zero, order-boundary, UINT64_MAX,
identity, equal-point, opposite-point, and cancellation unit controls.

Any local CPU wall time is exploratory under AGENTS.md. A controlled
wall-time ratio requires the strict host-level isolation receipt in
`docs/ISOLATED_BENCHMARKS.md`. A smaller rotation count alone is not a
speedup claim. The single-target rho workload remains the primary
end-to-end gate after this scalar-stage diagnostic.
