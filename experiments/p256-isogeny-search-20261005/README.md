# P-256 isogeny search

This experiment turns a proposed search for exceptional curves in the NIST
P-256 isogeny class into a reproducible experiment. It separates structural
facts, reusable discovery work, per-instance mapping cost, and Pollard-rho walk
speed instead of treating scalar-multiplication benchmarks as ECDLP results.

## First structural result

For P-256,

```text
t = p + 1 - n
D_pi = t^2 - 4p
     = -455213823400003756884736869668539463648899917731097708475249543966132856781915
```

The repository contains and verifies the complete factorization

```text
|D_pi| =
  3
  * 5
  * 456597257999
  * 1428624589419343516204097
  * 46523541035814968339936406074986559003387.
```

The factors are distinct and their primality is checked with recursive
Pocklington certificates and deterministic 64-bit Miller-Rabin leaves. Since
`D_pi` is a fundamental discriminant,

```text
Z[pi] = O_K.
```

Consequently every curve in the `F_p`-isogeny class has the same maximal
endomorphism order. There are no vertical volcano levels to explore. The CM
field is neither `Q(sqrt(-3))` nor `Q(i)`, excluding `j = 0`, `j = 1728`, and
extra geometric automorphisms. A non-scalar endomorphism has norm at least
`ceil(|D_pi|/4)`, a 256-bit lower bound, so a useful low-degree GLV-style
endomorphism is also excluded.

The remaining search is therefore a horizontal class-group search for:

- an explicit low-cost path from P-256;
- measurable constant-factor arithmetic improvements; or
- evidence for a genuinely non-generic ECDLP algorithm.

Absence of such a result in a finite traversal is not proof that none exists.

## Frozen exploratory result

The protocol and first run were developed together, so the frozen run is
**retrospective and exploratory**, not a held-out speed experiment. The exact
structural conclusions do not depend on host timing. On the unisolated initial
host, five baseline trials averaged 139,559 canonical rho iterations/s with a
nominal 95% interval of 137,887–141,232 iterations/s. This is a Python control
measurement only. No isogenous candidate was timed, no mapping cost was
measured, and no ECDLP speedup is claimed. The toy control recovered scalar
4242 in 55 iterations.

The frozen artifacts are in [`results/initial`](results/initial), the experiment
contract is [`protocol.json`](protocol.json), and the run accounting is
[`receipt-initial.json`](receipt-initial.json). Verify them with:

```bash
python scripts/verify_frozen.py
```

## Sage depth-one result

A SageMath 10.6 run on 2026-10-06 retained six explicit horizontal neighbors:
one each of degrees 3 and 5, and two each of degrees 11 and 13. All have
geometric automorphism order 2. A seven-trial, order-balanced rho comparison
found no significant speedup; every neighbor's paired 95% interval contained
`1.0`. The largest point estimate was `1.028x` with interval
`0.971x–1.089x`.

The full candidate maps, raw forward/reverse order-bias diagnostics, corrected
benchmark, and claim limits are frozen in
[`results/sage-depth-one-20261006`](results/sage-depth-one-20261006). This is a
six-neighbor depth-one result, not an exhaustive class-group search, and path
evaluation was not timed in that run. The later mapping follow-up below measures
it for the strongest retained candidates.

## Depth-two and depth-three follow-up

The next run reached 24 curves through depth two and 56 through depth three.
All 17 new depth-two neighbors were screened in order-balanced blocks. One
unadjusted screening interval barely excluded `1.0`, but a fresh 20-trial,
two-second holdout rejected it and the other two screening leaders. No holdout
interval excluded `1.0`; no candidate advances.

The 32 new depth-three curves retained verified explicit paths and exposed no
exceptional automorphisms. They were not subjected to another non-isolated
Python timing sweep because the complete depth-two screen and holdout found no
reproducible effect. Raw registries, screening blocks, holdout results, costs,
class-number computation failures, and claim limits are frozen in
[`results/sage-depth-three-20261006`](results/sage-depth-three-20261006).

## Widened one-hop result

A complementary direct-neighbor scan covered every ramified or split prime
degree through 47. It added 14 curves beyond the depth-three registry and
brought the combined explicit total to 70 unique curves. All 14 new one-hop
curves were screened in balanced P-256 control blocks; no paired 95% interval
excluded `1.0`. The best estimate was `1.026x` with interval
`0.996x–1.057x`, so no holdout was triggered.

The registry, raw timing blocks, receipt, and verifier are frozen in
[`results/sage-wide-depth-one-20261006`](results/sage-wide-depth-one-20261006).
Across the three Sage runs, 37 distinct neighbors have now been timed. Per-key
evaluation for the strongest screening candidate is included in the follow-up.

## Mapping-cost and native follow-up

The three depth-two holdout leaders and the strongest widened one-hop point
estimate were evaluated end to end through their retained maps. Mapping both
`P` and `Q` cost 0.65–0.97 ms per public key in Sage, or fewer than 681
iterations of the measured native rho kernel. Reusable map parsing cost less
than 0.19 seconds for each selected path.

A matched native comparison then put P-256 and all four candidates on the same
fixed-limb Montgomery field code, complete general-`a` projective formulas,
64-way batch normalization, and native scalar-coefficient tracking. Fifteen
one-second trials per curve found no significant speedup: every paired 95%
interval contained `1.0`. The largest point estimate was `1.0031x`, with
interval `0.9847x–1.0217x`.

The raw mapping and native results, exact cost boundaries, receipt, and claim
limits are frozen in
[`results/sage-mapping-20261006`](results/sage-mapping-20261006). This focused
retest closes the per-key accounting gap for four leaders; it does not make the
70-curve traversal exhaustive over the isogeny class.

## Full retained-registry native screen

The same native backend then screened the remaining 65 explicitly reached
neighbors in 11 root-controlled, position-balanced blocks. Two unadjusted
screening intervals excluded `1.0`, for degree-17 and degree-23 paths. A fresh
30-trial, two-second holdout rejected both: their paired estimates were
`1.0069x` (CI `0.9923x–1.0217x`) and `1.0030x` (CI
`0.9879x–1.0183x`).

Combining this screen with the focused four-curve panel, all 69 retained
non-root curves now have matched native measurements and none has a
reproducible advantage. The complete block artifacts, holdout, receipt, and
verifier are frozen in
[`results/sage-native-full-screen-20261006`](results/sage-native-full-screen-20261006).
This covers the explicit 70-curve registry, not the entire isogeny class.

## Complete one-hop enumeration through degree 199

Every ramified or split rational prime degree through 199 is now explicitly
enumerated. The standard division-polynomial route exhausted an 8 GiB PARI
stack at degree 137, but a lower-memory modular-polynomial method reproduced
the legacy degree-103 maps exactly and recovered both explicit neighbors at
every remaining degree. Peak RSS was about 293 MiB. The combined registry now
contains 98 curves.

The 28 additions beyond degree 47 were all screened with the matched native
backend. No paired 95% interval triggered a holdout, so all 97 retained
non-root curves now have native measurements and no reproducible speedup
remains. The completed registries, superseded stack-overflow tracebacks,
modular-method regression check, native screens, receipt, and verifier are in
[`results/sage-wide-depth-one-199-20261006`](results/sage-wide-depth-one-199-20261006).
This is complete for the classified degrees through 199, not for larger prime
degrees or the entire isogeny class. Per-key evaluation of the new maps was not
timed.

## Low-degree paths through depth five

The complementary cheap-path search now covers every curve first reached in at
most five horizontal steps of degrees 3, 5, 11, and 13. It contains 168 curves;
deduplication against the 98-curve prior union contributed 112 new neighbors
and raised the combined explicit registry to P-256 plus 209 distinct neighbors.

All 112 additions received root-controlled matched-native rho measurements.
Six unadjusted 0.5-second screening intervals triggered a fresh 30-trial,
two-second holdout. None reproduced: the largest holdout estimate was `1.0153x`
with paired 95% interval `0.9945x–1.0366x`. Thus all 209 retained non-root
curves have now been measured in the matched native backend, with zero
reproducible speedups.

The registry, all explicit paths, 19 screening blocks, holdout, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-five-20261006`](results/sage-low-degree-depth-five-20261006).
This is a depth-five result for four low degrees, not a full class-group
enumeration. Per-key evaluation of the added paths was not timed.

## Resumed low-degree paths through depth seven

The frozen depth-five frontier was resumed through depths six and seven without
duplicating prior candidate records. It added 176 curves—80 at depth six and 96
at depth seven—with no overlap against the prior 210-curve union. The combined
explicit registry now contains P-256 plus 385 distinct neighbors.

All additions were screened with the matched native backend while pinned to a
CPU separate from the concurrent class-group computation. One unadjusted screen
hit triggered a fresh 30-trial, two-second holdout and did not reproduce: its
estimate was `0.9886x` with paired 95% interval `0.9628x–1.0151x`. All 385
retained non-root curves now have native measurements and zero reproducible
speedups.

The delta registry, 30 screening blocks, holdout, receipt, and verifier are
frozen in
[`results/sage-low-degree-depth-seven-20261006`](results/sage-low-degree-depth-seven-20261006).
This remains a bounded low-degree traversal, not the entire isogeny class, and
per-key map evaluation was not timed for the additions.

## Resumed low-degree paths through depth nine

The depth-seven frontier was next extended through depths eight and nine. It
added 240 curves—112 at depth eight and 128 at depth nine—with no overlap
against the prior 386-curve union. The combined explicit registry now contains
P-256 plus 625 distinct neighbors.

All additions were screened on the CPU-separated matched native backend. Six
unadjusted screening hits triggered a fresh 30-trial, two-second holdout. None
reproduced: the largest holdout estimate was `1.0312x` with paired 95% interval
`0.9975x–1.0660x`. All 625 retained non-root curves now have native
measurements and zero reproducible speedups.

The delta registry, 40 screening blocks, holdout, receipt, and verifier are
frozen in
[`results/sage-low-degree-depth-nine-20261006`](results/sage-low-degree-depth-nine-20261006).
This remains a bounded low-degree traversal, not the entire isogeny class, and
per-key map evaluation was not timed for the additions.

## Resumed low-degree paths through depth eleven

The next extension reached 144 curves at depth ten and 160 at depth eleven,
with no overlap against the prior 626-curve union. The combined explicit
registry now contains P-256 plus 929 distinct neighbors, each with its complete
ordered path, edge maps, short-model isomorphisms, and transported generator.

All 304 additions received CPU-separated matched-native measurements. Eight
unadjusted short-screen hits entered a fresh 30-trial, two-second holdout, and
none reproduced. The largest holdout point estimate was `1.0220x` with paired
95% interval `0.9918x-1.0531x`; all 929 retained non-root curves now have
native measurements and zero reproducible iteration-rate improvements.

The delta registry, 51 screening blocks, holdout, typed transfer assessment,
receipt, and verifier are frozen in
[`results/sage-low-degree-depth-eleven-20261006`](results/sage-low-degree-depth-eleven-20261006).
This remains a bounded traversal over degrees 3, 5, 11, and 13. The default
exact class-group computation continues separately, and its unsuccessful and
running attempts are recorded in
[`results/sage-class-group-20261006/attempts.json`](results/sage-class-group-20261006/attempts.json).
Per-key map evaluation was not timed for the 304 additions, and the ordinary
host does not satisfy the repository's isolation gate for a promoted timing
claim.

## Resumed low-degree paths through depth thirteen

The next extension added 176 curves at depth twelve and 192 at depth thirteen,
again with no overlap against the prior union. The combined explicit registry
now contains P-256 plus 1,297 distinct neighbors, all with complete ordered
paths and transported generators.

All 368 additions received matched-native measurements in 62 root-controlled
blocks. Sixteen unadjusted short-screen hits entered a fresh 30-trial,
two-second holdout, and none reproduced. The largest holdout point estimate
was `1.0179x` with paired 95% interval `0.9920x-1.0445x`; all 1,297 retained
non-root curves now have native measurements and zero reproducible
iteration-rate improvements.

The delta registry, raw blocks, holdout, transfer assessment, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-thirteen-20261006`](results/sage-low-degree-depth-thirteen-20261006).
This is still a bounded degree-3/5/11/13 traversal. The exact class-group job
remained active after more than seven hours when this stage was frozen, and
per-key map evaluation was not timed for the 368 additions.

## Resumed low-degree paths through depth fifteen

The next two shells added 208 curves at depth fourteen and 224 at depth
fifteen, with no overlap against the prior union. The combined explicit
registry now contains P-256 plus 1,729 distinct neighbors.

All 432 additions received matched-native measurements in 72 root-controlled
blocks. Seven unadjusted short-screen hits entered a fresh 30-trial,
two-second holdout, and none reproduced. The largest holdout estimate was
`1.0151x` with paired 95% interval `0.9878x-1.0431x`; all 1,729 retained
non-root curves now have native measurements and zero reproducible
iteration-rate improvements.

The delta registry, raw blocks, holdout, transfer assessment, receipt, and
verifier are frozen in
[`results/sage-low-degree-depth-fifteen-20261006`](results/sage-low-degree-depth-fifteen-20261006).
This is still a bounded degree-3/5/11/13 traversal. The exact class-group job
remained active after more than eight hours when this checkpoint was frozen,
and per-key map evaluation was not timed for the 432 additions.

## Class-wide model eligibility audit

A deterministic follow-up closes several standard arithmetic-model loopholes.
Every curve in the class has the same odd prime group order, with no rational
two- or three-torsion. Consequently no member has an `F_p` Montgomery or twisted
Edwards model, and exceptional short-Weierstrass coefficients would require the
already-excluded `j = 0` or `j = 1728`.

Because `p = 3 mod 4`, every nonzero short-Weierstrass `a` is `F_p`-isomorphic
to a model with `a = 1` or `a = 3`. P-256 itself has a verified map from
`a = -3` to `a = 1`, so small-`a` specialization is not a neighbor-only
advantage. Replaying the normalization over the depth-seventeen delta verified
all 497 models and transported generators: 245 map to `a = 1` and 252 to
`a = 3`.

The unchanged native benchmark also has no candidate-dependent formula branch:
each timed complete addition performs the same three full multiplications by
`a` and two by `3b`. The certificate, source hash, typed obligations, and claim
limits are frozen in
[`results/model-eligibility-20261006`](results/model-eligibility-20261006).
This rules out those standard model shortcuts, not unknown formula families or
non-generic ECDLP algorithms.

## Resumed low-degree paths through depth seventeen

The next extension added 240 curves at depth sixteen and 256 at depth seventeen,
with no overlap against the prior union. The combined explicit registry now
contains P-256 plus 2,225 distinct neighbors, each with its ordered path, edge
maps, model isomorphisms, and transported generator.

All 496 additions received matched-native measurements in 83 root-controlled
blocks. Eight unadjusted short-screen hits entered a fresh 30-trial, two-second
holdout. None reproduced. The largest holdout point estimate was `1.0097x` with
paired 95% interval `0.9899x-1.0300x`; all 2,225 retained non-root curves now
have native measurements and zero reproducible iteration-rate improvements.

The registry, 83 raw screening blocks, holdout, candidate-model audit, failure
ledger, transfer assessment, receipt, and verifier are frozen in
[`results/sage-low-degree-depth-seventeen-20261006`](results/sage-low-degree-depth-seventeen-20261006).
The first launch failed before Sage import because Docker `vfs` storage filled
the writable layer; the exact traceback and successful CPU-separated recovery
are retained. This remains a bounded degree-3/5/11/13 traversal, not the whole
isogeny class. The exact class-group job remained active after more than 9.6
hours at this checkpoint, and per-key map evaluation was not timed for the 496
additions.

## Full-registry normalized-coefficient audit

The complete 2,226-curve retained union was reconstructed from fourteen frozen
candidate registries and normalized to the certified `a = 1` or `a = 3` models.
Every fourth-root certificate and transported generator verified. The audit then
ranked the normalized `3b` constant used twice by each complete addition.

P-256's normalized coefficient has 251 bits, popcount 125, and a binary
double-and-add bound of 374 field additions/doublings. The smallest retained
coefficient still has 243 bits, giving an unavoidable addition-chain lower bound
of 242 operations. The best binary bound is 352 operations, and the minimum
popcount is 100. Consequently zero curves pass the conservative 32-operation
gate for implementing a coefficient-specialized native formula.

The full metrics, input hashes, cost model, receipt, summary, and verifier are
frozen in
[`results/coefficient-cost-audit-20261007`](results/coefficient-cost-audit-20261007).
No wall-time speedup is claimed: this is a deterministic eligibility screen, and
no candidate advanced to a native benchmark. It closes the retained-registry
small-constant route, not other coordinate systems, formula families, deeper
paths, or unknown algorithms.

## Quick start

Python 3.11 or newer is required.

```bash
cd experiments/p256-isogeny-search-20261005
python -m pip install -e .
p256-isogeny run --output-dir runs/latest --seconds 1 --trials 3
```

The run creates:

- `structural-report.json`: exact invariants and eliminated structures;
- `benchmark.json`: repeated rho iteration measurements with a 95% interval;
- `toy-rho.json`: a completed small-curve collision and recovered logarithm;
- `summary.md`: a compact human-readable report.

To independently rediscover the discriminant factorization rather than verify
the checked certificate:

```bash
p256-isogeny analyze --refactor
```

This can take several minutes.

Run the tests with:

```bash
python -m unittest discover -s tests -v
```

## Horizontal exploration with SageMath

The first useful rational prime degrees are classified from the Kronecker
symbol `(D_pi / ell)`. Up to 13:

- `3, 5` are ramified and give one horizontal direction;
- `11, 13` split and give two horizontal directions;
- `2, 7` are inert and give no horizontal edge.

With SageMath installed:

```bash
sage -python scripts/explore_sage.py \
  --ells 3,5,11,13 \
  --depth 2 \
  --max-nodes 100 \
  --output data/candidates/generated/depth-2.json

sage -python scripts/benchmark_interleaved.py \
  --candidates data/candidates/generated/depth-2.json \
  --seconds 2 \
  --trials 7 \
  --output runs/sage/benchmark.json
```

Each candidate retains:

- its short-Weierstrass coefficients and mapped P-256 generator;
- every edge degree and kernel polynomial;
- the isogeny and model-isomorphism rational maps;
- elapsed reusable discovery time and total path degree;
- a separate placeholder for the two per-instance map evaluations.

The `P-256 Sage horizontal search` GitHub Actions workflow exposes the same search as
a manual, parameterized job and uploads both candidates and benchmark results.

## Interpreting the benchmark

The reference implementation runs parallel `r`-adding walks. It batch-normalizes
their projective points with one inversion per batch, ensuring that partition
choices depend on canonical affine `x` and define a legitimate rho iteration.
For a prime-order group its generic expected work is reported as

```text
sqrt(pi*n/2)
```

before automorphism quotients. Candidate speed is compared using the identical
walk and repeated wall-clock trials. The comparative script warms every
candidate, rotates execution order so a full block puts every curve in every
timing position, and reports a paired Student-t interval for each per-trial
log-rate ratio against P-256. The security change attributable to a
constant-factor rate difference is `log2(candidate_rate / baseline_rate)` bits.

The benchmark intentionally reports these cost categories separately:

1. discovery and reusable precomputation;
2. per-instance evaluation of the explicit path on `P` and `Q`;
3. ECDLP walk iterations on the candidate.

An end-to-end P-256 speedup must include all three. The Python implementation is
control code, not a claim about the fastest available P-256 attack; serious
candidates should be reproduced in an optimized constant-quality backend.

## Repository layout

```text
src/p256_isogeny_search/   exact analysis, curve arithmetic, rho harness
data/candidates/           versioned candidate/path interchange files
scripts/explore_sage.py    explicit horizontal path explorer
scripts/benchmark_mapping_sage.py  retained-map P,Q cost benchmark
tests/                     structural and collision regression tests
../../suite/examples/p256_isogeny_native_bench.rs  matched native rho benchmark
../../.github/workflows/   path-scoped CI and manual Sage exploration
```

## Scope

This is cryptanalytic research tooling. It does not implement signing, key
generation, or production cryptography. The in-tree elliptic-curve arithmetic
is variable-time and must not process secrets in a real system.

This experiment complements the broader Rust profiler in
[`suite/src/cryptanalysis/p256_structural.rs`](../../suite/src/cryptanalysis/p256_structural.rs).
That module covers twist and extension-field structure; this experiment adds a
certified complete Frobenius-discriminant factorization, explicit horizontal
path retention, and separate discovery/mapping/ECDLP cost accounting.
