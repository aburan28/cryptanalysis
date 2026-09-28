# First empirical pass over the 1,000 IC proposals

A subsequent [complete N13 follow-up](COMPLETE_N13.md) reports 20 paired
one-target DLP runs for a separately pinned exact SAT variant derived from
the `Q1` axes. The ledger below remains a proposal assessment: its `Q1`
`candidate_id` and measured cost stay null because the original chained-S3
SAT stage and the new explicit-sumset selector CNF are different methods.
The `Q1` assessment row links the complete candidate separately.

The [assessment ledger](assessment.jsonl) and [spreadsheet-ready CSV](assessment.csv)
have exactly one row for every
`Q1`–`Q1000` proposal. These are **stage measurements and readiness results**,
not 1,000 complete attacks. No proposal has an exact materialized pipeline,
verified one-target DLP run, paired rho online result, or earned `IC1` ID.
Consequently every `single_target_online_ms` and `online_speedup` is `null`.
This follows the current [agent rule](../../../../AGENTS.md): the primary IC
comparison is one previously unseen target after reusable preparation.

## What was measured

| Catalog profile | Proposals sharing the profile | Exact profile evidence from this pass | Matched method evidence |
| --- | ---: | --- | --- |
| N13 same base, four summands, `fb6` | 100 | Four-sum support **84 / 2,002** uniform nonidentity subgroup points (4.196%); two folded columns. | The first-witness SAT PDP stage for `Q1`–`Q4` has budget-matched receipts below. No final matrix or DLP. |
| N19 five shifted bases, five summands, `fb30` union | 100 | Five-sum support **7,560 / 130,872** (5.777%); two folded columns. | No catalog PDP backend is wired to this exact shifted system. |
| N131 polynomial base d=7, four summands, `fb26` | 100 | Exact support **19,604 / 680564733841876926932320129493409985128** nonidentity subgroup points, about `2.881e-35`. | The pair-lookup control found 24/24 **planted** decompositions. Its 13 matrix-rank rows are all negation identities, adding zero rank beyond them. No ordinary-query solver yield. |
| N131 normal-basis HW2, four summands | 100 | Exact subgroup-filtered **fb3668**, 14 folded columns, with the full point set saved. | No matching PDP or target solver. |
| N131 normal-basis HW3, five summands | 100 | Exactly the **same fb3668** and 14 columns: the added odd-weight x coordinates yield no subgroup points. | No matching PDP or target solver; the different arity remains a distinct proposal. |
| N131 polynomial d=24, six summands | 100 | Uniform sample: 119 / 1,024 x values usable. Estimated `B≈3.90 million`, Wilson 95% interval **3.29–4.61 million**. Exact `B` remains unknown. | No matched PDP or target solver. |
| N131 polynomial d=28, five summands | 100 | Uniform sample: 126 / 1,024 x values usable. Estimated `B≈66.1 million`, Wilson 95% interval **56.0–77.6 million**. Exact `B` remains unknown. | No matched PDP or target solver. |
| N53 retained base, five-summand proposal | 100 | The pinned prior receipt still reports 23,320 usable points and 220 folded columns; its SHA-256 was checked in this pass. | No exact five-summand PDP or complete base-point digest for this profile. |
| N131 isogeny profiles | 200 | Codomain bases and routes remain unmaterialized. | Search-only routes have no verified point maps or one-target DLP. |

The toy support counts are **exact finite enumeration**, not sample estimates.
The new [geometry receipt](geometry.json) repeats all 24 toy cells with a
separate combinatorial replay; the table selects the two bases fixed by the
catalog. The [N131 support receipt](n131_poly_d7_exact_support.json) enumerates
all 23,751 unordered four-tuples with repetition and checks the resulting
support by a distinct two-pair enumeration. Both enumerations use the same
curve arithmetic implementation. Its four-sum support is the probability of
*mathematical coverage* under a uniform nonidentity subgroup target; it says
nothing about how fast SAT, F4, F5, or PolyBoRi finds a witness.

The N131 d=7 polynomial factor-base rebuild took 2.045 seconds and enumerating its four-sum
support took 4.670 seconds on this host, each from one run. The separate
[pair-control receipt](n131_poly_d7_pair_control.json) took 1.892 seconds to
rebuild the base and 0.0367 seconds across 24 planted lookups. These are
stage diagnostics with no timing confidence interval. Planted lookups cannot
estimate ordinary relation yield.

The N131 ONB [HW2](n131_onb_hw2_base.json) and
[HW3](n131_onb_hw3_base.json) runs independently reported the same 3,668
usable points and 14 signed-Frobenius columns; the
[enumerated point list](n131_onb_hw2_hw3_usable_points.json) has the same
SHA-256 digest in both receipts. HW2 checked 8,647 candidate x coordinates
and took 2.367 seconds for geometric construction plus 0.464 seconds for
subgroup filtering. HW3 checked 374,792 candidate x coordinates and took
148.042 plus 17.820 seconds for those stages. These are single-run setup
costs, not online target times or a robust timing ratio. The larger HW3 scan
added no usable points: every new weight-three x has odd field trace, while
the x-coordinate of a double on this curve is `lambda^2+lambda` and therefore
has trace zero. Every point in the odd-order DLP subgroup is a double. The
four-sum and five-sum counting bounds for this same base are at most
`1.110e-26` and `8.152e-24` of uniform nonidentity subgroup targets,
respectively; these are bounds, **not measured solver yields**.

An additional exact ONB Hamming-weight-4 screen is recorded in
[its receipt](n131_onb_hw4_base.json), generated by
[the cyclic-orbit runner](run_n131_onb_hw4_base.py). It tested all 89,440
Frobenius orbits of exact weight four after reproducing the known HW2/HW3
subset: 1,392 rational x-orbits, 3,668 subgroup points, and 14 folded
columns. Exact weight four contributes 44,719 rational x-orbits and 22,269
subgroup-usable orbits. The complete `HW <= 4` base has **5,838,146 actual
subgroup points before sign/Frobenius folding** and 22,283 folded columns.
Construction and exact subgroup filtering took 1,585.5 seconds on this host.

For that frozen point set, the distinct-tuple counting upper bound
`C(B,m)/r` is `2^-23.52`, `2^-3.63`, and `2^16.04` at five, six, and
seven summands. These are combinatorial ceilings only; they do not measure
support, relation yield, PDP cost, or a target solve. Seven summands are the
first arity whose tuple-count upper bound reaches the subgroup size, and no seven-summand
solver or complete one-target pipeline has been tested. No `IC1` candidate ID
is assigned.

The [d=24](n131_poly_d24_sample.json) and [d=28](n131_poly_d28_sample.json)
receipts preserve every sampled x coordinate, lift result, subgroup check,
seed, and source digest. Each drew 1,024 distinct x values uniformly without
replacement from its full polynomial-coordinate domain. The intervals are
Wilson intervals for the usable-x fraction, scaled by twice the domain size;
they are **sample estimates**, not exact factor-base counts, and do not create
an `fb` number for a final candidate ID. The bounded sample loops took
20.757 and 24.456 seconds respectively, with no solver or target descent.

## Frozen N13 SAT stream

The source curve, six-point base, first-witness policy, one-thread solver,
stream seed 91001, and declared 32-query stream were fixed. Each target was
an ordinary nonzero subgroup point generated independently of the base. The
50 ms and 1,000 ms variants used the same target prefix. A 45-second stream
cap stopped the longer run after 31 queries. The [contract-v2 stage rows](n13_sat_stage_runs.jsonl)
retain that censoring and can be read by the catalog analyzer.

| Native per-query limit | Queries attempted | Verified decompositions | Native timeouts | New rank | Charged solver/load/lift wall time |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 50 ms | 32 | 0 | 32 | 0 | 2.169 s |
| 1,000 ms | 31 | 0 | 31 | 0 | 45.611 s |

The corresponding [50 ms](n13_sat_50ms.json) and [1,000 ms](n13_sat_1000ms.json)
raw receipts preserve every attempted target and status. One target in each
attempted prefix had an offline four-sum witness, but the solver did not
return it within its limit. The SAT circuit has a documented affine-chain
completeness caveat, so even an eventual `UNSAT` from this model would require
care before being interpreted as absence of a group decomposition. The two
all-timeout runs do not support a speed ratio or a claim that natural yield is
zero. The budget-matched solver evidence applies to `Q1`–`Q4` **only at the
PDP stage**; choosing a different final LA method does not create another
independent solver measurement.

## Catalog-wide status and next gate

The [summary](summary.json) records 300 proposals with shared exact profile
geometry, 200 with newly enumerated ONB bases, 200 with bounded polynomial
base-density samples, four with a matched N13 SAT stage receipt, 100 with only
a checked prior N53 base-count receipt, and 200 blocked isogeny searches. The other
solver and collection combinations have no exact adapter. The catalog's
`candidate_id` and `measured_cost` fields remain null; the assessment ledger
links receipts without rewriting proposal identities. Its `Q1` row separately
links the completed toy candidate and 20 paired one-target run receipts.

The [N13 follow-up](COMPLETE_N13.md) performs the first complete single-target
online comparison for a different exact SAT encoding. Further proposal cells
still need materialized factor logs and target solvers. N131 isogeny rows first need
explicit maps and subgroup/log transport. The separately measured N53 compact
four-summand root-index candidate in another experiment has a different base
and PDP method, so its online timing cannot be assigned to this catalog's N53
five-summand proposals.

The catalog [version-2 measurement contract](../../measurement_contract_v2.json)
and [analyzer](../../analyze.py) require exact five-phase online wall
time and verified paired rho for a complete one-target headline;
cold operation totals are supplementary. This change prevents setup-inclusive
or batch costs from silently becoming the headline speedup.

## Reproduce and verify

Run from the repository root with the Homebrew Python used for these receipts.
Each measurement script refuses to overwrite an existing raw receipt; choose
a new output directory for a repeat.

```sh
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/shifted-base-geometry/audit.py --independent-replay --out /tmp/ic-geometry-repeat.json
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/ic-candidate-catalog/measurements/2026-09-25/run_n13_sat.py --budget-ms 1000 --out /tmp/ic-n13-sat-repeat.json
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/ic-candidate-catalog/measurements/2026-09-25/assess.py --check
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 experiments/ic-candidate-catalog/analyze.py experiments/ic-candidate-catalog/measurements/2026-09-25/n13_sat_stage_runs.jsonl
```

The first two commands are new measurements and may produce different wall
times. The last two verify the saved ledger and stage-record semantics. The
measurement host was macOS arm64 with Python 3.14.7; peak RSS was not captured
for the SAT stage and remains `null` rather than zero.
