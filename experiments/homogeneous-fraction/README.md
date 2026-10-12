# Block-filtered fraction equations: a measured pilot

This is a **PDP-stage toy experiment**, not a complete index-calculus candidate
or an ECC2K-130 attack. `candidate_id` is intentionally null. It asks whether
retaining the three numerator/denominator blocks reduces the work in a Boolean
Macaulay/XL solver for the cleared fourth Semaev equation. The construction and
curve model come from the earlier homogeneous-fraction audit; this folder has a
standalone copy of its `math_model.py` generator.

## Reproduce

Python 3.10+ and the standard library suffice:

```sh
python3 block_fraction_solver.py --repeats 3 --output block_fraction_results.json
```

The captured result uses Python 3.12.14 on x86-64. Each arm runs in a fresh
process with a 45-second limit; target order is fixed and arm order alternates
between repeats. The result JSON contains every attempt, including negative
targets, separate per-process peak RSS, matrix rank, row/column counts, exact
root audit, curve oracle, search nodes, and timings. `total_solver_seconds`
starts inside the worker and includes equation expansion, matrix assembly,
elimination, and the target search/verification. It excludes subprocess
startup, the exhaustive correctness audit, and independent curve oracle; the
excluded times are reported separately.

For each `n`, the field is in polynomial basis: `0x83` for n=7 and `0x805`
for n=11. The curve is `y^2 + xy = x^3 + 1`, with three fraction blocks,
`k=1`, and four coefficient bits per block. The generator expands the cleared
S4 equation in the Boolean quotient and independently evaluates it on 100
random coefficient assignments. The ten input equations are `n` descended
coordinates plus three polynomial denominator-nonzero conditions. All three
arms use **the same input ideal**, target, variable order, verification, and
exact Boolean depth-first search:

- `block`: enumerate multiples whose **output monomials** have at most three
  active coefficients in **each** of the three blocks; construct a GF(2)
  Macaulay matrix, eliminate, and pass consequences of total degree <=3 to
  the exact search.
- `total`: same construction and elimination, with output total degree <=9;
  thus it allows all three-block profiles of that total degree.
- `direct`: run the exact search without constructing a Macaulay matrix. It is
  a tiny-instance control, not a proposed asymptotic IC solver.

The cap `(3,3,3)` admits **every** input equation; the program aborts if any
cap would exclude one. A preceding pilot with `(3,3,2)` was rejected because
it excluded every Semaev coordinate equation. The reported runs use only the
corrected cap. The original cleared expression is formally multihomogeneous
of block degree `(4,4,4)` before Boolean reduction. Field equations `x²+x`
break strict grading; this implementation uses its surviving **block-degree
filtration**, not a multigraded F4/F5 algorithm on a saturated homogeneous
ideal. Matrix rows are polynomial multiples in the Boolean quotient, and
the extracted consequences are rechecked against **all 4,096 assignments**.

## Measured results

Numbers are medians of three isolated repetitions, in seconds; RSS is peak
MiB rounded to one decimal. `roots` are original Boolean roots / roots that
also give an actual signed curve relation. Negative targets are charged.

| n | target x | roots | direct s | block s | total s | total/block | block rows / cols | total rows / cols | block / total RSS MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 1 | 216 / 108 | 0.020 | 1.319 | 2.734 | 2.07 | 2,345 / 3,363 | 5,456 / 4,017 | 14.4 / 20.0 |
| 7 | 50 | 0 / 0 | 0.340 | 2.473 | 3.408 | 1.38 | 2,056 / 3,356 | 3,116 / 4,017 | 13.9 / 15.6 |
| 11 | 679 | 12 / 12 | 0.232 | 3.339 | 4.323 | 1.29 | 2,068 / 3,368 | 3,001 / 4,017 | 14.3 / 14.9 |
| 11 | 702 | 0 / 0 | 0.430 | 3.232 | 4.433 | 1.37 | 2,037 / 3,356 | 3,307 / 4,017 | 14.1 / 17.0 |

The ranks and exact roots are in the JSON. Both matrix arms found verified
relations on the two positive targets and exhausted the two negative targets.
The block arm reduced matrix work and RSS. It barely altered the exact search:
for the four targets the block and total arms explored the same 13, 989, 240,
and 705 nodes. The direct control explored 13, 1,037, 248, and 721 nodes,
respectively, but was **faster than both matrix arms**. Thus the pilot finds a
real matrix-filtration saving, **not an end-to-end relation-search gain**.

The `n=7, target=1` example also shows why a raw polynomial root is not a
relation: 108 of its 216 roots failed independent signed point addition. All
reported success statuses require a real point triple summing to the target
abscissa. A subsequent **subgroup audit changed the interpretation of this
pilot**: the `n=7,k=1` fraction set has three curve points, all of which
project to the identity under the cofactor 4. The point sums above create
**zero useful subgroup columns or independent IC rows**. They remain correct
PDP arithmetic checks, not index-calculus relation yield. Neither fraction
base here is a demonstrated Frobenius-invariant torus base for ECC2K-130;
no recovered DLP, comparison with rho, degree-131 solve, or scaled F4/F5
speedup has been measured.

## A strict homogeneous lift and an explicit component solver

`strict_multigraded.py` lifts every Boolean S4 coordinate polynomial to
formal tri-degree `(4,4,4)` with three separate homogenizers. Its homogeneous
field equations are `x_j^2+x_j*h_i`; its denominator equations exclude zero
denominators. Macaulay2 saturates by `h_0*h_1*h_2` and runs F4. The `multi`
and `total` arms pass the **same generators and monomial order**, differing
only in whether the ring records three degrees or one. `run_strict_multigraded.py`
checks the *entire affine Boolean root set*, a separate curve relation oracle,
and the tri-degrees of the computed multi-arm basis.

The reproducible Macaulay2 1.22 action
[`strict-homogeneous`](https://github.com/aburan28/cryptanalysis/actions/workflows/strict-homogeneous.yml)
completed eight runs on `n=5,k=0`: two repeats each for a positive target 0
(four Boolean roots and four verified roots) and a negative target 2 (zero
roots). F4 CPU medians, in milliseconds, were **1.67 multi / 1.38 total**
for target 0 and **0.98 multi / 0.96 total** for target 2. Saturation CPU
medians were **13.38 multi / 4.68 total** and **10.26 multi / 4.75 total**.
Macaulay2's available trace did not expose F4 matrix partitions, so the
grading annotation by itself establishes **no measured block exploitation**.
The generated scripts, logs, and per-run JSON are uploaded by the action.
The formal lift specializes exactly to the same Boolean equations at `h_i=1`,
but it is the lift of Boolean-reduced S4, not an assertion about the original
unreduced project's homogeneous ideal.

The separately bounded `n=7,k=1` positive/negative panel timed out in all
four arms after 60 seconds per arm **before F4**. The graded arm printed its
22-generator input count but no saturation-complete marker; the total arm did
not print even the input count. Its [timeout receipts](strict_n7_timeouts.json)
and generated inputs/logs are retained. This experiment therefore cannot
support an `n=7` F4 speed comparison. The costly panel runs only on a manual
workflow dispatch.

`homogeneous_components.py` explicitly performs component-wise GF(2)
Macaulay elimination in the homogeneous quotient `x_j^2=x_j*h_i`. Each row
has an exact three-component degree. `split` reduces one degree component
at a time; `flat` reduces **identical degree-tagged rows and columns**
together. Both dehomogenize the same consequences, run the same exact search,
and independently check every Boolean root and signed curve relation. This
is a bounded XL experiment and **not a full multigraded F4**.

Reproduce the isolated three-repeat panel with:

```sh
python3 homogeneous_components.py --repeats 3 --output homogeneous_component_results.json
```

These are local Python 3.12 median total solver seconds, with the exhaustive
audit and independent oracle timed separately. Positive and negative attempts
both count:

| n / k | target | components / rows | split s | flat s | flat / split | maximum columns, split / flat |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 / 0 | 0 | 34 / 123 | 0.0056 | 0.0065 | 1.17 | 23 / 252 |
| 5 / 0 | 2 | 34 / 177 | 0.0080 | 0.0108 | 1.34 | 27 / 320 |
| 7 / 1 | 1 | 117 / 3,079 | 0.2295 | 2.1893 | 9.54 | 482 / 12,056 |
| 7 / 1 | 50 | 117 / 3,079 | 0.5686 | 2.5544 | 4.49 | 730 / 12,304 |

Ranks, consequence hashes, exact root sets, search nodes, and relation checks
agree arm by arm; the raw receipts are in
[`homogeneous_component_results.json`](homogeneous_component_results.json).
The saving comes from shorter bit vectors and smaller back-elimination loops.
An optimized sparse ungraded solver could discover these disconnected
supports on its own. The prior direct-search control still wins: 0.020 s on
`n=7,target=1` and 0.340 s on `n=7,target=50`. Thus this explicitly
measures the homogeneous blocks, **without demonstrating an index-calculus
speedup**.

## First subgroup-valid relation gate

`relation_gate.py` fixes the exact Koblitz curve over `F_(2^13)` with
modulus `0x2027` and prime subgroup order **2,003** (curve order 8,012).
The `k=2` fraction x-set lifts to 35 curve points. Multiplication by the
cofactor 4 produces **16 distinct nonidentity subgroup points**, or eight
columns after sign folding. The baseline builds a complete table of 630
unordered point pairs, then processes *ordinary uniform nonzero subgroup
targets*. It verifies exact signed point addition, the S4 equation, the
projected point equation, and rank over `F_2003`. Duplicate and dependent
rows are charged. The target fixture's scalar is used to generate an ordinary
query and label its right-hand side; it never supplies a witness.

```sh
python3 relation_gate.py --attempts 128 --target-rank 8 --seeds 20260927 20260928 20260929 --repeats 2 --out relation_gate_results.json
python3 verify_relation_gate.py relation_gate_results.json
python3 relation_gate.py --attempts 128 --target-rank 0 --seeds 20260927 20260928 20260929 --repeats 2 --out relation_yield_results.json
python3 verify_relation_gate.py relation_yield_results.json
python3 probe_large.py --target-index 16 --timeout 20 --out relation_probe_results.json
python3 probe_large.py --target-index 16 --timeout 60 --out relation_probe_completed.json
python3 verify_probe.py relation_probe_completed.json
python3 compiled_control.py --out compiled_control_results.json
python3 verify_relation_gate.py compiled_control_results.json
python3 factor_base_yield.py --out factor_base_yield_results.json
python3 compiled_k3_control.py --out compiled_k3_control_results.json
python3 verify_k3_control.py
python3 probe_k3_homogeneous.py --seed 20260927 --target-index 0 --timeout 60
python3 verify_homogeneous_bitset.py --out homogeneous_bitset_exact_intersection_verification.json
python3 probe_k3_homogeneous_targetonly.py --seed 20260927 --target-index 0 --timeout 60 --deduction-degree 8 --out k3_homogeneous_targetonly_degree8_results.json
python3 probe_k3_homogeneous_targetonly.py --seed 20260927 --target-index 0 --timeout 60 --deduction-degree 9 --out k3_homogeneous_targetonly_degree9_results.json
python3 goal_check.py --baseline compiled_control_results.json --probe relation_probe_completed.json --out goal_status_k2_refreshed.json
```

The [primary collection receipts](relation_gate_results.json) stop **as soon
as rank reaches eight**. A fixed-length 128-target
[yield audit](relation_yield_results.json) retains every later duplicate and
dependent row as a separate diagnostic, but its post-completion work is not
charged to the primary time-to-rank metric. Both files preserve the frozen
target stream, every executed attempt, coefficient vectors, phase timing and
process-startup-inclusive wall time. The independent
`ToyCurve/pdpkernel.c` replay checks **282 primary and 768 yield-audit
target outcomes**, all 96 accepted point/rank certificates, and the earlier
`n=7,k=1` cofactor collapse.

| Seed | Attempts to rank 8 | Misses before rank 8 | Charged s / new row | Full 128-query hits / misses / dependent | Repeated coefficient rows in full audit |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20260927 | 65 | 57 | 0.127 | 16 / 112 / 8 | 73 |
| 20260928 | 43 | 35 | 0.109 | 23 / 105 / 15 | 221 |
| 20260929 | 33 | 25 | 0.105 | 23 / 105 / 15 | 184 |

Each seed was timed twice in a fresh process. The median primary cost across
six runs is **0.111 s per independent row**, including factor-base and
pair-index construction, all failed attempts *before required rank*,
point verification, rank work, Python overhead and process startup. This
Python collector is an archival reference; the compiled collector below is
the fastest **currently measured on this exact base**. Fix the same
rank-eight stopping rule, target stream and base digest for each arm.

## Compiled controls and factor-base yield sweep

[`factor_base_yield.py`](factor_base_yield.py) constructs the same rational
fraction bases for `n=13,53,83` at `k=2,3,4`. It checks the field moduli by
Rabin's irreducibility test, uses the Koblitz Lucas recurrence for the full
curve order, records a primality certificate for each prime subgroup order,
and checks `[r]([h]P)=O` for every distinct nonidentity projected point. The
exact points and hashes are in
[`factor_base_yield_results.json`](factor_base_yield_results.json). `n=53`
is a screening curve; `n=83` remains the required higher-fidelity check.

| n | k | Fraction x-values | Original lifted points | Projected nonidentity points B | Sign-folded columns | Ordered-triple upper bound B^3/r |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 13 | 2 | 32 | 35 | 16 | 8 | 2.04 |
| 13 | 3 | 128 | 115 | 56 | 28 | 87.7 |
| 13 | 4 | 512 | 467 | 226 | 113 | 5.76e3 |
| 53 | 2 | 32 | 19 | 8 | 4 | 2.43e-11 |
| 53 | 3 | 128 | 131 | 64 | 32 | 1.25e-8 |
| 53 | 4 | 512 | 523 | 260 | 130 | 8.35e-7 |
| 83 | 2 | 32 | 43 | 20 | 10 | 3.31e-21 |
| 83 | 3 | 128 | 131 | 64 | 32 | 1.08e-19 |
| 83 | 4 | 512 | 563 | 280 | 140 | 9.08e-18 |

The final column is only a loose upper bound on the chance that a uniformly
random subgroup target is the sum of some ordered triple from the projected
base. It is **not** an observed relation rate. Even the `n=83,k=4` base is
far too small to support a collection comparison; no `n=53` or `n=83`
ordinary-target collector was run.

The compiled [`direct_collector.c`](direct_collector.c) now builds both the
`n=13,k=2` and `n=13,k=3` bases. [`compiled_k3_control.py`](compiled_k3_control.py)
uses the **same fixed subgroup generator, exact target points and six frozen
target streams** as the refreshed `k=2` compiled control. It charges C base
and pair-index construction, process launch and input, target misses,
repeated/dependent rows, C exact checks and rank updates, Python parsing, and
an independent point/S4/projected-row replay for every accepted row. The
compiler cost is separate. All 48 `k=3` accepted rows pass the independent
pure-Python replay in [`verify_k3_control.py`](verify_k3_control.py).

| Seed | k=2 attempts / misses | k=2 ms per row | k=3 attempts / misses | k=3 ms per row | k=2 / k=3 cost ratio |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20260927 | 65 / 57 | 5.735 | 8 / 0 | 1.217 | 4.71 |
| 20260928 | 43 / 35 | 4.034 | 8 / 0 | 1.246 | 3.24 |
| 20260929 | 33 / 25 | 3.395 | 8 / 0 | 1.273 | 2.67 |

Each seed has two fresh-process repetitions. The k=2 values are refreshed
medians over the two repetitions; the k=3 values use the same rule. The global
median is **4.03 ms per row at k=2** and **1.237 ms per row at k=3**. Every
`k=3` run reached signed rank eight in eight ordinary targets with zero misses;
the first stream also contained one repeated row and one additional dependent
row. This shows a useful **base-yield effect** on these small screening streams.
It does not show a homogeneous-solver speedup: both arms use the direct point
pair collector and the factor base changed. The `k=3` same-base baseline sets
the provisional 2× ceiling at **0.618 ms per new row** for a homogeneous
candidate, before the paired 95% bootstrap gate.

## Bounded homogeneous extraction on the k=3 base

[`probe_k3_homogeneous.py`](probe_k3_homogeneous.py) takes an ordinary first
target from the frozen streams, builds target-specific homogeneous S4 rows,
reduces them by three-block degree, searches the resulting consequences, and
independently checks any extracted signed points against the exact curve sum,
S4 equation, cofactor projection, and rank-one signed row. Its per-target
budget is 60 seconds.

The degree-5 target-equation matrix attempt timed out during equation/row
construction at the 60-second cap, before producing a complete matrix or a
signed point triple. The raw log and censored receipt are in
[`k3_homogeneous_degree5_raw`](k3_homogeneous_degree5_raw/) and
[`k3_homogeneous_degree5_results.json`](k3_homogeneous_degree5_results.json).
A preceding cap-4 calibration built 79,720 rows in 61 components in 24.4 s,
then timed out during elimination; its matrix did not multiply the S4
coordinate equations, so it is not a solver result. Both attempts have zero
independently verified relations and **null cost per row**. A timeout is
censored work, not an UNSAT result.

For the matched k=3 direct baseline, the six-run median is **1.237 ms per new
row**; the seed-20260927 paired median is **1.217 ms per row**, so its 2×
screening ceiling is **0.608 ms per row**. None of the homogeneous attempts
returned one verified relation within its 60-second target budget. Therefore
there is no rank-eight candidate run, speedup, full relation-collection
estimate, final relation-matrix linear algebra, or DLP cost.

### Packed degree-one homogeneous layer

[`probe_k3_homogeneous_bitset.py`](probe_k3_homogeneous_bitset.py) tests a
degree-one Macaulay layer on that same first ordinary target. It uses the
Boolean-reduced S4 coordinate equations at tri-degree `(4,4,4)`, then
multiplies them by the constant and each of the 24 coefficient variables. The
result is reduced in four separate components: `(4,4,4)`, `(5,4,4)`,
`(4,5,4)`, and `(4,4,5)`. Denominator constraints stay in exact search and
independent replay. [`homogeneous_bitset.py`](homogeneous_bitset.py) packs
monomial supports as bit vectors, and [`monomial_degree_order.c`](monomial_degree_order.c)
orders columns by total degree and then monomial mask before component
reduction.

The earlier conservative extractor selected only low-degree rows already
present in a reduced basis. Those cutoff-five and cutoff-seven runs built
1,800,555 Boolean terms in about 9.4 s, reduced 325 rows across four
components, and found no such basis rows. Their exact source is preserved in
[`homogeneous_bitset_conservative_v1.py`](homogeneous_bitset_conservative_v1.py).

The current extractor computes the **exact row-space intersection** with the
low-degree monomial subspace by eliminating the high-degree projection. With
cutoff seven it built and reduced the same 325 rows in 5.68 s after equation
construction; with cutoff eight it took 6.11 s. Both matrices have rank 325,
1,952,064 tagged columns, and zero high-projection dependencies, so the
degree-one row space has no nonzero consequences supported through degree
eight. Peak RSS was 691,380 KiB and 702,720 KiB, respectively. A third
cutoff-eight run passed **only the target point** into the worker; it also
found zero consequences and timed out during exact search. These receipts are
[`k3_homogeneous_exact_intersection_degree7_results.json`](k3_homogeneous_exact_intersection_degree7_results.json),
[`k3_homogeneous_exact_intersection_degree8_results.json`](k3_homogeneous_exact_intersection_degree8_results.json),
and
[`k3_homogeneous_targetonly_degree8_results.json`](k3_homogeneous_targetonly_degree8_results.json).
The point-only cutoff-nine run timed out before row construction completed;
that cell is censored, with no matrix rank or relation result, in
[`k3_homogeneous_targetonly_degree9_results.json`](k3_homogeneous_targetonly_degree9_results.json).

The compiled direct control independently accepts this ordinary target as a
new relation, so the timeout is a solver failure, not evidence that the
target has no decomposition. Earlier workers also received the fixture scalar
as output metadata, although their equation builder and search did not read
it. Only the final target-only receipts are eligible for a strict no-key
comparison. No attempt returned signed points within 60 seconds, so the cost
per verified relation remains null.

| Attempt | Last complete stage | Built rows | Peak RSS | Charged result |
| --- | --- | ---: | ---: | --- |
| [Sparse degree-one rows](k3_homogeneous_degree1_results.json) | 325 rows in four components | 325 | 2,627,320 KiB | 60.102 s timeout during elimination |
| [Packed bitsets, numeric order, cutoff 4](k3_homogeneous_bitset_results.json) | matrix reduced, no deductions | 325 | 1,037,412 KiB | 60.065 s timeout during exact search |
| [Packed bitsets, numeric order, cutoff 5](k3_homogeneous_bitset_degree5_results.json) | matrix reduced, no deductions | 325 | 1,035,456 KiB | 60.065 s timeout during exact search |
| [Packed bitsets, graded order, cutoff 5](k3_homogeneous_graded_bitset_degree5_results.json) | matrix reduced, no deductions | 325 | 635,508 KiB | 60.067 s timeout during exact search |
| [Packed bitsets, graded order, cutoff 7](k3_homogeneous_graded_bitset_degree7_results.json) | matrix reduced, no deductions | 325 | 636,220 KiB | 60.067 s timeout during exact search |
| [Exact row-space intersection, cutoff 7](k3_homogeneous_exact_intersection_degree7_results.json) | exact high-degree projection, empty intersection | 325 | 691,380 KiB | 60.067 s timeout during exact search |
| [Exact row-space intersection, cutoff 8](k3_homogeneous_exact_intersection_degree8_results.json) | exact high-degree projection, empty intersection | 325 | 702,720 KiB | 60.024 s timeout during exact search |
| [Target-only exact intersection, cutoff 8](k3_homogeneous_targetonly_degree8_results.json) | point-only worker, empty intersection | 325 | 679,892 KiB | 60.064 s timeout during exact search |
| [Target-only exact intersection, cutoff 9](k3_homogeneous_targetonly_degree9_results.json) | monomial order ready; row construction incomplete | — | 112,616 KiB | 60.069 s timeout during matrix setup |

The first sparse-row wrapper run also failed while writing its raw log because
of a relative-path bug; it earned no relation credit, and its output was lost.
That harness failure is recorded in
[`k3_homogeneous_attempt_history.json`](k3_homogeneous_attempt_history.json).
[`verify_homogeneous_bitset.py`](verify_homogeneous_bitset.py) checks the fast
field arithmetic against the reference implementation, the graded monomial
permutation, packed multiplication, and component ranks. Its receipt is
[`homogeneous_bitset_exact_intersection_verification.json`](homogeneous_bitset_exact_intersection_verification.json).
The conservative verifier receipt is retained at
[`homogeneous_bitset_verification_conservative.json`](homogeneous_bitset_verification_conservative.json).

This is a measured homogeneous matrix stage, not a completed point-decomposition
solver. The matrix rows remained independent, the exact low-degree
intersections through degree eight were empty, and exact extraction consumed
the remaining budget. The gate stays closed; do not use these matrix timings
as relation-collection or final linear-algebra costs.

## Research goal and promotion rule

On a larger, subgroup-valid base, require **at least 2× less total charged
time per *new independent, verified* relation than the fastest matched
baseline**. Freeze ordinary targets, base, cofactor projection, subgroup
order, sign/orbit columns, cache policy and resource limit. Count all
construction, failed and timed-out attempts, repeated and dependent rows,
solving, exact point verification and rank updates. A timeout gives a
censored observation, not an UNSAT conclusion or a finite speedup. A
compiled, same-base collector must be included before promoting any
Python-only win. The `n=13` work is screening; high-fidelity confidence
requires a separate `n=83` valid base with nonnegligible natural coverage,
and any `n=131` claim requires its own validation.

**Current gate: not met.** Only after a paired relation-collection gain with
matched yield and rank should we add the full collection, final relation
matrix linear algebra, target descent, and rho costs in the style of Table 1.
An internal Macaulay-matrix elimination time must never occupy the final
relation-matrix LA column.

The [current k=3 goal status](k3_collection_goal_status.json) is
`not_evaluated_no_complete_rank8_candidate`. Its paired same-base direct
control median is **1.237 ms per new row**, so the candidate must stay at or
below **0.618 ms per row at the median**, with the paired 95% bootstrap lower
limit reaching 2×. The candidate receipt, per-seed speedups, and confidence
interval remain null because all bounded homogeneous probes were censored
before a verified relation. The refreshed k=2 control calculation is in
[`goal_status_k2_refreshed.json`](goal_status_k2_refreshed.json); its baseline
median is **4.034 ms per row** and its median 2× ceiling is **2.017 ms**.
[`goal_status.json`](goal_status.json) applies the refreshed per-seed control
timings to the matched-prefix receipts: every first candidate attempt exceeds
its revised per-seed 2× budget. Earlier status calculations remain in the
preceding commit history.

The existing `goal_check.py` independently replays the k=2 C relation/rank
receipts before evaluating a supplied candidate. The k=3 receipts have their
own independent Python replay and status record. Promotion still requires a
complete, same-base rank-eight candidate, matched target order and base hash,
and the paired bootstrap gate. An unsolved target remains a charged miss.

## Exact measurement source snapshot

The `C_source_sha256` and `monomial_order_source_sha256` values in the receipts bind the source bytes used during measurement. Those bytes match commit [`b437c7e4`](https://github.com/aburan28/cryptanalysis/commit/b437c7e4b5a875f3dbead4419eaaf541496a294d), also recorded as `measurement_source_commit` in the manifest. The follow-up applies the repository's clang-format output to the two C sources; control and bitset verifiers pass on the formatted files. Timing receipts remain tied to the hashed source snapshot.

Source: Galbraith, Granger, Merz, Petit, [*On Index Calculus Algorithms for
Subfield Curves*, Section 5.2](https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf).
