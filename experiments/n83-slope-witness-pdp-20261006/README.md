# N83 affine slope-witness point-decomposition pilot

This stage experiment uses the same exact binary curve, normal-basis W3/W4
factor selector, measured projected factor base, public target fibers, and
CryptoMiniSat resource envelope as the
[indexed-factor pilot](../n83-indexed-factor-pdp-20261006/README.md).
The complete IC pipeline is not frozen, so `candidate_id` remains `null`.

For each nonzero factor abscissa `x`, the circuit introduces a free `y` and
enforces `y² + xy = x³ + 1`. For each regular addition of points `P` and `Q`,
it introduces a free slope `s`, requires `x(P) != x(Q)`, and enforces

```
s * (x(P) + x(Q)) = y(P) + y(Q)
x(P+Q) = s² + s + x(P) + x(Q)
y(P+Q) = s * (x(P) + x(P+Q)) + x(P+Q) + y(P)
```

These equations eliminate the inversion and half-trace Boolean circuits.
The solver formulation still excludes zero-abscissa factors and equal-x
additions. This is an explicit coverage limit; an UNSAT result on this circuit
would not prove that the target has no five-factor group decomposition.

The [frozen protocol](protocol.json) pins the source fixture, factor-base
representatives, solver binary, one-thread 120-second internal cap, one-million
conflict cap, 900-second external process-tree cap, and 2 GiB RSS cap. The
[stage reconciler](compare_slope_costs.py) charges every completed bounded
attempt by exclusive circuit-build, XCNF-write, solver, inner-residual, and
outer-residual wall phases. It keeps a separate sandbox process-inspection
failure row. Source and runtime hashes accompany each measurement. Host CPU
contention makes wall comparisons exploratory.

## Correctness controls

The [small-field test](test_slope_witness_circuit.py) exhausts all finite
targets for a fixed pair of distinct factor abscissae over `GF(2^5)`:
four reachable targets have verified SAT/group models, 39 unreachable targets
are rejected, and equal-x additions are rejected by the regular-locus guard.

The N83 planted mask-only and fully pinned solver controls both returned
`BOUNDED_UNKNOWN` under the internal cap. The separate [known-witness evaluator](replay_known_witness.py)
assigned every Boolean gate from the planted five raw factor points and
implied slopes, verified all CNF and XOR constraints, and passed independent
[checked-Sage replay](sage_replay_slope.py) of the five points, measured base
membership, regular additions, raw fiber, and subgroup target. This proves
that the exact N83 circuit admits that witness. It supplies no SAT search
cost or ordinary-query yield estimate.

## Promotion boundary

The four ordinary raw fibers are preimages of **one** public subgroup target.
They are not four independent queries for estimating natural yield. A
verified ordinary relation would permit a next rank/collector experiment;
without it, useful-row cost is unknown. The primary objective remains one
previously unseen target with complete IC scalar recovery and independent
replay, paired against rho on that same point under an isolated CPU receipt.
No stage timing in this directory is an IC online speedup.
