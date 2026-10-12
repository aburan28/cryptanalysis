# Factor-base search: predicting end-to-end IC cost from the factor base

This directory scores factor bases by their **predicted complete, verified DLP
cost** and validates the prediction against end-to-end runs. Every base is
labelled with the AGENTS.md `IC1` candidate ID that
[`../ic-bench`](../ic-bench/README.md) assigns it. So a prediction, its
archived base and its measured runs all share one `candidate_id`, and runs add
their `workload_id` and `run_id`.

```bash
python3 search.py scan --n 19 --l 4 5 6 7 8 --families prefix geometric geomtraceu geomtrace kertrace random --seeds 1-48
python3 search.py select results/scan-n19m2.jsonl.gz --cells 19:5 19:6 19:7 --families prefix geometric geomtraceu kertrace random
(cd ../ic-bench && python3 bench.py run --suite search --jobs 4 --record)   # the selection, end to end
python3 search.py check ../ic-bench/baseline/search.jsonl --out results/check-search.csv
python3 search.py expect --n 19 prefix:5:1 geomtraceu:6:4 --workloads 1-200  # replay estimate over 200 workloads
python3 analyze.py results/scan-n19m2.jsonl.gz results/scan-n23m2.jsonl.gz > results/summary.md
python3 analyze.py --receipts ../ic-bench/baseline/search.jsonl > results/measured-search.md
python3 trace_equation.py --n 19 --l 6 7 --out results/trace-equation.jsonl
python3 -m pytest -q test_fb_search.py
```

## Prior art first

See [`PRIOR_ART.md`](PRIOR_ART.md). Most structural results here are already known:

- The trace morphism and the trace-zero base are Kosters-Yeo 2015.
- The linear two-point oracle and the `2^(n/3)` splitting are Courtois 2016. This repository's
  [`../linearized-half-decomposition`](../linearized-half-decomposition/README.md) already
  implements that oracle, with its linearization bound.
- The online/precomputation exponent is Bernstein-Lange 2012.

What this directory adds is measurement: exact cost models, the integrated one-target pipeline,
and verified runs. It adds no new exponent.

## One-target IC versus rho, exploratory panel (harness: [`isolated/`](isolated/README.md))

`isolated/` packages the one-target comparison for the isolated benchmark service that AGENTS.md
requires for any CPU speedup claim:

- a benchmark executable with an internal online timer and scalar replay;
- a frozen 96-target panel manifest that passes the runner's schema;
- tests.

**No controlled result exists yet.** This VM fails the service's preflight on 18 counts
(`results/isolated-probe-cursor-vm.json`): it is a KVM guest with no root, no isolated cgroup
partition, no `nohz_full`, no fixed frequency and no `numactl`.

The same cases, run directly here (`results/ic-rho-exploratory.jsonl`, `"controlled": false`), give:

| base | verified pairs | IC online ms, median / mean | rho online ms, median / mean | rho/IC, geometric mean [bootstrap 95%] |
|---|---|---|---|---|
| `IC1N19Ckb1fb78PDP2htRCsampleLAgaussTDpdpISO0h286621b6083e` (n = 19) | 32/32 | 4.82 / 7.00 | 4.64 / 4.75 | 0.97 [0.62, 1.46] |
| `IC1N23Ckb1fb266PDP2htRCsampleLAgaussTDpdpISO0h33de8ed9a126` (n = 23) | 12/12 | 5.68 / 10.09 | 20.66 / 18.77 | 2.69 [1.45, 5.31] |

**Caveats.**

- Both variants use the same Python and ctypes arithmetic, which taxes rho's single walk most.
- Setup is excluded from IC's interval (about 5 s at n = 19, 30 s at n = 23). It is
  precomputation, so the fair generic comparison is Bernstein-Lange, which these tables do not beat
  (Sec. 4e of `ABOVE_LIMIT.md`).
- Single targets vary by over an order of magnitude, in both directions.

## Above the linearization limit (search record: [`ABOVE_LIMIT.md`](ABOVE_LIMIT.md))

**Question.** Is there a decomposition method that stays cheap past the linearization limit,
`l > (n + 2)/3`? There, the linear oracle leaves a `d = 3l - n - 2` dimensional residual to
enumerate, `2^d` candidates. That pins the online optimum to the limit.

**Answer: no, among everything tried.** The record holds a literature search (Sec. 1), why the
limit is where m = 2 IC touches the generic preprocessing curve `S T^2 = r` (Sec. 2), and exact,
measured candidates:

| Candidate | Result |
|---|---|
| MXL closure on the residual bilinear system (Sec. 4, 4b) | Solving degree 3 up to `d = 9`, 4 up to `d = 18`, 5 at `d = 21`, far below the generic overdetermined-bilinear degree. Still 3.6-700x costlier than enumeration at n = 41 |
| One-block t-closure, y-XL style (Sec. 4c) | 14-100x less work than the full closure at the same degree. Cheaper than enumeration only at `d <= 9`; plain certificates give a Wiedemann exponent of about `1.3 d` |
| CDCL with XOR reasoning (CryptoMiniSat) on the residual (Sec. 4d) | A constant 19-35x slower than the C enumeration from `d = 15` on |
| The repository's F4 on the same above-limit base (Sec. 4d') | `PDP2ht` is 75-680x faster per attempt |
| Meet in the middle, T-adic lifting, Möbius images, power sums, guided enumeration, partial oracles, Courtois's common-factor cover (Sec. 5) | Rejected on paper or measured break-even. The cover keeps about `2^-delta` of the yield and never beats enumeration at the best l |
| k >= 3 summands (Sec. 5b) | No exact linear oracle exists. The measured k-point methods keep the exponents `m`, `m - 1`, `ceil(m/2)` |

Online at n = 41, all in C (Sec. 4e; a prediction from measured stage costs, exploratory host):

- The best one-target cost is 5.1 ms at `l = 16` (`d = 6`), 11x faster than plain rho and 6.0x
  slower than Bernstein-Lange.
- Past that point it roughly doubles per added dimension.
- Every verified IC1 run with `d >= 8` is slower online than plain rho on the same target
  (Sec. 6).

## The linear two-point oracle in the pipeline (`PDP2ht`)

[`../pdp-degree-heuristics/htsolver.py`](../pdp-degree-heuristics/htsolver.py) is the
linearized S_3 oracle, for an arbitrary subspace V:

1. `p = x1 x2` is F_2-affine in `u = x1 + x2`.
2. Projecting onto `F / V^(2)` gives `n - dim V^(2)` linear equations in `u` alone.
3. Each solution `u` is split by one half-trace and checked for membership in V.

It is a complete PDP solver: it finds exactly the decompositions in the exact pair table on every
tested base (`test_halftrace.py`, and `halftrace.py check`). `monitor.collect --mode ht` uses it
for collection and descent, and `--rerandomize walk` replaces the per-attempt scalar multiplication
`Q + [a]G` by one addition, `Q + i [a0]G`. Over 3000 targets per base, the walk's mean attempt
count matches `1/p_dec` within error.

Beyond the linearization limit the search dimension is, measured on 54 bases
(`results/halftrace-compare.jsonl`; the mean matches within 0.1 wherever it is positive):

    max(0, dim V + dim V^(2) - n - 1 + [V in ker Tr]).

The `+[V in ker Tr]` is the [KY15] trace row becoming vacuous. So once the dimension is positive,
the trace-zero yield gain and the lost row cancel exactly. Since `dim V^(2) >= 2l - 1` for
every subspace at prime n, the online cost is at least about `2^(n/3)`: this family cannot beat
the [BL12] exponent.

**Measured, one target per run** (`online-ht` suite, 30 runs, every IC answer and every paired rho
verified, replay exact 30/30). The per-target operations match the model (median 0.999, pooled
0.998). Full table: `results/online-ht-measured.md`. Best bases, in calibrated operations
(predicted expectation, frozen calibration):

| n | plain rho `sqrt(pi r/2)` | precomputation rho, Bernstein-Lange `1.77 r^(1/3)` | best `PDP2xl` online | best `PDP2ht` online (walk) |
|---|---|---|---|---|
| 19 | 5.3e7 | 1.05e7 | 2.2e9 (41x rho, 206x BL) | 1.44e8, geomtraceu l6 (2.7x rho, 14x BL) |
| 23 | 2.6e8 | 3.26e7 | 9.0e9 (35x rho, 276x BL) | 4.44e8, geomtraceu l8 (1.7x rho, 14x BL) |

- The oracle cuts the best online cost 15-20x against our Gröbner pipeline.
- The gap to Bernstein-Lange stays at 14x at both sizes, as the shared exponent predicts.
- The product-set criterion now dominates the base choice: random and kertrace bases, with
  saturated `V^(2)`, are predicted to be 7-13x worse than the best progression at the same n.
- Measured wall-time speedups over this host's Python rho reach a geometric mean of 1.75
  (geomtraceu l8, n = 23). That number is exploratory: one target per run, an unisolated host, and
  a rho whose per-call overhead its batch price omits. It is not a claim that IC beats rho.

## Single-target online objective (the AGENTS.md default)

AGENTS.md makes one previously unseen target the default IC objective. The
headline is that target's verified online time, paired with rho on the same
point. Factor base, collection and relation linear algebra are setup, excluded
from the online interval. [`online.py`](online.py) predicts
`T_online,1` from the factor base:

```bash
python3 online.py scan --n 19 --l 4 5 6 7 8 9 --families prefix geometric geomtraceu kertrace random --seeds 1-8
python3 online.py select results/online-n19m2.jsonl results/online-n23m2.jsonl      # -> online-selected.json
(cd ../ic-bench && python3 bench.py run --suite online --jobs 4 --record)            # one target per run, paired rho
python3 online.py check ../ic-bench/baseline/online.jsonl                           # per-target ops, model vs measured
python3 online.py report ../ic-bench/baseline/online.jsonl > results/online-measured.md
```

**The model is exact in law.** Each attempt `Q + [a]G` is uniform on the
subgroup, so the attempt count is geometric in `p_dec`. The online cost is
`(1/p_dec - 1) c_fail + c_success + c_recovery`. The three prices are probed on
the exact `monitor.collect` code path: failed attempts on rerandomized probe
targets, successful attempts on points uniform on `D`, and one scalar replay.
With the replayed attempt count of each target, the model matches the measured
per-target operations as follows:

| receipts | targets | measured / predicted per target, median [p10, p90] | pooled |
|---|---|---|---|
| `search` suite (earlier always-enumerate path, `--eager`) | 351 | 1.000 [0.995, 1.008] | 1.0002 |
| `online` suite (current path) | 30 | 1.001 [0.959, 1.159] | 1.013 |

**Count solutions only when the scan asks.** Target attempts used to run the
exhaustive `(N + 2) 2^(N-1)` solution enumeration before every scan. A
refutation never reads the count, so `macaulay.degree_scan` now takes the count
lazily. The enumeration runs only when a degree ends without refutation, and
the scan output is identical; a test checks this on random systems. Collection
queries now also pay for every count the scan consults. Before, an
unsatisfiable query refuted above its first degree read the count for free.
That raises the ci-suite cold totals by at most 0.75%, and both baselines are
re-recorded. Median eager/lazy predicted online cost on the same bases:

| n | l | geomtraceu | prefix |
|---|---|---|---|
| 19 | 6 / 7 / 8 | 1.69 / 1.49 / 1.01 | 1.70 / 2.91 / 1.07 |
| 23 | 7 / 8 / 9 | 3.16 / 5.01 / 1.01 | 3.15 / 7.93 / 1.36 |

At `n = 13, m = 3` (9 variables) the saving is 1% of the target operations.

**Online-optimal bases (predictions).** Median predicted online operations ÷ rho
reference operations over 8 seeds (`results/online-n19m2.jsonl`,
`results/online-n23m2.jsonl`):

| n | l | prefix | geometric | geomtraceu | kertrace | random |
|---|---|---|---|---|---|---|
| 19 | 5 | 389 | 464 | 170 | 157 | 439 |
| 19 | 6 | 115 | 129 | 57 | 121 | 224 |
| 19 | 7 | **43** | 54 | 56 | 97 | 181 |
| 19 | 8 | 133 | 162 | 110 | 109 | 200 |
| 23 | 7 | 118 | 141 | 82 | 242 | 550 |
| 23 | 8 | 48 | 57 | **41** | 277 | 527 |
| 23 | 9 | 323 | 408 | 256 | 286 | 565 |

The online objective is not the cold objective. Larger `l` cuts the number of
attempts by about 4×, and costs nothing until the first degree stops refuting.
That happens near `n - l - (2l - 1) = 0`, i.e. `l ≈ n/3`; one step past it the
failed-attempt cost jumps 10-25×. Online attempts are nearly all refutations,
so the trace-zero base's dearer refutation (the lost equation, below) counts in
full, while its doubled yield only halves the attempt count. At `n = 19, l = 7`
the prefix base therefore beats geomtraceu.

**Measured one-target runs.** The `online` suite ran the best predicted base per
family and `n` on workloads 1-3, one target each: 10 candidates, 30 runs, all
**complete and verified, and every paired rho also verified**. The full table,
in the AGENTS.md one-target form, is in `results/online-measured.md`. The best
rows by expected cost:

| candidate | base | per workload w1 / w2 / w3: attempts, IC ms vs rho ms, online_speedup | expected online_speedup (model) | online ops / rho ops (model) |
|---|---|---|---|---|
| `IC1N19Ckb1fb150PDP2xlRCsampleLAgaussTDpdpISO0h9c8c71c913e2` | geometric l7 s6 | 50: 30.1 vs 1.39, 0.046 / 23: 14.6 vs 3.05, 0.21 / 14: 9.1 vs 10.30, 1.14 | 0.175 | 41 |
| `IC1N19Ckb1fb136PDP2xlRCsampleLAgaussTDpdpISO0h3cf513e2b056` | prefix l7 s1 | 23: 13.9 vs 1.61, 0.12 / 50: 29.6 vs 2.97, 0.10 / 32: 20.1 vs 10.64, 0.53 | 0.160 | 43 |
| `IC1N23Ckb1fb286PDP2xlRCsampleLAgaussTDpdpISO0hd5e542c02ca3` | geomtraceu l8 s5 | 83: 64.8 vs 38.23, 0.59 / 329: 234.2 vs 8.59, 0.037 / 1: 2.1 vs 7.59, 3.68 | 0.212 | 35 |

These wall times are **exploratory**: the host is shared and unisolated, so they
are not a controlled speedup claim. One target is a single draw from a geometric
law, as rho's own time also is, so single-run speedups range from 0.002 to 3.7
across the 30 runs. One geomtraceu target decomposed on its first attempt. The
expected speedup column is the mean measured rho time of the three targets
divided by the model's expected IC online time (probed wall prices). It is about
0.2: IC online is about 5× slower than this host's Python rho. In calibrated operations it is 35-43× rho. The pure-Python
rho loop pays per-call overhead that its batch-calibrated `ec_add` price does
not include, which is why the wall and operation ratios differ.

**Scaling (predictions).** All costs below are under one calibration measured
on this host for `n = 19, 23, 41` (`results/calibration-n19-23-41.json`,
`ICBCAL1h4bd79b3f965c`). Its weights are 1.03-1.18× the frozen ic-bench
calibration (except `gf_lin`), so ratios carry over. The next toy sizes with
cofactor 4 are `n = 41` (40-bit `r`) and 131; `n = 29` and 31 have cofactors
33412 and 1492 and are not comparable. Best base per `(n, l)`, from
`results/online-scale.jsonl`:

| n | l | best | attempts | c_fail | c_success | online / rho |
|---|---|---|---|---|---|---|
| 19 | 7 | prefix | 53 | 4.4e7 | 2.5e8 | 43 |
| 23 | 8 | geomtraceu | 116 | 7.9e7 | 1.0e9 | 33 |
| 41 | 11 | geomtraceu | 5.1e5 | 1.6e8 | 7.0e10 | 276 |
| 41 | 12 | geomtraceu | 1.3e5 | 1.8e8 | 3.0e11 | 81 |
| 41 | 13 | geomtraceu | 3.3e4 | 2.1e8 | 1.3e12 | **28.5** |

For trace-zero bases, `p_dec ≈ 2^(2l - n)`. While the first degree refutes
(`l ≲ n/3`), the failed-attempt cost grows only polynomially, so the online
attempts scale like `2^(n/3)` against rho's `2^(n/2)`. This is the classic
precomputation trade-off: setup grows like `2^(2n/3)` and is excluded from the
online metric.

The best ratio falls from 43 to 33 to 28.5 as `n` goes 19, 23, 41. At
`n = 41, l = 13` the `l = 12-13` yields come from the psi-class formula, which
is within 2% of the exact yield wherever both exist, with successes planted as
psi-compatible pair sums (their cost is within 0.5% of uniform-`D` successes).

**The next bottleneck was the one successful attempt** (resolved by `PDP2ht` above, which reads
the solutions off a linear system instead of enumerating them). Its exhaustive
enumeration costs `(N + 2) 2^(N-1)` at `N = 2l`: 1.3e12 rps at `n = 41, l = 13`,
4.5 times the whole rho reference. It also caps `l` at 13, the 26-variable
limit. The `l ≈ n/3` regime needs the solutions read from the Macaulay echelon
form (standard monomials and multiplication matrices) instead of enumerated.

The cold, three-target material below is supplementary under the one-target rules.

Scope: m = 2 point decomposition (`PDP2xl`) on the toy Koblitz curves
`EC1N19Ckb1ha7a2e0b48125` and `EC1N23Ckb1h32a1300cea95`
(`y^2 + xy = x^3 + 1`, cofactor 4), with the ic-bench pipeline
`RCsample LAgauss TDpdp ISO0`. Costs are in the ic-bench calibrated unit (rps,
calibration `ICBCAL1ha3f79d4aaca9`) for 3 targets with cold caches.

## The model is exact at m = 2

A collection run draws ordinary queries `R = [k]G` and adds every verified
two-point decomposition of `R` to an echelon form mod `r`, until it reaches the
achievable rank. Every two-point decomposition of every subgroup point can be
enumerated from the factor base: they are the pair sums whose `psi` component
vanishes. The query sequence is therefore fixed by the base and the workload:

- **Replay** (`replay_workload`). Feeding a workload's query and
  rerandomization streams through this lookup reproduces the collection and
  descent query counts of **all 117 measured `search` runs and the 3 recorded
  `ci` runs exactly**. The Macaulay solver found every decomposition: no run
  had a budget or lift failure.
- **Law** (`rank_process`). A query decomposes with probability
  `p_dec = |D| / (r - 1)`, a decomposable query is uniform on `D`, and it adds
  all of its rows. Monte Carlo over this law gives the mean and sd of the
  collection length. Over 200 replayed workloads the replay means match the law:
  prefix `l = 5` gives 25002 replayed against 24799 predicted, and geomtraceu
  `l = 6` s30 gives 9062 against 9087. Descent is geometric in `p_dec`.
- **Price** (`probe`). `monitor.collect` runs 200 queries from an independent
  probe stream (`fbsearch-probe|<curve-id>|1`) under opcount. The predicted
  total is `fixed + price_per_query * (E[collection] + targets / p_dec)`.
  Across the 117 runs, measured total / (probe price × replayed queries + fixed)
  has median 1.026 and range [0.906, 1.193].

Covering every column (the coupon estimate in `monitor.py`) is necessary but not
sufficient. A row joins two columns, and a component is determined only once it
carries a cycle. Over the 1847 scanned bases, the coupon estimate falls short of
the law by a median of 3%, and by 20% or more for a tenth of them. For the three
`ci` bases the shortfall is 7-11%.

One run is a noisy measurement of a base. The collection length has sd ≈ 35% of
its mean, and prefix `l = 5` drew 45280, 39707 and 39226 queries on workloads
1-3 against an expectation of 27937. Compare bases by expected cost:
`search.py expect` replays many workloads without running the solver. These are
**replay estimates**, not measured runs.

## Where the cost goes, and when the solving degree matters

Median price per query at `n = 19` over 48 seeds, from the probes:

| l | geometric | geomtraceu | kertrace | random | PDP share (geomtraceu / kertrace) |
|---|---|---|---|---|---|
| 5 | 2.02e7 | 2.02e7 | 2.03e7 | 2.03e7 | 0.5% / 1.0% |
| 6 | 2.66e7 | 2.68e7 | 3.05e7 | 3.03e7 | 1.6% / 13.6% |
| 7 | 3.78e7 | 4.54e7 | 7.49e7 | 7.41e7 | 25.8% / 55.0% |
| 8 | 1.93e8 | 3.01e8 | 3.29e8 | 2.34e8 | 86.0% / 87.2% |

At `l <= 5` the Macaulay solve is under 1% of a query. The cost is building the
Weil-descent system (63%), field multiplications (22%) and group operations
(14%). The end-to-end cost is then just the query count, and the solving degree
does not enter. From `l = 6` the product profile starts to matter, since the
minimal-profile progressions keep `dim V^(2) = 2l - 1`. At `l = 8` the solve
dominates.

## Trace-zero bases trade one equation for twice the yield

On this curve `S_3 = (x1 x2 + x1 x3 + x2 x3)^2 + x1 x2 x3 + 1`. With
`u = x1 x2 / x3`, `S_3 / x3^2 = u^2 + u + x1^2 + x2^2 + 1/x3^2`, so

```text
Tr(S_3 / x3^2) = Tr(x1) + Tr(x2) + Tr(1/x3).
```

A subgroup target lies in 2E and lifts, so `Tr(xR) = 0` and `Tr(1/xR) = 0`.
Every descent system therefore contains the **linear** equation
`Tr(x1) + Tr(x2) = 0`, as the combination `Tr(S_3 / xR^2)` of its `n`
coordinate equations. This equation is why a generic base loses half of its pairs.
If `V` lies in ker(Tr), every pair passes it. That doubles `p_dec`, but the
combination then vanishes identically and the system keeps only `n - 1`
equations. The test suite checks the identity, and `trace_equation.py` measures
its effect on 120 identical queries (`results/trace-equation.jsonl`):

| n, l | base | equation rank | refutation degree | Macaulay ops per refutation |
|---|---|---|---|---|
| 19, 7 | geometric | 19 (≈78%), 18 | 2 (≈90%), 3 | 3.4e3-4.3e3 |
| 19, 7 | geomtraceu | never 19: 18 (≈86%), 17 | 2 (50-65%), 3 | 8.9e3-1.2e4 |
| 19, 7 | random / kertrace | always 19 / always 18 | 3 / 3 | 1.1e5 / 9.5e4 |
| 23, 9 | geometric | 23 (≈94%) | 3 (≈90%) | 7.2e4-1.4e5 |
| 23, 9 | geomtraceu | never 23 | 3 (≈95%) | 6.4e5-6.7e5 |

The lost equation is nearly free when the degree is already fixed by a saturated
`V^(2)` (random against kertrace). It costs a degree step for progressions near a
threshold (geometric against geomtraceu at `l = 7`), and it costs 5-9× within the
degree-3 closure at `n = 23, l = 9`. The yield doubling wins while the solve is
a small part of a query. In these scans, trace-zero progressions win at
`n = 19, l <= 8` and at `n = 23, l <= 8`, and lose at `n = 23, l = 9`
(1.11e13 against 8.55e12 for plain progressions). At ECC2K-130 scale the solve
dominates, so the two effects must be weighed at the operating dimension. The
fitted degree rule from `../pdp-degree-heuristics` should use `n - 1` equations
for a trace-zero base.

## Scan results (predictions)

1850 bases were scored: 48 seeds per family at `n = 19, l = 4..8` and 32 seeds at
`n = 23, l = 5..9`. The full tables are in `results/summary.md`; the raw
records are `results/scan-n19m2.jsonl.gz` and `results/scan-n23m2.jsonl.gz`
(`kind: prediction`; `scan` appends plain JSONL, committed as deterministic gzip). Median predicted cost over seeds:

| n | l | prefix | geometric | geomtraceu | kertrace | random |
|---|---|---|---|---|---|---|
| 19 | 5 | 5.71e11 | 8.21e11 | 3.55e11 | 3.72e11 | 8.13e11 |
| 19 | 6 | 8.34e11 | 5.37e11 | **2.51e11** | 2.75e11 | 6.16e11 |
| 19 | 7 | 3.88e11 | 4.02e11 | **2.32e11** | 3.88e11 | 7.92e11 |
| 19 | 8 | 8.41e11 | 1.16e12 | 8.79e11 | 9.63e11 | 1.38e12 |
| 23 | 6 | 8.62e12 | 9.81e12 | 4.65e12 | 4.63e12 | 1.00e13 |
| 23 | 7 | 5.79e12 | 6.54e12 | 3.37e12 | 3.97e12 | 8.48e12 |
| 23 | 8 | 4.26e12 | 4.89e12 | **2.60e12** | 7.05e12 | 1.33e13 |
| 23 | 9 | 7.86e12 | 8.55e12 | 1.11e13 | 1.33e13 | 2.31e13 |

- **Family and dimension first.** Trace-zero halves the queries at every `l`.
  A progression keeps the solve cheap once `l >= 6`. The best dimension is
  `l = 6-7` at `n = 19` and `l = 8` at `n = 23`.
- **Seeds second.** Within one family and `l`, the best of 32-48 seeds costs
  0.63-0.87× the median seed for geomtraceu. The best single predictor of the
  rank within a cell is the **rarest column's hit rate** (Spearman -0.83 to
  -0.95 at `l <= 6`). A base is only as good as the column it reaches last. B
  and `p_dec` are weaker (-0.4 to -0.9). The product profile is constant across
  a progression family. At the largest `l`, where the solve dominates, no
  structural feature ranks seeds well (|Spearman| < 0.4).
- The prefix base is itself a progression, `g = z`. At `l = 7-8` its solve is
  25-30% cheaper per query than the median geometric progression. A likely
  reason, not checked here, is that products in `V^(2)` stay below degree `n`
  without reduction, which keeps the equations sparse.

## End-to-end validation (measured)

The `search` suite ran the best, median and worst predicted seed per family at
`n = 19, l = 5, 6, 7`, plus the prefix base, on workloads 1-3: 39 candidates and
117 runs. **All 117 are complete, verified DLPs** with scalar replay of every
target. The receipts are `../ic-bench/baseline/search.jsonl`, rows are appended to
`../ic-bench/history.csv`, and the manifests are in `../ic-bench/candidates/`.
The full per-candidate table is in `results/measured-search.md` and the per-run
join is in `results/check-search.csv`.

- Replay of the query counts is exact in 117/117 runs.
- 83/117 collection lengths fall within 1 sd of the predicted mean; the mean z is +0.11.
- Predicted cost against the mean of 3 measured runs: Spearman 0.924 over the 39
  candidates. Pooled measured/predicted is 1.027.

Headline, `n = 19`, 3 targets, cold. Rho reference: `sqrt(pi r / 2)` =
5.31e7 rps. Floor: `sqrt(pi r / (4 n))` = 8.68e6 rps. Both are fixed in the
workload records, with `r` = 130873.

| candidate | base | verified | measured total (w1-3 mean) | paired speedup, w1-3 | replay estimate, 200 workloads [95% CI] | expected speedup | x rho | x floor | S = total / sqrt(r) |
|---|---|---|---|---|---|---|---|---|---|
| `IC1N19Ckb1fb26PDP2xlRCsampleLAgaussTDpdpISO0hc0cc43a2b0ee` | prefix l5 (baseline) | 9/9 targets | 8.49e11 | 1 | 5.66e11 [5.39e11, 5.96e11] | 1 | 1.60e4 | 9.78e4 | 2.35e9 |
| `IC1N19Ckb1fb32PDP2xlRCsampleLAgaussTDpdpISO0h7f4bc7348bda` | geomtrace l5 s1 (ci suite) | not in suite | - | - | 3.53e11 [3.36e11, 3.70e11] | 1.60 | - | - | - |
| `IC1N19Ckb1fb78PDP2xlRCsampleLAgaussTDpdpISO0h025a8b000651` | geomtraceu l6 s4 (best l6) | 9/9 targets | 2.06e11 | 4.21 [2.99, 5.37] | 2.02e11 [1.94e11, 2.11e11] | 2.80 | 3.87e3 | 2.37e4 | 5.69e8 |
| `IC1N19Ckb1fb130PDP2xlRCsampleLAgaussTDpdpISO0hb34aa06f6d50` | geomtraceu l7 s3 (best predicted) | 9/9 targets | 2.96e11 | 2.89 [2.38, 3.28] | 1.99e11 [1.92e11, 2.06e11] | 2.84 | 5.56e3 | 3.41e4 | 8.17e8 |
| `IC1N19Ckb1fb62PDP2xlRCsampleLAgaussTDpdpISO0hb0c0716f6e86` | geomtraceu l6 s30 (median seed) | 9/9 targets | 2.35e11 | 3.71 [2.97, 4.60] | 2.53e11 [2.43e11, 2.63e11] | 2.24 | 4.43e3 | 2.71e4 | 6.50e8 |

The measured paired speedups on workloads 1-3 overstate the expectation,
because the prefix baseline drew upper-tail workloads. Over 200 workloads, the
best search base is **2.8× the prefix `l = 5` base and 1.75× the `ci` suite's
geomtrace `l = 5` s1 base**. About 2.2× of that comes from the family and
dimension (median seed) and 1.25× from seed selection. Every measured cell
remains 3.9e3-4.4e4 times the rho reference. In this implementation the toy IC
pipeline is far above rho, and this work moves it by a constant factor.

## Archive

The 39 selected bases, and the best `n = 23` base of each family, are archived
by [`../fb-archive`](../fb-archive/README.md) (`index.csv`; `fbarchive.py
verify` passes). Any base here can be rebuilt from `(n, family, l, seed)`, and
its exact basis is recorded in the `IC1` manifest.

## Files

- `search.py`: the model (`decomposition_lookup`, `rank_process`,
  `replay_workload`, `probe`, `score`) and the `scan`, `select`, `check` and
  `expect` commands.
- `analyze.py`: the scan summary and the measured table.
- `trace_equation.py`: equation rank, degree and cost with and without ker(Tr).
- `selected.json`: the picks the ic-bench `search` suite runs.
- `results/`: scans (`kind: prediction`), replay estimates
  (`kind: replay_estimate`), trace-equation stage records, the measured join, and logs.

Limits: the exact law is implemented for m = 2. At m = 3 (the `n = 13` suites)
the solve is about 40% of the cost, so the degree matters directly, and the
decomposition table would need improper rows. The toy curves have prime `n`, so
there are no subfield effects.
