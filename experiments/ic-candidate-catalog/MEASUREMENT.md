# Measurement contract for IC candidate proposals

The primary unit of comparison is one previously unseen, verified discrete
logarithm in the same source subgroup and resource envelope. The headline is
measured online wall time for that public target after reusable IC preparation,
paired with a verified rho solve of the same point. A proposal is not an experiment result.
Promote a proposal to a final `IC1...h...` ID only after materializing an exact
base and complete method manifest, resolving all stage interfaces, and, for
`ISO1`, verifying the linked isogeny route. Keep raw runs keyed by
`(candidate_id, workload_id, run_id)` as required by `AGENTS.md`.

## Freeze the comparison before timing

For every matched cell, freeze the source curve and subgroup, field encoding,
base recipe, target distribution, target and control seeds, cache state, query
and resource caps, operation calibration, code hashes, rho reference, and
success criterion. A factor-base comparison may vary the base recipe, but
its source curve and workload remain the same. A solver comparison fixes the
base, summation-polynomial or chained-S3 formulation, Boolean equations, and
input instances. If the formulation changes, compare the complete PDP stage,
including encoding and lifting, and label it as a method change. An isogeny
comparison fixes the **source** DLP and
counts transport plus all work on the codomain. Use independent holdouts
after choosing a survivor; preserve failed, timed-out, and OOM runs.

Use ordinary uniform nonzero subgroup points for relation-yield estimates.
Planted positive instances check completeness and lifting, but do not estimate
natural yield. Exhaustive small-field or certified UNSAT controls can assess
false positives; a timeout is censored, not UNSAT. Report result counts by
`sat`, `verified_decomposition`, `proved_unsat`, `timeout`, `budget`, `error`,
and `lift_rejected`, with the exact denominator and confidence interval.

## Exclusive measurements by stage

| Stage | Raw counters and artifacts | Reported comparison |
| --- | --- | --- |
| Curve and route setup | Field/curve validation, source and codomain IDs, explicit map, kernel and subgroup certificates, conductor proof status, map construction and transport cost | Verified route cost and transported `G,Q`; otherwise route is blocked. |
| Factor base | Candidate x values, lifts, subgroup checks, actual distinct `B`, base digest, signed/Frobenius orbit count, initially known logs, build operations/time, retained bytes and RSS | Cost to build and size of *usable* base; compare coverage at matched source targets. |
| PDP encoding and solve | Summation/chain form, Boolean unknowns/equations, degree, FFD/DoR for algebraic frontier claims, CNF variables/clauses, SAT conflicts or Macaulay rows, setup/encode/solve/extract/lift/replay times, cache hits, statuses, memory | Cost and verified completion probability per ordinary query, with censored attempts retained. |
| Relation collection | All attempted ordinary targets, verified witnesses, false lifts, duplicate and dependent rows, useful rank increments, coefficient RHS checks, query cost and rank trajectory | Coverage, conditional solve rate, novel-row rate at frozen rank checkpoints, charged cost per useful row and time to required rank. |
| Relation matrix LA | Exact matrix digest, modulus `r`, rows, columns, nonzeros, rank, solver/version, build cost, solve operations/time, memory, verified factor logs | Matched complete matrix solve cost; keep PDP Macaulay LA separate. |
| Target descent and recovery | Independent holdout targets, failed descent attempts, recursive PDP costs, recovered scalar and `[k]G=Q` certificate | Verified completion fraction and incremental per-target cost. |
| One-target online result | Target query, PDP including failed attempts, relation check, descent, scalar replay; same-point rho interval and certificate | Verified `rho_online_ms / IC_online_ms` with all five exclusive target phases summing to the IC interval. |
| Whole pipeline, supplementary | Every exclusive phase above, setup/cache policy, orchestration, failed attempts, total calibrated operations and wall time | Cold `S=C_total/sqrt(r)`, ratio to fixed theoretical rho and floor, and baseline/candidate total-cost ratio, clearly separate from online speed. |

At a fixed row space, the diagnostic expected cost per new row can be written
`mean_attempt_cost / (p_coverage * p_solve_given_coverage * p_novel_given_solved)`.
Measure all three probabilities on the same ordinary-query stream and row
checkpoint. If any denominator is zero or censored, report a bound or `null`,
not a finite point estimate. The row space changes during collection, so
integrate observed costs along the rank trajectory for end-to-end collection
cost. Charge construction, failed attempts and matrix work separately; do not
reuse this local formula as a complete speedup.

Save one JSON object per run in a `.jsonl` file. The machine contract in
[`measurement_contract.json`](measurement_contract.json) fixes the eleven
exclusive operation phases, required provenance and counts. Include both
`proposal_id` and `candidate_id` keys, with exactly one non-null; use the
final candidate ID for a complete DLP. `workload_fixture_sha256` hashes the
shared source curve/target workload and excludes candidate-specific base or
code choices, so a factor-base experiment can still pair on it. Each run has
an independent `pair_block_id`, status, `wall_ns`, peak RSS, subgroup order,
per-phase operation and wall-time counts (integer or `null`), PDP attempts and
outcomes, `total_operations`, and `rho_operations`. PDP outcome counts must
sum to the number of attempts; recorded phase times must fit inside total
wall time. For a stage or incomplete run, `total_operations` is null.
Every run links to `isogeny_route_ref`; a search-only route cannot support a
complete DLP record.
The required PDP counts describe ordinary relation-query attempts. Keep
target-descent attempts in the raw target trace and charge their cost to the
five online target phases exactly once.
For a complete DLP, every phase is priced, the total equals their sum, and
the scalar certificate is required. [`analyze.py`](analyze.py) validates these
rules before reporting rates or a paired speedup.

## Cross-regime normalization

The common receipt schema is not permission to mix incomparable operation units.
Binary extension-field `ic-bench` receipts use calibrated reference picoseconds
(`rps`); `ca-ic prime --solver orbit` receipts use counted affine group
operations. A prime receipt maps its logarithm-database oracle/probe work to the
common `precompute` phase and its ordered descent oracle/probe work to
`target_descent`; common phases that the native prime ledger does not separately
charge are zero and the native report is retained. Do not convert those zeros
into claims that the physical work was free.

Across field regimes compare dimensionless quantities against a matched control:
one-target IC/rho for one-target work and IC/folded-shared-DP-rho for batches.
Absolute `total_operations` values may be compared only when `operation_unit`
and the calibration/accounting definition match. Prime candidates use the
`IC1P<b>C...` namespace defined in `AGENTS.md` and must bind the exact modulus,
target points, automorphism quotient, executable hash, startup commit, and all
algorithm-affecting options in their manifests/receipts.

## Many-target control

For T targets on one curve, report shared precomputation separately from the
ordered marginal target costs and retain exact prefix points at T=1,2,4,... .
The independent baseline `T * rho_one_target` is useful for showing setup
amortization, but it is not the fair many-target opponent. Also report a
shared-distinguished-point rho expectation. For N equivalence classes use

`sqrt(pi*N/2) * sum_{k=0}^{T-1} C(2k,k)/4^k`,

which tends to `sqrt(2*N*T)`. When the IC candidate folds an automorphism group,
use the same quotient in N for the strict rho control (for the binary Koblitz
sign/Frobenius benchmark, N=r/(2n)). State setup/detection-lag assumptions.
Never call a crossover against independent per-target rho a many-target
algorithmic win when the shared-DP rho control still wins.

A batch receipt must make it possible to distinguish fixed setup amortization
from a change in marginal target work. If descents learn across targets, record
the ordered learning state and compare against a no-learning control. If they
do not, say so explicitly; a decreasing total/T alone is then only setup
amortization.

## Isogeny activation gate

An `isogeny_routes.json` search record is a task, not a usable route. To
activate one, add each exact codomain curve node and directed edge with
degree `ell`, explicit map artifact and digest, kernel order/check,
homomorphism tests, subgroup order check, and certificates that transported
`G` retains order `r` and transported `Q` is the image of the source target.
Record dual/composition checks when available. For an `ell` that divides `r`,
prove the source subgroup does not meet the kernel before transporting a DLP.
Record the endomorphism-order conductor and `v_ell` level as proved, unknown,
or inapplicable on **both** endpoints. Only then bind a route's ordered edge
IDs and issue an `ISO1` candidate ID. Include map discovery/building and
transport in cold cost; for a warm claim, name the number of source targets
sharing that setup.

## Analysis and promotion

Use matched baseline/candidate inputs and resources. For rates, give numerator,
denominator, a binomial interval or block bootstrap interval, and the count of
censored cases. For costs, report all observed paired runs and a 95% paired
confidence interval; state whether it includes no improvement. Never average
only successful solves or erase a timeout. Compare the verified one-target
online wall time to measured same-point rho first; retain calibrated cold
operations, stage costs, and memory as supplementary diagnostics. A component
win is a stage result. Extrapolated N131 costs remain predictions until
measured with the complete pipeline.
