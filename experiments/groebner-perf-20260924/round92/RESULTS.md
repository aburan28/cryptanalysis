# Reusable Macaulay layout results

Ring-only support reuse with fresh numeric pivots certifies all six changed
nonlinear pair-product controls. Fixed proof replay rejected these controls in
round91. The larger multiplier setting increases work, and the difficult MQ
families remain inconclusive under the declared limits. This is an engineering
prototype using established Boolean Macaulay construction, not a new asymptotic
algorithm. Every qualified or aggregate speedup field remains null.

The numerical source is `a7f1a789f010cc36e0934a8a6f1e235b49b6018a`.
Round62's packed F4 producer, round11's independent checker and round4's native
evaluation/interpolation engine are rebuilt from unchanged sources. Thirty-four
source bindings and eight local native libraries are retained. No numeric source
changed after the single predetermined diagnostic run.

## Frozen comparison and outcomes

The 14 families contain 28 coefficient-changing input systems. There is no
numeric training. Linear families use multiplier degree zero; nonlinear families
use degree one (`r1`) or two (`r2`). The six arms are fresh packed F4, fresh-layout
r1, reused r1, reused r2, interpreted Boolean F5B and native evaluation/interpolation.
All start from identical full-support packed ANF. Layout preparation is separate
for reused arms; fresh-layout construction and destruction are included in that
arm's query. Input generation and fixture packing are outside every algebra call.

Across one copy of the 28 inputs, reused r1 accepts 20 proposals and falls back on
eight; reused r2 accepts 18 and falls back on ten. All ten linear controls, six
pair-product controls and four small field/reverse-inclusion controls pass r1.
The extra two r2 fallbacks are the 21-variable pair-product inputs, which exhaust
the matrix work allowance. The random-eight and 12/16/21-variable dense-MQ
families account for the other eight fallbacks. A fallback is not itself a win:
all dense-MQ F4/Macaulay arms remain inconclusive under the frozen budgets.

The signature comparator now attempts through 12 variables; its two dense
12-variable inputs time out at the declared two-second limit. Evaluation now
attempts through its native 20-variable bound, including an independent uncached
certificate above 12. It solves the 16-variable planted MQ controls, where the
F4/Macaulay arms remain inconclusive. The signature comparator is interpreted
Boolean F5B with optional runtime CFFI disabled, not the fastest available F5.
The evaluation engine retains its 256-root cap; unsupported results are explicit.

The optimized/UBSan correctness panel has 336 query records and 28 layout
preparations: 232 verified, 44 unsupported and 60 other unsuccessful records.
The diagnostic panel has 1344 records and 14 preparations, including 336 warmup
records and 1008 observations in six balanced orders: 928 verified, 176 unsupported
and 240 other unsuccessful. The audits independently verify 59 distinct
mathematical outputs and require exact fresh/reused r1 proof and counter equality
for all 56 control pairs and 224 diagnostic pairs. Failures are never removed.

## Exploratory complete algebra calls

Median ± median absolute deviation of six observations on a shared Apple host,
in milliseconds. The interval includes fresh coefficient decoding, all numeric
proposal and fallback work, independent certification, and basis/proof export.
It does not include input construction, curve checks or target-DLP recovery.
Host-wide isolation is unverified; these descriptive observations are not
qualified speedups. Identical r1/r2 linear algorithms can differ in local timings.

| Input 0 | Fresh F4 | Fresh layout r1 | Reused r1 | Reused r2 |
| --- | ---: | ---: | ---: | ---: |
| triangular-21 | 0.2227 ± 0.0097 | 0.0600 ± 0.0018 | 0.0509 ± 0.0024 | 0.0507 ± 0.0017 |
| triangular-64 | 2.0995 ± 0.0162 | 0.1688 ± 0.0117 | 0.1491 ± 0.0186 | 0.1351 ± 0.0048 |
| pair-products-6 | 0.0293 ± 0.0024 | 0.0280 ± 0.0015 | 0.0188 ± 0.0006 | 0.0207 ± 0.0001 |
| pair-products-12 | 0.1001 ± 0.0045 | 0.0937 ± 0.0104 | 0.0380 ± 0.0033 | 0.1133 ± 0.0037 |
| pair-products-21 | 0.0729 ± 0.0014 | 0.1962 ± 0.0233 | 0.0728 ± 0.0022 | 1.2212 ± 0.0411 |
| random-8-budget-control | 8.7424 ± 0.0611 | 9.0934 ± 0.0644 | 8.9717 ± 0.0718 | 12.4786 ± 0.0756 |

The linear 64-variable r1 candidate exports 127 derivation nodes and uses 15351
checker-work units for input 0; the F4 output costs 27117 checker-work units.
These are easy linear controls. No degree-of-regularity result follows.
For 21-variable pair products, building the full support/scatter map costs more
than the retained-layout call, while r2 adds an exhausted proposal before F4.
No automatic routing is justified by these measurements.

The negative MQ results identify a verification bottleneck: input 0 at 12/16
variables costs approximately 18.95/83.20 ms in the reused-r1 complete call, yet
neither verifies. Incomplete candidates cause 870680/2866539 checker-work units
before charged fallback. Fresh F4 also fails under the fixed limit, and its
shorter failure duration is not a solve-time win. Evaluation independently
finishes those two inputs in approximately 1.02/1.32 ms. All 21-variable dense-MQ
arms remain unsuccessful or explicitly unsupported. The complete 168-cell table,
including both inputs, all six observations and failures, is in
[results/summary.json](results/summary.json).

## Validation, failures and publication

Nine optimized/UBSan test groups cover 96 full-multiplier random small-ring
comparisons, changed nonlinear coefficients through 21 variables, linear bit-63
controls, zero/unit ideals, 65/128/130-equation bitsets, work/checker/proof/row/layout
limits, malformed ABI recovery, result lifetime after layout destruction, exact
fresh/reused traces and 48 calls from threads. Accepted bases also pass independent
Python derivation/completion checking and small-ring exhaustive controls.

The first development test run passed eight groups and failed a test that paired
`max_rows=1` with the incompatible default `batch=64`. Correcting the test to
`batch=1` fixed the harness without changing native code. That failed test source
and log remain archived. The subsequent frozen build, all tests, controls,
negative controls and diagnostic panel pass. Twenty-one artifact corruptions and
25 additional synthetic publication predicates are rejected. The synthetic
publication fixture uses the control portion of the local receipt; it is clearly
labelled and is not evidence of hosted CI execution.

The publication workflow rebuilds on Ubuntu 24.04 and macOS 15. The coordinator
waits for round91's verified merge, then opens this round's PR and requires full
repository CI, audited push/PR native artifacts, unchanged tested base/head/tree
and resolved review gates before merging. The publication scripts and local PR
status snapshot are retained. Hosted CI and a verified merge are pending; no
cross-platform performance or isolation claim is made from local evidence.
