# ECC2K-130 quotient pair-sum gate, 2026-09-26

This experiment supplies exact four-point and five-point quotient pair-sum methods on
public Koblitz curves, three verified degree-53 target-seeded discrete logarithm
pilots, and a separate degree-131 support bound. The degree-53 pilots have
exact `IC1` method identities but incomplete online and operation accounting.
There is no degree-83 or ECC2K-130 recovered logarithm, calibrated operation
comparison with rho, or demonstrated work below `2^61`. The other stage
receipts retain `candidate_id: null`.

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
from query timing. These weight-base toy rows do not recover a scalar.

## Frozen stage measurements

The degree-23 full and one-orbit rows have the same workload ID
`b8db2fa3dde1` and exactly the same 12 public target points. Each query has
an independent four-point curve-law replay when it hits. Misses exhaust the
quotient index and agree with the direct pair table. Index build time is
target-independent and separate from query time. Wall times below are medians
from one macOS Python 3.14.7 run, in milliseconds; they are not field-operation
counts or ECC2K-130 projections.
The [curve manifest](curve_manifest.json) records canonical field and curve
identities for all six measured degrees; the paired degree-23 curve is
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

## Matched x-first canonicalization follow-up

The [x-first implementation](fast_canonical.py) exploits the binary curve
law: negating `(x,y)` leaves `x` unchanged. It finds the least Frobenius
conjugate of `x`, then transforms `y` only at shifts attaining that `x` and
chooses the smaller of the two signs. [Exact equivalence controls](test_fast_canonical.py)
compare its `(key, shift, sign)` with the original scan on degrees 13, 19,
23, 53, 83, and 131. Every matched run also reproduces the original complete
selected-base index digest and the same bounded query hit trace.

The comparison uses six paired process blocks per degree. Both arms in each
block use the same field, curve ID, base digest, one ordinary target, and
2,048-lookup prefix repeated three times. Arm order alternates. The ratio
below is original scan time divided by x-first time, using each arm's median
query time within a block; confidence intervals bootstrap the six paired
log-ratios 10,000 times. These are stage timings on one macOS host, with
considerable run-to-run variation.

| Degree and curve ID | Actual `B` / folded columns | Original / x-first mean query time per 2,048 lookups | Paired geometric-mean ratio | Paired bootstrap 95% interval | Faster blocks |
| --- | ---: | ---: | ---: | ---: | ---: |
| 53, `EC1N53Ckb1hf77aab617904` | 212 / 2 | 333 / 200 ms | 1.66 | 1.57–1.78 | 6/6 |
| 83, `EC1N83Ckb1h876c2921cb64` | 332 / 2 | 645 / 373 ms | 1.73 | 1.61–1.83 | 6/6 |
| 131, `EC1N131Ckb1h6816f880945e` | 524 / 2 | 1,328 / 713 ms | 1.86 | 1.80–1.91 | 6/6 |

Per 2,048-lookup prefix, the original scan used 109,567 point Frobenius calls
and 111,616 point negations at degree 53; x-first used 1,023 and 3,072,
respectively, plus 106,496 x-coordinate field Frobenius calls and about
2,000 y-coordinate field Frobenius calls. At degrees 83 and 131 the
x-coordinate counts are 167,936 and 266,240. At degree 131 the original
scan uses 269,311 point Frobenius calls per prefix and x-first uses 1,023,
plus its x- and y-coordinate calls. These operation types have different costs and are not combined
into a field-operation count. The pair-complement-probe exponent in the
degree-131 work model below is unchanged.

The [stage proposal registry](stage_proposals.json) reserves `Q1001`–`Q1006`
for the two variants on the three exact curves. It records the normal-basis
field modulus and encoding, exact curve and subgroup, pre-fold usable `B`,
folded columns, base digest, solver variant, and `isogeny: "none"` with unknown
endomorphism conductor left `null`. The [version-2 stage rows](stage_runs.jsonl)
carry `proposal_id`, `candidate_id: null`, workload and run IDs, matched
resource and target references, all bounded outcomes, and partial phase
costs. The [comparison receipt](comparison.json) preserves every paired
timing and its input hashes. The catalog's current analyzer accepts its older
version-1 run schema; this experiment's [emitter](emit_protocol_comparison.py)
validates the version-2 stage invariants locally. Neither variant has an
`IC1` ID: collection, final relation-matrix solving, and target descent are
unresolved. The repeated prefixes are not completed ordinary decomposition
attempts and give no relation-yield estimate.

## Normal-basis cyclic and x-only quotient keys

[`cycle_canonical.py`](cycle_canonical.py) reorders the optimal-normal-basis
coordinates into their Frobenius cycle. One Frobenius step is then one cyclic
bit rotation. The implementation chooses the least rotation before
transforming the selected point. Its key order differs from x-first, so
index construction and lookup must both use this rule. The independent
[orbit-scan test](test_cycle_canonical.py) checks keys, shifts, signs, and
group witnesses at degrees 53 and 83.

[`x_only_cycle.py`](x_only_cycle.py) goes further. On
`y²+xy=x³+1`, every rational nonzero `x` has two `y` roots, related by
curve negation. Thus `x` alone identifies a signed-Frobenius point orbit.
The lookup returns a rotation of `x` without transforming `y`; after a hit,
the stored pair sum is aligned to the complement and its sign is checked
before the four base points are replayed. The [positive control](test_x_only_cycle.py)
constructs a four-point target, gets a hit, and checks the group sum at both
degrees. Both index variants contain exactly the same number of quotient
orbits as the frozen x-first index, though their key digests differ by design.

The [cycle](runs/n83_cycle_comparison.json) and
[x-only](runs/n83_x_only_comparison.json) degree-83 receipts retain six
paired blocks each, alternating arm order, with three repeated 2,048-lookup
ordinary-target prefixes per block. Corresponding [degree-53 cycle](runs/n53_cycle_comparison.json)
and [x-only](runs/n53_x_only_comparison.json) receipts use the same design.
Every prefix had zero hits and every constructed positive control had an
independently replayed hit. The table gives the paired geometric mean of
x-first query time divided by the new variant's time; intervals bootstrap
the six paired block ratios. The selected base and target are identical
within each pair, and setup is outside the query interval.

| Degree, exact curve ID | Actual `B` / columns | Variant | Quotient keys | x-first / variant query ratio | Paired 95% interval | Faster blocks |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 53, `EC1N53Ckb1hf77aab617904` | 212 / 2 | cyclic full-point | 207 | 1.69 | 1.62–1.83 | 6/6 |
| 53, same curve | 212 / 2 | cyclic x-only | 207 | 2.43 | 2.39–2.47 | 6/6 |
| 83, `EC1N83Ckb1h876c2921cb64` | 332 / 2 | cyclic full-point | 327 | 1.95 | 1.81–2.09 | 6/6 |
| 83, same curve | 332 / 2 | cyclic x-only | 327 | 3.07 | 3.00–3.16 | 6/6 |

Each x-only miss performs 82 or 52 word rotations at degrees 83 or 53,
respectively, and no selected `x`/`y` field Frobenius transform. The
full-point cyclic variant still transforms both coordinates at the selected
shift. The [proposal registry](cycle_stage_proposals.json) uses `Q1007`–`Q1010`
and retains `candidate_id: null`, the exact curve identity, pre-fold `B`,
folded columns, base digest, and `isogeny: "none"`. The
[version-2 stage rows](cycle_stage_runs.jsonl) retain a run ID for every
bounded variant block, workload ID, partial phase time, and budget outcome.
The [comparison summary](cycle_stage_comparison.json) retains input hashes,
operation vectors, paired uncertainty, and the absent relation-yield and
verified-DLP fields. This benchmark measures lookup prefixes on small bases;
it does not estimate a complete solve.

### Conditional degree-83 work screen on an enumerated base

The separate [work screen](n83_d12_work_screen.json) uses frozen
[curve](n83_d12_inputs/n83_toy_curve.json) and
[base geometry](n83_d12_inputs/n83_d12_frobenius_orbit_base_geometry.json)
inputs for **`EC1N83Ckb1hc1776f347753`**, a polynomial-basis field
representation. This is a different curve ID from the normal-basis timing
panel; no timing or operation conversion is transferred between them. Its
dimension-12 base has 4,006 projected seed points, **326,024 actual subgroup
points before folding**, and 1,964 signed-Frobenius columns. No isogeny is
used. The [screen source](n83_d12_work_screen.py) counts
`C(326024,2) − 1964·C(166,2)` cross-column unordered pairs exactly and
uses a declared uniform pair-sum model:

| Conditional quantity | Value and unit |
| --- | ---: |
| Pair-complement probes per verified relation | `2^45.37` probes |
| `K=1,964` novel rows plus one target relation | `2^56.31` probes |
| Quotient pair generators, with no cross-orbit sum collisions | 319,992,556 generators |
| Bare 11-byte x-key payload at that size | 3,519,918,116 bytes |
| Word rotations for those probes with x-only key | `2^62.67` rotations |
| Field-operation budget per probe to keep the modeled total below `2^61`, if all other costs were zero | 25.78 field operations |

These figures include failed probes in the uniform-support model but assume
every relation adds a new row. Actual pair-sum distribution, novel rank,
index storage overhead, field-operation conversion, factor-base logarithms,
matrix solution, and target scalar recovery are unmeasured. The key payload
is a minimum that excludes witnesses, point values, and table overhead.
There is still **no measured ordinary relation yield, full DLP, or verified
work below `2^61`**. The screen identifies the cost a scaled implementation
must beat; it is not evidence that it does.

### Batch-inversion operation gate

The [batch implementation](batch_x_only.py) computes the target complements
for one signed-Frobenius orbit using one shared field inversion. It handles
identity, equal-`x`, doubling, and opposite-point cases through the complete
curve law. [Exact controls](test_batch_x_only.py) compare each batch sum with
ordinary addition and compare both quotient-query hit traces, including a
constructed positive four-point target, at degrees 53 and 83.

The [degree-53](runs/n53_batch_x_only_comparison.json) and
[degree-83](runs/n83_batch_x_only_comparison.json) receipts pair the same
small selected base, ordinary target, and 2,048-lookup prefix against the
affine x-only implementation in six alternating-order blocks. The
[summary](batch_stage_comparison.json) reports the ratio of affine wall time
to batch wall time; a ratio below one means the batch was slower in Python.

| Degree, exact curve ID | Affine / batch paired wall ratio (95% interval) | Affine inversions → batch inversions per prefix | Affine multiplications → batch multiplications |
| --- | ---: | ---: | ---: |
| 53, `EC1N53Ckb1hf77aab617904` | 0.875 (0.799–0.926) | 1,942 → 19 | 3,884 → 9,710 |
| 83, `EC1N83Ckb1h876c2921cb64` | 0.949 (0.913–0.987) | 1,882 → 12 | 3,764 → 9,410 |

The counts cover calls to the field API during one frozen prefix. The batch
formula also contains direct XORs, and the internal bit work of a field
multiplication or inversion is not decomposed. Batch inversion greatly
reduces inversion calls but did **not** improve Python wall time on these
small bases. At degree 83 it uses about 4.59 multiplication calls and
0.0059 inversion calls per probe, plus about 0.92 squarings and 0.92
Frobenius calls. These operation types cannot be added to the polynomial-
basis work screen's 25.78-field-operation allowance without a calibrated
common unit and measured ordinary rank yield. The
[stage registry](batch_stage_proposals.json) uses `Q1011`–`Q1012`, with
`candidate_id: null`, and the [version-2 rows](batch_stage_runs.jsonl)
retain every bounded outcome.

## Dyadic-window quotient relations at degrees 53 and 83

The [dyadic proposal registry](dyadic_stage_proposals.json) names `Q1013`–`Q1028`
under the repository protocol. Every row carries the exact field and curve,
actual distinct subgroup-usable `B` **before** folding, the enumerated-set
digest, signed-Frobenius columns, effective unknown seed-log columns, and
`isogeny: "none"`. The ONB curve IDs are
`EC1N53Ckb1hf77aab617904` and `EC1N83Ckb1h876c2921cb64`; they must not
be conflated with the polynomial-basis degree-83 curve above. The unknown
endomorphism-order conductor remains `null`. The
[receipt verifier](verify_dyadic_receipts.py) independently replays curve
identity hashes, coefficient labels, group sums, recovered scalars, and
candidate identity hashes.

The base starts with subgroup points `G` and one or more independent seeds,
takes a short doubling window from each, and closes under sign and Frobenius.
The label of each point is `±2^k λ^j` times its seed log modulo the subgroup
order, where `λ` is the verified Frobenius eigenvalue. This preserves an exact
large point set while reducing the number of *unknown* logs. The two-seed
target-dependent variant uses the supplied public DLP target as its second
seed, so a known-scalar query `αG` with a verified four-point relation gives
one equation `α = a + b log_G(Q) (mod r)`. If `b != 0`, one modular inverse
recovers the scalar, which is independently replayed on the curve. All
target-dependent base and index work belongs to that target.

| Frozen degree-53 run | Actual `B` | Signed-Frobenius columns / unknown logs | Complete missed queries | Verified relations | Complement probes including failures | Index keys / build | Measured interval after target preflight | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Q1015`, independent eight-seed base, one ordinary target | 3,392 | 32 / 7 | 1 | 0 | 5,033,728 | 47,488 / 11.7 s | 233.6 s query only | — |
| `Q1016`, same base, secondary four-target panel | 3,392 | 32 / 7 | 3 | 1 | 15,107,470 | 47,488 / 9.7 s | 699.0 s queries | — |
| `Q1019`, public target as second seed, 16 doublings | 3,392 | 32 / 1 | 4 | 1 | 11,694,693 | 27,136 / 12.3 s | 674.2 s | 61.5 MB |
| `Q1021`, same target, 64 doublings | 13,568 | 128 / 1 | 0 | 1 | 1,573,644 | 434,176 / 131.8 s | 223.9 s | 576.0 MB |

The secondary `Q1016` panel was frozen only after the `Q1015` single-target
miss. Its first three ordinary targets exhausted the quotient index and its
fourth hit after 6,286 probes. The four-point witness has four distinct
points and a nonzero coefficient in four unknown seed columns; it supplies
one verified row, not seven logs or a DLP. Observed yield is `1/4`, with an
exact 95% binomial interval of about `[0.0063, 0.806]`. The two target-seeded
runs recovered the same scalar, `3400509474685`, on the same public point;
the [16-step](runs/n53_dyadic_target_seed_dlp.json) and
[64-step](runs/n53_dyadic_target_seed_dlp_w64.json) receipts retain every
miss, probe count, four-point witness, coefficient row, index digest, and
independent `[scalar]G = Q` check. Their query streams differ, so their wall
times are individual results, not a paired speedup estimate.

The exact [candidate manifests](candidates) name the completed degree-53
methods as
`IC1N53Ckb1fb3392PDP4qpairRCsampleLAgaussTDdirectISO0h9bff857cc742`
and
`IC1N53Ckb1fb13568PDP4qpairRCsampleLAgaussTDdirectISO0hb99205944185`.
The corresponding [candidate-linked pilot rows](runs) use the full
`<candidate-id>W<workload-id>R1` run form. `PDP4qpair` is recorded in
[`AGENTS.md`](../../AGENTS.md) as the exact four-summand quotient pair index.
These are target-specific candidate identities because the public target
itself is an exact factor-base seed. The measured interval begins with base
enumeration and omits target subgroup validation just before that timer;
therefore the formal single-target online time, complete calibrated field
operation count, `2^x` full-work value, and paired rho speedup all remain
`null` in the candidate-linked rows. Neither pilot establishes a speedup.

At degree 83, the [L32 bounded performance run](runs/n83_dyadic_target_perf_L32.json)
built a complete target-seeded quotient index with **10,624 actual usable
points**, 64 signed-Frobenius columns, 169,984 quotient keys, and one unknown
log. Index construction took 60.4 seconds and peak process RSS was 282.5 MB.
Three prefixes of 10,624 ordinary known-log complement lookups had zero hits;
their median was 647 ms, or about 61 µs per lookup in this bounded run.
A separate planted four-point target hit at lookup 1 and passed group-law
replay. The zero-hit prefixes are throughput measurements, **not** a
relation-yield estimate. This gives a larger same-curve performance point
than the earlier 332-point base, without extrapolating wall time across
field representations.

The [packed Q1023 run](runs/n83_dyadic_compact_packed.json) uses the **same**
L32 curve, public target, base, and known-log query. It enumerates only one
cross-seed orientation, sorts `(83-bit key, compact pair label)` rows, and
reconstructs full point witnesses during a query. All 169,984 keys occupy
**4,079,616 retained bytes at 24 bytes per row**. Its one-process build took
9.2 seconds with 80.3 MB peak RSS; three 10,624-lookup prefixes had a 746 ms
median and no ordinary hits, and the planted hit passed replay. This single
process result is not a paired wall-speed estimate against the dictionary.
The independent [comparison control](runs/n83_dyadic_compact_compare.json)
reconstructed the dictionary index, proved equality of the **entire key
set** and its frozen digest, and replayed 1,001 sampled packed witnesses.

### Five-point two-plus-three quotient decomposition

The five-point variant indexes every signed-Frobenius quotient class of a
sum of two generator-seed points. For a known-log query `αG`, it samples
three points from the public target-seed base and looks up the remaining
complement. A verified hit has the form `αG = aG + bQ`; `b != 0` gives the
target scalar by one modular inverse. This is a complete index for the
chosen two-G side, followed by random sampling on the three-Q side. Every
failed triple is charged to the same public target.

The [degree-53 Q1024 receipt](runs/n53_dyadic_five_sum_dlp.json) uses the
same exact L64 base and target as Q1021: `B=13,568`, 128 folded columns,
one unknown log, and the same enumerated-set digest. Its G-pair index has
207,940 keys and took 41.3 s to build. One natural verified relation
appeared after **121,430** ordinary triple attempts, recovering
`log_G(Q)=3400509474685`; the independent `[scalar]G=Q` replay passed.
The measured target interval, including target membership preflight, base,
index, failed attempts, and replay, was **53.2 s**. One hit in one search
is not a stable yield estimate, and this run is not paired with rho. The
complete implemented method has its own
[IC1 candidate manifest](candidates/IC1N53Ckb1fb13568PDP5q23RCsampleLAgaussTDdirectISO0hf7ff67353971.json)
and [candidate-linked run](runs/n53_dyadic_five_sum_candidate.json).
`PDP5q23` is defined in [`AGENTS.md`](../../AGENTS.md). Exclusive phase
accounting and calibrated field-operation totals remain incomplete, so the
formal work `2^x` and online speedup remain unknown.

The [degree-83 Q1025 receipt](runs/n83_dyadic_five_sum_stage.json) uses
the exact named ONB curve, public target, and L32 base: `B=10,624`, 64
folded columns, one unknown log. Its complete two-G quotient index has
80,868 keys, representing exactly **13,423,923** distinct pair sums under
the verified 166-point nonidentity signed-Frobenius orbits. Build time was
28.8 s and peak process RSS was 153.3 MB. Three bounded blocks sampled
12,288 ordinary target-base triples with no hit; median time was 636.7 ms
per 4,096 attempts. A planted five-point relation passed group and seed
coefficient replay. The batched point-addition helper is checked against
the complete affine law for ordinary, identity, equal-point, and opposite
inputs at both degrees 53 and 83. The zero-hit prefix is a stage throughput
measurement, not a useful natural relation or a measured DLP yield.

The [packed two-G Q1027 run](runs/n83_dyadic_five_sum_packed_stage.json)
stores the same complete L32 point-witness index in 1,940,832 retained
bytes (24 bytes per key). Its packed-only process peak before constructing
the dictionary control was 61.6 MB, and build took 9.44 s. The dictionary
control built in 30.96 s in the same process; these build times were not
alternated. The **entire** packed key set matches the dictionary key set;
1,001 sampled witnesses and a five-point planted relation with three
different Q-side x coordinates pass group and coefficient replay. Three
paired, alternating-order blocks used identical frozen ordinary triples
for the dictionary, per-key packed binary search, and batched NumPy
search. All 12,288 attempts per variant missed. The median
dictionary/packed query wall ratio was **0.945** for per-key binary search
and **0.969** for vectorized lookup, so the latter came close to dictionary
query time on this L32 process. Across the three paired blocks, the observed
ratios ranged **0.889–0.949** and **0.896–0.979**, respectively; three blocks
do not support a precise population interval. A planted relation also passed
through the full vectorized query and replay path. This is a real packed point-witness
index, but only at L32; it does not change the L1000 search exponent. At the
82,843,900 exact L1000 two-G quotient keys, the retained packed rows alone
would be 1,988,253,600 bytes. That is a format-based storage projection,
not an L1000 point-witness index measurement.

The [symmetric packed Q1028 run](runs/n83_dyadic_five_sum_symmetric_stage.json)
uses the commutativity of the two G summands: for seed-orbit pair `(i,j)`,
it constructs only the orientation with `i <= j`. On the **same n83 L32
curve and base**, this cut point-pair generators from 169,984 to **87,648**
and raw row storage from 4,079,616 to **2,103,552 bytes**. It built in
4.74 s, including the orbit partition, at 59.8 MB peak process RSS; the
full packed Q1027 build took 9.44 s in a separate process, so the wall
comparison is unpaired. The full 80,868-key digest and even the retained
row digest match Q1027 exactly, and 1,001 sampled witnesses pass group
and quotient replay. The retained array remains 1,940,832 bytes and query
probability is unchanged. At L1000, this schedule requires **83,083,000**
pair generators rather than 166,000,000, assuming the same orbit geometry;
the former count was also enumerated exactly by Q1026's scalar-support
calculation. No L1000 curve-point witness build or n83 natural relation
has yet been measured.

The [Q1029 disk-backed builder](dyadic_n83_g_pair_witness_index.py) is now
running the exact L1000 two-G point-witness construction, with a checkpoint
after each completed G orbit. Its completed [L32 control](runs/n83_dyadic_G_pair_witness_index_L32.json)
reconstructed all 87,648 generators and 80,868 quotient keys on the same
curve and base as Q1028. The **entire** sorted unique-row digest and key-set
digest match Q1028, and 996 sampled row witnesses passed point addition
and quotient replay. This verifies the disk-backed format
before the L1000 build. The larger run will compare its complete point-key
count against Q1026's independently enumerated scalar support; until its
receipt exists, L1000 point witnesses and ordinary relation yield remain
unmeasured. Both the raw and sorted large row files stay outside Git; a
completed receipt will retain their hashes and the exact local paths. The
build is target-dependent because the base includes the public Q.

```sh
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_g_pair_witness_index.py \
  --window 1000 --workdir /private/tmp/ecc2k83-Gpair-witness-L1000
```

### Same-target degree-83 rho reference

The [rho bridge](n83_public_target_rho.cpp) supplies the **same frozen public
G and Q** to the tracked CPU engine in `crypto/ecc2k130/src/main.cu`. It
converts the declared 167-bit symmetric ONB representation to the engine's
83-bit ONB coordinates; the source contains no target scalar. The engine's
degree-83 field, orbit, walk, and collision-solver self-checks passed on
these points. This is a separately labeled rho reference, not a `Q`/`IC1`
factor-base candidate. Its collision is not evidence of ordinary IC relation
yield. The [independent replay script](verify_n83_public_target_rho.py)
rejects an incomplete log and writes a receipt only after the returned
scalar reproduces the exact public Q under the experiment's separate point
arithmetic. It reports rho walk iterations as its work unit, leaving
complete IC work unknown.

The bridge was compiled against the tracked `crypto` engine at commit
`fb4491d4451b882514b2312c8f1eabff622dfe26` for the current local run.
The local four-thread 16-launch collection prefix measured 67,108,864 walk
iterations in 1.4 s, or 46.838 million iterations/s, with 1,114 distinguished
points and zero drops. This prefix is a throughput diagnostic, not a DLP.
The [stopped-attempt receipt](runs/n83_public_target_rho_attempt.json) records
three same-target workers with distinct run IDs and preserved failed work:
**91,142,225,920** total walk iterations (`2^36.407`), **1,467,130** DP
records, zero dropped reports, and a complete three-corpus merge with
1,467,130 distinct orbits and no collision. Every worker exited through its
checkpoint path. The multiworker experiment was stopped when host load caused
throughput to collapse; its DP files and checkpoints remain available locally
for resume. This is an unsuccessful rho attempt, **not** a measured DLP,
ordinary IC relation, or complete-work success below `2^61`. The attempt
receipt retains source, binary, log, corpus, and checkpoint hashes; the large
binary corpora are not bundled in this PR.
The exact first-worker [driver source snapshot](n83_public_target_rho_initial.cpp)
is retained beside the portable bridge; the verifier matches both source
hashes to their respective worker rows.

The resumed worker later produced a cross-corpus collision with one of the
stopped workers. The [terminal merge log](runs/n83_public_target_rho_merge_solved.log)
records `k = 467066815623456506232910` and the engine's `[k]P == Q` check.
The [separate Python replay receipt](runs/n83_public_target_rho_solved.json)
recomputes `[k]G` on the exact named ONB curve and verifies the frozen public
Q. It charges **all three workers**, including the earlier unsuccessful
attempt and the checkpointed resume: **201,733,439,488** rho walk iterations,
or **`2^37.554` walk iterations**, to this one solved target. The terminal
worker counts are 176,404,037,632, 12,914,262,016, and 12,415,139,840.
The quotient is a count of rho walk steps, not field multiplications or a
complete IC cost; collision replay, corpus hashing, and offline scalar replay
are outside that operation boundary. The primary paired online rho wall time
is unknown because this run was interrupted and resumed in separate intervals.
The large distinguished-point corpora and terminal logs were copied to a
frozen local snapshot whose hashes match the receipt; they are omitted
from Git. **No ordinary n83 factor-base relation has been found**, so this
rho DLP does not establish the requested index-calculus relation yield.

For a new local run, set `RHO_ENGINE_SRC` to the `src` directory of a
checkout of the pinned `crypto` commit, then build and run from this repo:

```sh
RHO_ENGINE_SRC=/path/to/crypto/ecc2k130/src
/opt/homebrew/opt/llvm/bin/clang++ -isysroot "$(xcrun --show-sdk-path)" \
  -O3 -std=c++17 -march=native -fopenmp -DECC_NO_CUDA -DECC_BATCH=32 \
  -I"$RHO_ENGINE_SRC" -x c++ \
  experiments/ecc2k130-quotient-pair-probe-20260926/n83_public_target_rho.cpp \
  -o /tmp/ecc2k83-public-rho
/tmp/ecc2k83-public-rho --test --threads 4
/tmp/ecc2k83-public-rho --threads 4 --steps 512 --run-id 32028 \
  --dp-weight 22 --verify 8 --dp-file /tmp/ecc2k83-public-rho.dps \
  --checkpoint /tmp/ecc2k83-public-rho.ckpt \
  > /tmp/ecc2k83-public-rho.log 2>&1
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/verify_n83_public_target_rho.py \
  --log /tmp/ecc2k83-public-rho.log --binary /tmp/ecc2k83-public-rho \
  --driver-source experiments/ecc2k130-quotient-pair-probe-20260926/n83_public_target_rho.cpp \
  --rho-source "$RHO_ENGINE_SRC/main.cu" \
  --out /tmp/ecc2k83-public-rho-replay.json
```

The final replay command must fail while the run is incomplete. The run
ID, DP file, and checkpoint form one frozen rho workload; use new paths and
a new run ID for an independent repetition. For a parallel solve, pass one
`--worker-log`, `--worker-binary`, `--worker-driver-source`, and
`--worker-dp`, and `--worker-run-id` per worker after all workers have
reached terminal logs;
the replay tool sums **every** worker's walk iterations, including failed
work. A merge log with a recovered scalar can be supplied as `--log`.

The [exact degree-83 L1000 support run](runs/n83_dyadic_G_pair_scalar_support_L1000.json)
replaces the earlier L32-ratio extrapolation. It uses the **same exact base**
as Q1020: `B=332,000`, 2,000 folded columns, one unknown log, and the
same point-set digest. The G side contains 166,000 points. Because its
scalar coefficients are known, raising each nonzero pair-sum coefficient
to the 166th power modulo the prime subgroup order identifies precisely
one signed-Frobenius orbit. Enumerating 83,083,000 unordered pair-orbit
generators took 69.7 s and 12.6 GB peak RSS and found **82,843,900**
quotient orbits, representing exactly **13,752,087,235** distinct G-pair
sums. This is **99.8113%** of the rigorous unordered-pair cap
`C(166000+1,2)=13,778,083,000`. At L32, the scalar-orbit key set agrees
with every key reconstructed from the independently built curve-point
index. The L1000 count is a support measurement, **not** a point-witness
index capable of querying an unknown target. At 24 bytes per packed witness
row, those exact keys would retain 1,988,253,600 bytes before sorting and
lookup overhead; this is a format transfer, not measured L1000 index memory.
The former L32 support-ratio
transfer (0.9513) was inaccurate at L1000.

The updated [five-point work projection](dyadic_five_sum_n83_projection.json)
uses the **exact** L1000 support. Under the still **unverified** model that
fixed-target triple complements are independent and uniform over the
subgroup and that hits have nonzero target coefficient, it gives
`2^47.321` expected triple attempts. Transferring the measured L32 batched
operation vector gives `2^51.227` field API multiplication calls and
`2^53.679` cyclic word rotations, in separate units. Transferring the
same Python wall rate would be about 866 single-process years; this is a
diagnostic extrapolation, not an implementation benchmark at L1000.
These are conditional query-work screens, **not** a complete solve-cost
upper bound or a claim below `2^61`: fixed-target triple coverage,
L1000 point-witness index construction and memory, field-cost calibration,
and an n83 ordinary relation remain unmeasured.

[Exact enumeration on the frozen public degree-83 target](runs/n83_dyadic_target_seed_geometry.json)
gave `B=332,000`, 2,000 folded columns, and one unknown log in 2.83 seconds.
The corresponding [independent-seed geometry](runs/n83_dyadic_two_seed_geometry.json)
has the same counts but a different exact point-set digest. A complete
cross-seed quotient index enumerates 166,000,000 pair generators and would
hold up to that many distinct keys. At the no-collision size, eleven bytes
per x key alone require 1.826 GB; this excludes witnesses and hash-table overhead.
Transferring the measured degree-83 L32 dictionary RSS per key would suggest
about 276 GB. The packed 24-byte format instead projects **3.984 GB retained**
at 166 million keys, with temporary sort/dedup storage and base points in
addition. Both figures are **memory extrapolations**, not degree-83 L1000
measurements. No complete degree-83 L1000 index, ordinary relation, rank,
or scalar recovery has been run.

The original two-seed `r/P` estimate, where `P` is the number of cross-seed
pairs, incorrectly treats pair probes as independent relation opportunities.
The [coefficient-support audit](dyadic_coefficient_support.json) corrects it.
Writing `C={±2^k λ^j}` and `S=C+C`, an `αG` four-sum relation on a
target-seeded base requires `α` to be in `S+log_G(Q)·S`. Therefore an
independent uniform known-log query has success probability **at most**
`|S|²/(r−1)`. Exact degree-53, 16-step enumeration gives `|S|=1,267,231`
and a probability cap of `0.0763`. At degree 83 with 1,000 steps, the
new exact count `|S|=13,752,087,235` gives probability at most
`7.82×10^-5`, hence at least `2^48.324` **expected probes in failed complete
scans alone** under independent uniform query sampling. This is a lower
bound for the stated direct-index query policy, not a solve-cost upper bound.
The separate [same-curve operation screen](dyadic_two_seed_n83_projection.json)
now uses the exact L1000 support. The earlier `2^48.52` L20 collision-ratio
transfer is superseded.
Applying the measured same-curve **packed** L32 batched-query operation vector
to the exact-support failed-scan lower bound gives `2^50.649` field API
multiplication calls and `2^54.681` cyclic word rotations, in separate units.
Index construction,
memory traffic, useful coefficient yield, full target checks, and any
field-operation calibration are additional and unmeasured. The earlier
`2^46.32` independent-probe projection is **refuted for this two-seed
policy**; the 100-seed `Q1013` model remains an unvalidated hypothesis with
different support geometry.

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
python3 -m unittest discover -s experiments/ecc2k130-quotient-pair-probe-20260926 -p test_fast_canonical.py -v
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_canonical.py --degree 53 --variant scan --run-number 1 --output /tmp/ecc2k130-qpair-n53-scan.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_canonical.py --degree 53 --variant xfirst --run-number 1 --output /tmp/ecc2k130-qpair-n53-xfirst.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/emit_protocol_comparison.py
python3 -m unittest discover -s experiments/ecc2k130-quotient-pair-probe-20260926 -p test_cycle_canonical.py -v
python3 -m unittest discover -s experiments/ecc2k130-quotient-pair-probe-20260926 -p test_x_only_cycle.py -v
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_cycle.py --degree 53 --output /tmp/n53-cycle-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_cycle.py --degree 83 --output /tmp/n83-cycle-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_x_only.py --degree 53 --output /tmp/n53-x-only-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_x_only.py --degree 83 --output /tmp/n83-x-only-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/n83_d12_work_screen.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/summarize_cycle.py
python3 -m unittest discover -s experiments/ecc2k130-quotient-pair-probe-20260926 -p test_batch_x_only.py -v
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_batch_x_only.py --degree 53 --output /tmp/n53-batch-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/compare_batch_x_only.py --degree 83 --output /tmp/n83-batch-comparison.json
python3 experiments/ecc2k130-quotient-pair-probe-20260926/summarize_batch.py
```

The probe uses frozen local copies of the repository's `ecc2k130/codegen`
[field](field.py) and [curve](curves.py) arithmetic plus Python's standard
library. The scripts and frozen receipts are self-contained in this
directory. To regenerate the frozen receipt hashes, use the paths in `runs/`
as outputs and run the verifier and estimator after all stage runs.
For a full refresh of the matched comparison, first run
`freeze_n131_stage_reference.py`, then rerun both variants for all six blocks
at degrees 53, 83, and 131, and finally run `emit_protocol_comparison.py`.
Refreshing only the degree-131 reference changes its measured timing fields
and therefore its hash; the comparison emitter correctly rejects older runs.
To refresh the cyclic comparison receipts, use their `runs/` paths rather
than `/tmp/` outputs above, then run `summarize_cycle.py`. The summary checks
each source and reference hash before emitting the proposal and stage rows.
The batch comparison works the same way: write both full receipts to their
`runs/` paths before running `summarize_batch.py`.

For the dyadic-window additions, run the local verified `./sage` launcher
from the primary repository checkout. The geometry, support, and projection
checks finish quickly; the two degree-53 DLP pilots take several minutes and
write their receipts incrementally so failures remain visible:

```sh
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_base_geometry.py --degree 53
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_base_geometry.py --degree 83
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_two_seed_geometry.py --degree 53
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_two_seed_geometry.py --degree 83
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_target_base.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_target_perf.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_compact_index.py --mode packed
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_compact_index.py --mode compare
python3 experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_coefficient_support.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_work_projection.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_two_seed_n83_projection.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n53_relation_probe.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n53_relation_panel.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n53_target_seed_dlp.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n53_target_seed_dlp_w64.py
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/test_dyadic_five_sum_batch.py
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n53_five_sum_dlp.py
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_five_sum_stage.py
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_five_sum_packed_stage.py
./sage -python experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_five_sum_symmetric_stage.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_n83_g_pair_scalar_support.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/dyadic_five_sum_n83_projection.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/emit_dyadic_stage_proposals.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/promote_dyadic_n53_candidates.py
python3 experiments/ecc2k130-quotient-pair-probe-20260926/promote_dyadic_n53_five_sum.py
./sage experiments/ecc2k130-quotient-pair-probe-20260926/verify_dyadic_receipts.py
```

The base geometry receipt hashes feed the later runs, so regenerate in this
order. The packed-index variant additionally requires NumPy. Timings and
receipt hashes will change on another host; candidate
identity hashes change only if the mathematical base, algorithm, or executed
source snapshot changes.
