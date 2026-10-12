# Bounded, checked chain pruning for sparse Boolean F4

This opt-in experiment avoids ordinary critical pairs only when it has a valid
chain representation. It builds on round13's cached sparse producer. The native
round11 checker and the independent Python round5 checker remain unchanged.
Earlier adapters and application dispatch are unchanged. All numeric state is
local to one computation; no target answers are cached.

The experiment implements an established Buchberger chain criterion, not a new
F5 signature algorithm or an asymptotic F6 result. See Christian Eder,
[Predicting zero reductions in Gröbner basis computations](https://arxiv.org/abs/1404.0161),
for the distinction between standard representations, zero reductions and
signature criteria.

## Criterion and resource bounds

Installed basis rows remain immutable until the critical-pair queue is exhausted.
For a pair `(i,j)`, search the first 64 basis leaders for a bridge `k` dividing
their LCM. Both child LCMs must be proper divisors of the parent LCM. That is a
conservative search policy, not a proof that either child is dispensable.

The parent is skipped only when both child pairs have LCM-bounded representations.
Such a representation is known from an actual zero S-polynomial, the coprime
product criterion, a previously established chain, or an explicit reduction to
zero against the current basis. Merely processing or queuing a child is
insufficient. A successful reduction to zero in the Boolean quotient lifts to
an ordinary-ring representation with the implicit field relations: square-free
reduction only introduces smaller monomials. Multiplying the two child
representations by their LCM quotients and adding gives the parent representation.
All Boolean field pairs are still processed. The final checker independently
verifies both ideal inclusions, reducedness, ordinary pairs and field pairs.

At most two new reductions are probed per parent. Each gets at most 4,096 charged
producer work units, within the remaining global budget. An RAII guard restores
the global limit and removes unreferenced scratch proof nodes on every exit.
Consumed work is never rolled back. A soft probe limit falls back to ordinary
processing; a true global work or proof-node failure remains inconclusive.

Failed probes are remembered only at the exact current basis size, so basis
growth allows another attempt. The represented and failed caches each hold at
most 65,536 entries. Full caches fall back without certifying unknown pairs.
Telemetry is thread-local and reset on every API call. Logical cache operations
are charged; these internal work units are not an IC operation metric.

## Ablations and checks

The build provides `prior`, `disabled`, `probe`, `cached`, `tiny_probe` and
`tiny_cache`, each optimized and with UBSan. `disabled` must match the prior
producer's exact proof and integer trace. `cached` uses only already established
representations. The tiny variants exercise soft probe exhaustion and cache
saturation.

Tests cover randomized Boolean ideals, nonzero bridge counterexamples, mandatory
field pairs, zero/unit ideals, cancellation, masks through 64 variables, 513 work
limits, proof/row/batch limits, fresh calls and concurrent callers. Six direct
native controls cover 65 work boundaries near `UINT64_MAX` and nine proof-node
boundaries, including exception cleanup and basis-growth invalidation. Successful
small systems also pass an independent truth/staircase oracle.

`screen.py` retains all 92 rows of the 23 frozen round13 inputs and checks every
successful basis with both independent checkers. `profile_phases.py` separately
instruments exclusive charged-work phases. Every instrumented proof, status and
original integer counter must match the screen. Profiling is not timing evidence.

The row-normalization profile motivated the separate round56 matrix-output
experiment. Its `run_validation.py` rebuilds and audits both rounds on each CI
platform; see [round56](../round56/README.md) for reproduction and results.
