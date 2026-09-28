# Measurement contract for IC candidate proposals

The unit of comparison is one verified discrete logarithm in the same source
subgroup and resource envelope. A proposal is not an experiment result.
Promote a proposal to a final `IC1...h...` ID only after materializing an exact
base and complete method manifest, resolving all stage interfaces, and, for
`ISO1`, verifying the linked isogeny route. Keep raw runs keyed by
`(candidate_id, workload_id, run_id)` as required by `AGENTS.md`.

The **primary** workload is one previously unseen public target point after
reusable factor-base, index, and factor-log precomputation is ready. Its
headline is verified IC online wall time paired with verified rho online wall
time on the same point and resource conditions:
`online_speedup = rho_online_wall_ns / IC_online_wall_ns`. The online clock
includes all target-dependent queries and failed attempts through recovery
and independent scalar replay. If evaluating a precomputed isogeny map on the
target is needed, charge that target-dependent transport in `target_query`.
Keep target-independent construction in separately reported cold/setup phases.
Multi-target and amortized results are secondary.

## Freeze the comparison before timing

For every matched cell, freeze the source curve and subgroup, field encoding,
base recipe, one public target point, target and control seeds, cache state, query
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
The analyzer's `verified_within_budget_query_rate` counts timeouts as queries
that did not finish within the declared limit. It measures operational
completion at that limit, not mathematical decomposition coverage.

## Exclusive measurements by stage

| Stage | Raw counters and artifacts | Reported comparison |
| --- | --- | --- |
| Curve and route setup | Field/curve validation, source and codomain IDs, explicit map, kernel and subgroup certificates, conductor proof status, map construction and transport cost | Verified route cost and transported `G,Q`; otherwise route is blocked. |
| Factor base | Candidate x values, lifts, subgroup checks, actual distinct `B`, base digest, signed/Frobenius orbit count, initially known logs, build operations/time, retained bytes and RSS | Cost to build and size of *usable* base; compare coverage at matched source targets. |
| PDP encoding and solve | Summation/chain form, Boolean unknowns/equations, degree, FFD/DoR for algebraic frontier claims, CNF variables/clauses, SAT conflicts or Macaulay rows, setup/encode/solve/extract/lift/replay times, cache hits, statuses, memory | Cost and verified completion probability per ordinary query, with censored attempts retained. |
| Relation collection | All attempted ordinary targets, verified witnesses, false lifts, duplicate and dependent rows, useful rank increments, coefficient RHS checks, query cost and rank trajectory | Coverage, conditional solve rate, novel-row rate at frozen rank checkpoints, charged cost per useful row and time to required rank. |
| Relation matrix LA | Exact matrix digest, modulus `r`, rows, columns, nonzeros, rank, solver/version, build cost, solve operations/time, memory, verified factor logs | Matched complete matrix solve cost; keep PDP Macaulay LA separate. |
| Target descent and recovery | Independent holdout targets, failed descent attempts, recursive PDP costs, recovered scalar and `[k]G=Q` certificate | Verified completion fraction and incremental per-target cost. |
| Whole pipeline | Five exclusive target-online phases, one exact target, verified scalar and paired rho time; cold setup and calibrated operations separately | Primary `rho_online_wall_ns / IC_online_wall_ns`; cold `S=C_total/sqrt(r)` and operation ratios are supplementary when fully priced. |

At a fixed row space, the diagnostic expected cost per new row can be written
`mean_attempt_cost / (p_coverage * p_solve_given_coverage * p_novel_given_solved)`.
Measure all three probabilities on the same ordinary-query stream and row
checkpoint. If any denominator is zero or censored, report a bound or `null`,
not a finite point estimate. The row space changes during collection, so
integrate observed costs along the rank trajectory for end-to-end collection
cost. Charge construction, failed attempts and matrix work separately; do not
reuse this local formula as a complete speedup.

Save one JSON object per run in a `.jsonl` file. The version-2 machine contract in
[`measurement_contract_v2.json`](measurement_contract_v2.json) fixes five exclusive
online target phases and eleven supplementary cold operation phases, along
with required provenance and counts. Include both
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
target-descent attempts in the raw target trace and charge their cost only to
the `target_descent` phase to avoid double counting.
For a complete DLP, `target_count` is one, `precomputation_ready` is true,
`target_point_sha256` identifies the exact public point, all five target-online
phase times sum exactly to `online_wall_ns`, and the scalar certificate and
verified paired `rho_online_wall_ns` are required. Incomplete runs retain
partial online times but cannot claim a speedup. Cold operation totals are
optional supplementary measurements; if supplied, every cold phase must be
priced and sum exactly to the total. [`analyze.py`](analyze.py) validates these
rules before reporting rates or a paired online speedup.

The [version-1 contract](measurement_contract.json) remains valid for earlier
receipts, including `accounting_mode: "verified_online_wall"`. That mode
requires a same-point rho measurement and scalar replay while keeping
unmeasured operation counts, operation ratios, and amortization null.
`analyze.py` selects the validator by schema version; one input file must
contain only one version.

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
source-curve setup in cold cost, but charge evaluation of the map on the one
public target to its online interval. For a secondary multi-target claim,
name the number of source targets sharing setup.

## Analysis and promotion

Use matched baseline/candidate inputs and resources. For rates, give numerator,
denominator, a binomial interval or block bootstrap interval, and the count of
censored cases. For costs, report all observed paired runs and a 95% paired
confidence interval; state whether it includes no improvement. Never average
only successful solves or erase a timeout. The primary complete-DLP comparison
uses paired one-target online wall time; calibrated operations, cold cost, and
peak memory are separate diagnostics. A component win is a stage result; a
full IC win requires equal verified DLP workloads, exact online boundaries,
and a paired rho online result. Extrapolated
N131 costs remain predictions until measured with the complete pipeline.
