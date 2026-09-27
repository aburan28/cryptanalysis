# ECC2K-130 quotient pair-sum gate, 2026-09-26

This experiment supplies an exact four-point **stage** oracle on public toy
Koblitz curves and a separate degree-131 support bound. It has no complete
index-calculus candidate, recovered discrete logarithm, calibrated operation
comparison with rho, or demonstrated work below `2^61`. All receipts have
`candidate_id: null`; the measured query times are PDP diagnostics, not the
single-target IC online metric.

## What the quotient index does

For a sign- and Frobenius-closed factor base `F` in the prime-order subgroup,
let `H = {±Frob^j : 0 <= j < n}`. Choose one representative `P` of each
`H`-orbit of base points and enumerate `(P,Q)` for every `Q in F`. Canonicalize
the sum under `H`, storing one transformed pair witness per distinct sum
orbit. This is a **complete existence index**: for every original pair
`(A,B)`, one element of `H` takes `A` to its chosen representative and takes
`B` to another member of `F`. Its sum orbit is therefore in the index.

To query an ordinary subgroup point `R`, enumerate every `H`-transform of
each stored pair sum `S`, look up the canonical complement `R-S`, undo the
canonical transform on its stored witness, and replay all four points with
the curve law. A separate, unquotiented pair table checks the same target for
existence or exhaustive absence. The program aborts on any disagreement.

The base starts with all nonzero normal-basis `x` coordinates of weight at
most `w`, tests curve rationality, projects each point by cofactor four, and
includes both signs. It records the **actual distinct subgroup points** `B`
before folding, not the coordinate count. An optional first-`k` orbit cut
selects entire signed-Frobenius orbits, so closure and the completeness proof
still hold. The fixed workload draws nonzero scalars with seed `260926`,
multiplies one verified subgroup generator, and excludes fixture creation
from query timing. No scalar is recovered by index calculus.

## Frozen stage measurements

The degree-23 full and one-orbit rows have the same workload ID
`b8db2fa3dde1` and exactly the same 12 public target points. Each query has
an independent four-point curve-law replay when it hits. Misses exhaust the
quotient index and agree with the direct pair table. Index build time is
target-independent and separate from query time. Wall times below are medians
from one macOS Python 3.14.7 run, in milliseconds; they are not field-operation
counts or ECC2K-130 projections.
The [curve manifest](curve_manifest.json) records canonical field and curve
identities for all five measured degrees; the paired degree-23 curve is
`EC1N23Ckb1h4e0f4fecc64d`. The base policy is the controlled variable.

| Field, base | Actual `B` | Pair generators | Quotient keys | Direct keys | Quotient index build | Verified hits / queries | Quotient query median | Direct query median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2^13`, weight ≤1 | 26 | 26 | 11 | 261 | 3.8 | 3/3 | 1.9 | 0.1 |
| `2^19`, weight ≤2 | 190 | 950 | 427 | 16,189 | 706.4 | 3/3 | 0.8 | 2.1 |
| `2^23`, weight ≤2 | 276 | 1,656 | 811 | 37,261 | 2,645.2 | 12/12 | 49.0 | 3.9 |
| `2^23`, first weight-≤2 orbit | 46 | 46 | 21 | 921 | 42.0 | 0/12 | 396.5 | 49.1 |

The sparse degree-23 miss scans all `21 × 46 = 966` signed-Frobenius pair
variants per target. Each query performs 966 complement lookups and 22,701
counted Frobenius applications; the direct oracle performs 921 lookups. The
quotient table is much smaller, but repeated canonicalization makes this
implementation slower on the paired degree-23 toy queries. The full-base and one-orbit
hit fractions have broad two-sided 95% exact binomial intervals:
`12/12` gives `[0.735, 1]`, and `0/12` gives `[0, 0.265]`. These small,
selected toy cells do not estimate ECC2K-130 relation yield.

The [run receipts](runs) retain target points, workload IDs, the exact base
construction inputs and base/index digests, source hashes, all outcomes, build and query times, counted
group operations, serialized index bytes, and process peak RSS. Their query
times include all failed complement probes. The direct oracle is an exact
control over the enumerated toy base; it is not an independent DLP solver.
The separate [verification receipt](verification.json) reconstructs each
base from the recorded normal-basis elements, replays every target scalar
from the seed, checks subgroup membership and each four-point witness, and
rechecks every hit or miss through an independently built direct pair set.

## Bounded stage performance at degrees 53 and 83

The [performance probe](perf_probe.py) uses a type-II optimal normal basis,
the exact Koblitz `b=1` curve, and the first two rational weight-two normal-`x`
orbits after subgroup projection. It includes both signs, builds the **entire**
quotient index for this selected two-orbit base, and times three repeated
2,048-lookup prefixes on one ordinary subgroup target. These are deliberately
small bases: `B=212` at degree 53 and `B=332` at degree 83. The query prefix
does not exhaust the index and neither target was decomposed within it; zero
hits in a prefix give no coverage estimate. Cofactors are 428 and 4,
respectively. All target fixture generation and base/index construction are
outside query time.

| Degree | Selected `B` | Pair generators / quotient keys | Complete index build | Query median, 2,048 lookups | Median per lookup | Point adds / Frobenius / negations per lookup |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 53 | 212 | 424 / 207 | 586 ms | 1,968 ms | 0.961 ms | 1 / 53.5 / 54.5 |
| 83 | 332 | 664 / 327 | 1,727 ms | 3,469 ms | 1.694 ms | 1 / 83.5 / 84.5 |

The [n53](runs/n53_perf_prefix.json) and [n83](runs/n83_perf_prefix.json)
receipts retain three individual timings, counted operations, actual base
digests, index key counts, source hashes, target fixtures, and peak process
RSS. The independent [verification receipt](verification.json) reconstructs
both bases, checks subgroup projection and the fixture scalar, and confirms
the selected-base index is complete. The measured per-lookup times are
implementation and degree specific; the table is **not** a wall-time
extrapolation to degree 131. The operation counts confirm this implementation
uses roughly one point Frobenius map and one negation per degree per query
lookup, in addition to a point addition.

## Degree-131 support gate

The [support receipt](weight5_support_gate.json) computes the exact generous
cap for normal-basis `x` weight **at most five**:

```text
candidate x values ≤ Σ_{i=1..5} C(131,i) = 309,694,087
subgroup base points B ≤ 2 × candidate x values = 619,388,174
```

The cap grants every `x` a rational lift and both signs. Cofactor projection
cannot increase `B`. For one uniformly sampled point in the prime-order
subgroup of order
`r = 680564733841876926932320129493409985129`, at most `B^4`
ordered fourfold sums can be supported. Thus the probability of a direct
four-point decomposition from this fixed base is at most `B^4/r < 2^-12.17`,
even with a perfect summation solver. The union bound requires
`B ≥ 4,294,967,297` merely to permit **50%** one-query coverage; it does
not guarantee that coverage. Repeated ordinary relation queries may still
find hits, but every failed query must be charged to relation collection.

This bound applies only to the static weight-≤5 base. The larger proposed
Frobenius orbit-union or `u`-window bases are outside it. For a generic base
with `B` points, the quotient pair index still has about `B²/(4n)` keys
if pair sums occupy full signed-Frobenius orbits, and this query enumerates
up to about `B²/2` pair-sum transforms while canonicalizing each complement.
These are conditional size estimates, not lower bounds on algebraic methods
that share work across many pairs. A useful next solver must exploit such
shared structure and then pass ordinary-query PDP, relation-rank, and
single-target recovery gates.

## Estimated work for one ECC2K-130 discrete logarithm

The [work estimate](work_estimate.json) assigns an explicit unit to every
`2^x` number. It uses a frozen [pair-index audit receipt](pair_index_gate_report.json), whose completed toy DLP runs at degrees 37, 41, and 53 observed rank probes per row within about 3% of the random-support model `2r/B²`. Transferring that law to degree 131 is an **assumption**, and it applies to direct pair-index collection, not to a future algebraic summation solver. The n53/n83 stage timings above calibrate implementation throughput on those small bases only; they do not validate the degree-131 support law.

For `B` actual subgroup points and `K` folded relation columns, the model is:

```text
pair-complement probes per useful relation ≈ 2r/B²
rank-collection probes, if every hit is novel ≈ K × 2r/B²
quotient-index keys, if pair orbits are full ≈ B²/(4n)
```

The second expression includes failed pair probes. It is optimistic about
novel rank and excludes factor-base construction, index generation, matrix
solving, target descent, and checks. One target after precomputed logs would
still need a working known-offset descent that repeatedly searches related
points until a verified decomposition is found; that descent has not been
implemented.

| Conditional degree-131 base | Input `B` | Input `K` | One useful relation or target descent, pair probes | Rank collection, pair probes | Quotient index, keys |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normal `x` weight ≤5, granting the rigorous maximum base | ≤`2^29.21` | unknown | at least about `2^71.59` under the pair-probe law | unknown | ≈`2^49.38` at the base cap if pair-sum orbits are full |
| Proposed `u` window, using sampled geometry | ≈`2^34.08` | ≈`2^26.05` | ≈`2^61.84` | ≈`2^87.89` | ≈`2^59.12` |

The `u`-window `B ≈ 18.1` billion comes from a frozen
[1,000-pattern rationality sample](u_window28_131_sample.json) and counts
**geometric points**, not an enumerated usable degree-131 subgroup base. The
model optimistically treats every such point as distinct after subgroup
projection. Its `K ≈ 69.3` million is a sampled folded-column estimate, not
a measured rank. At 17 bytes per compressed 131-bit key,
`2^59.12` quotient keys alone require about `2^63.21` bytes, before values,
hash-table overhead, and logs. The current canonicalization loop applies at
least 131 point Frobenius maps per complement probe; under the same support
law, its target descent would use about `2^68.88` point Frobenius calls and
rank collection about `2^94.92`. A different canonicalization could change
those latter counts.

Thus the **optimistic dominant component for a first solve by this direct
pair-index route** is about `2^87.89` pair-complement probes, requiring at
least `2^94.92` point Frobenius maps as written, with an
unbuildable proposed table under ordinary memory limits. This is a
conditional core work estimate in two distinct units, not a calibrated total
or a `2^x` field-operation count. The target-only
`2^61.84` figure excludes that preparation and is itself conditional. The
existing compact-orbit audit independently estimates `2^78.30` index states
at its equal-unit balance, or `2^99.66` rank probes under an unrealistically
generous 48 GiB, one-byte-per-state cap. Those are different parameter
choices within the direct pair-index family.

There is no measured ECC2K-130 DLP here. A complete, calibrated work total
and a rho speedup are **unknown**: the required stage costs and verified
scalar recovery are absent. The estimate does not rule out an algebraic
quotient summation method that avoids the pair-probe law.

## Reproduce

From the repository root with Python 3.11 or later:

```sh
python3 experiments/ecc2k130-quotient-pair-probe-20260926/scale_gate.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/quotient_pair_probe.py --degree 23 --weight 2 --queries 12 --output /tmp/ecc2k130-qpair-full.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/quotient_pair_probe.py --degree 23 --weight 2 --orbit-limit 1 --queries 12 --output /tmp/ecc2k130-qpair-orbit1.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/perf_probe.py --degree 53 --generators 424 --lookups 2048 --output /tmp/ecc2k130-qpair-n53-perf.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/perf_probe.py --degree 83 --generators 664 --lookups 2048 --output /tmp/ecc2k130-qpair-n83-perf.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/verify_receipts.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/work_estimate.py
```

The probe uses frozen local copies of the repository's `ecc2k130/codegen`
[field](field.py) and [curve](curves.py) arithmetic plus Python's standard
library. The scripts and frozen receipts are self-contained in this
directory. To regenerate the frozen receipt hashes, use the paths in `runs/`
as outputs and run the verifier and estimator after all stage runs.
