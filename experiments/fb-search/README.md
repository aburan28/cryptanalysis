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
