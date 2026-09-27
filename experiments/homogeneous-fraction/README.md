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
abscissa. Neither fraction base here is a demonstrated Frobenius-invariant
torus base for ECC2K-130; no relation-matrix rank, recovered DLP, comparison
with rho, degree-131 solve, or scaled F4/F5 speedup has been measured.

## Next discriminating experiment

Use a **compiled multigraded F4 or F5 backend** on the same valid fraction
ideal, eliminating zero-denominator and zero-block components without giving
either arm a toy-only enumerated membership polynomial. Record actual
multidegree matrix supports, solving degree, peak memory, preprocessing,
verified independent relations, and failed attempts at `k=2` and eventually
the paper's `n=17` panel. A genuine gain must beat an optimized ordinary
solver on the *same* valid ideal and lower cost per verified independent
relation before transfer to the phase-aware ECC2K base.

Source: Galbraith, Granger, Merz, Petit, [*On Index Calculus Algorithms for
Subfield Curves*, Section 5.2](https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf).
