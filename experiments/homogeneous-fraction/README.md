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
python3 relation_gate.py --attempts 128 --seeds 20260927 20260928 20260929 --repeats 2 --out relation_gate_results.json
python3 verify_relation_gate.py relation_gate_results.json
python3 probe_large.py --target-index 16 --timeout 20 --out relation_probe_results.json
python3 m83_feasibility.py
```

The [raw relation receipts](relation_gate_results.json) retain every target,
failed query, first novel row, coefficient vector, repeated row, rank
increment, phase timing, and process-startup-inclusive wall time. Here are
the three independent streams; each was timed twice in a fresh process.
The independent `ToyCurve/pdpkernel.c` audit replays **all 768 target
outcomes** and the 48 accepted point/rank certificates, and independently
checks the earlier `n=7,k=1` cofactor collapse.
The last column is the median of the two fully charged times divided by eight
new rows, in seconds:

| Seed | Targets | Verified-target hits | Misses | Hits with no new rank | Repeated coefficient rows | New rank / columns | Charged s / new row |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 20260927 | 128 | 16 | 112 | 8 | 73 | 8 / 8 | 0.174 |
| 20260928 | 128 | 23 | 105 | 15 | 221 | 8 / 8 | 0.170 |
| 20260929 | 128 | 23 | 105 | 15 | 184 | 8 / 8 | 0.166 |

The median across six runs is **0.166 s per independent row**, including
factor-base construction, pair-index construction, all unsuccessful attempts,
point verification, rank work, Python overhead, and process startup. This
direct point-table collector is the fastest **currently measured on this
exact fraction base**; a compiled same-base collector remains an open
baseline. A 2× win against this control alone would require at most
**0.083 s per independent row** on these matched streams. The target stream
and base digest must remain fixed.

The [bounded homogeneous attempt](relation_probe_results.json) selected a
known positive target at index 16 solely to diagnose solver feasibility.
Building its 98 tri-degree components and 39,001 rows took 14.6 s, and the
process timed out at 20 s during elimination. **No independent row was
obtained**, so cost per row and a speedup ratio are **null**. This selected
positive is a diagnostic, not an estimate of natural yield. The same
original fraction points and projected base are frozen for both methods;
the current component solver still needs exact-target, signed-point
extraction to enter the collection comparison.

At the user's higher-fidelity `n=83` curve, the independently checked
[`k=2` base audit](m83_feasibility.json) finds 43 original fraction points,
20 nonidentity cofactor-projected points, and 10 sign-folded columns. All
projected points pass the known prime-subgroup order check. For a uniformly
random subgroup query, even the **upper bound** from all ordered projected
three-tuples is only `20^3 / 2417851639230796216685689
= 3.31e-21`; no natural relations or rank were measured at `n=83`.
This particular small base cannot be the high-fidelity collection candidate.
It is a validity/coverage bound, not a solver extrapolation.

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

Source: Galbraith, Granger, Merz, Petit, [*On Index Calculus Algorithms for
Subfield Curves*, Section 5.2](https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf).
