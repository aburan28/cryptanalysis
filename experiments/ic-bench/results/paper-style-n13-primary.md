# Index calculus collection and matrix cost sample

Fresh `primary` suite on a local CPU: nine complete, independently verified
one-target DLP runs, three frozen targets paired across prefix, geomtrace and
random bases. The [raw receipts](paper-style-n13-primary.jsonl) retain workload,
candidate, source and calibration identities; corresponding manifests are in
`../candidates/`. Reproduce the tables with:

```bash
python3 experiments/ic-bench/cost_table.py \
  experiments/ic-bench/results/paper-style-n13-primary.jsonl --paper 2 131 32 4
```

At n=13, m=3, collection consumed about 2.48e10–5.67e10 calibrated rps per
run. Matrix build plus final LA cost about 0.74e6–2.28e6 rps. Every paired
one-target rho run was faster; rho/IC online time ranged from roughly 0.0049
to 0.041. These are implementation measurements on tiny curves, not a scaling
claim for ECC2K-130 or a test of the paper's invariant factor-base method.

## Observed IC costs

| Method / workload | status | B → columns | queries → verified → rank | Relation collection (ops; ms) | mean H (ops/system) | Final matrix (ops; ms) | queries/rank | collection ops/rank | one-target rho/IC online |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| binary PDP / n13m3l3-prefix-s1-mxl-w1 / 026858681e66 / 5415881dcda3 | complete ✓ | 8 → 4 | 134 → 7 → 4 | 3.02e+10; 177 | 1.26e+08 | 2.28e+06; 0.165 | 33.5 | 7.55e+09 | 0.0144 |
| binary PDP / n13m3l3-geomtrace-s1-mxl-w1 / 026858681e66 / 1aa613bd0dd8 | complete ✓ | 8 → 4 | 143 → 4 → 4 | 3.14e+10; 181 | 1.16e+08 | 1.67e+06; 0.149 | 35.8 | 7.84e+09 | 0.0347 |
| binary PDP / n13m3l3-random-s1-mxl-w1 / 026858681e66 / eec64c9bb4df | complete ✓ | 4 → 2 | 169 → 2 → 2 | 3.38e+10; 195 | 9.7e+07 | 857,552; 0.137 | 84.5 | 1.69e+10 | 0.04 |
| binary PDP / n13m3l3-prefix-s1-mxl-w2 / 398002869ca3 / 5415881dcda3 | complete ✓ | 8 → 4 | 186 → 5 → 4 | 4e+10; 229 | 1.16e+08 | 1.88e+06; 0.196 | 46.5 | 1e+10 | 0.00493 |
| binary PDP / n13m3l3-geomtrace-s1-mxl-w2 / 398002869ca3 / 1aa613bd0dd8 | complete ✓ | 8 → 4 | 161 → 4 → 4 | 3.51e+10; 200 | 1.14e+08 | 1.55e+06; 0.222 | 40.2 | 8.78e+09 | 0.041 |
| binary PDP / n13m3l3-random-s1-mxl-w2 / 398002869ca3 / eec64c9bb4df | complete ✓ | 4 → 2 | 284 → 3 → 2 | 5.67e+10; 335 | 9.62e+07 | 857,552; 0.331 | 142 | 2.83e+10 | 0.019 |
| binary PDP / n13m3l3-prefix-s1-mxl-w3 / aa4b90819f2f / 5415881dcda3 | complete ✓ | 8 → 4 | 207 → 5 → 4 | 4.44e+10; 254 | 1.15e+08 | 2.12e+06; 0.219 | 51.8 | 1.11e+10 | 0.0056 |
| binary PDP / n13m3l3-geomtrace-s1-mxl-w3 / aa4b90819f2f / 1aa613bd0dd8 | complete ✓ | 8 → 4 | 111 → 4 → 4 | 2.48e+10; 144 | 1.2e+08 | 1.8e+06; 0.158 | 27.8 | 6.19e+09 | 0.0207 |
| binary PDP / n13m3l3-random-s1-mxl-w3 / aa4b90819f2f / eec64c9bb4df | complete ✓ | 4 → 2 | 284 → 2 → 2 | 5.62e+10; 329 | 9.46e+07 | 736,712; 0.206 | 142 | 2.81e+10 | 0.00524 |

| Workload / candidate suffix | verified-query yield (Wilson 95%) | unsat / timeout / budget / error | rank / columns | cold IC / one-rho ops |
|---|---:|---:|---:|---:|
| 026858681e66 / 5415881dcda3 | [2.55%, 10.4%] | 127 / 0 / 0 / 0 | 4 / 4 | 8.21e+03 |
| 026858681e66 / 1aa613bd0dd8 | [1.09%, 6.97%] | 139 / 0 / 0 / 0 | 4 / 4 | 7.6e+03 |
| 026858681e66 / eec64c9bb4df | [0.325%, 4.21%] | 167 / 0 / 0 / 0 | 2 / 2 | 8.04e+03 |
| 398002869ca3 / 5415881dcda3 | [1.15%, 6.14%] | 181 / 0 / 0 / 0 | 4 / 4 | 1.4e+04 |
| 398002869ca3 / 1aa613bd0dd8 | [0.97%, 6.21%] | 157 / 0 / 0 / 0 | 4 / 4 | 8.49e+03 |
| 398002869ca3 / eec64c9bb4df | [0.36%, 3.06%] | 281 / 0 / 0 / 0 | 2 / 2 | 1.43e+04 |
| aa4b90819f2f / 5415881dcda3 | [1.04%, 5.53%] | 202 / 0 / 0 / 0 | 4 / 4 | 1.37e+04 |
| aa4b90819f2f / 1aa613bd0dd8 | [1.41%, 8.9%] | 107 / 0 / 0 / 0 | 4 / 4 | 7.11e+03 |
| aa4b90819f2f / eec64c9bb4df | [0.193%, 2.53%] | 282 / 0 / 0 / 0 | 2 / 2 | 1.68e+04 |

Each row uses its receipt's native unit: binary `rps` and prime counted group operations. Times are milliseconds on the run host. Do not compare absolute operations between regimes. The rho/IC column uses paired, verified, one-target **online wall time** (values above 1 favor IC).
Collection includes failed searches. In binary receipts it is queries + PDP + relation checks; mean H is measured PDP work divided by *all* PDP attempts. Matrix includes build + final relation LA, not the internal Macaulay elimination. Prime receipts put counted oracle/probe work in precompute; their final graph LA is not separately metered, so its entry is unknown rather than zero.
The yield interval uses binary positive-query counts; prime relation batches have no Bernoulli interval. Cold IC/rho is supplementary and compares counted operations for one target. Zero rank leaves cost per independent row unknown. Incomplete or unverified runs cannot show an end-to-end speedup. The observed rank is checked, never multiplied by a theoretical Frobenius factor.

## Paper model (q=2, n=131, n′=32, m=4, k=3)

| Method | Expected polynomial systems | Relation collection cost | LA asymptotic proxy |
|---|---:|---:|---:|
| General IC | 5.154e+10 | 5.154e+10 × H1 | O(7.379e+19) |
| m distinct bases | 8.59e+09 | 8.59e+09 × H1 | O(1.181e+21) |
| Koblitz symmetry | 2.147e+09 | 2.147e+09 × H2 | O(7.379e+19) |
| one Frobenius invariant base | 1.611e+09 | 1.611e+09 × H3 | O(4.3e+15) |
| invariant + symmetry | 6.557e+07 | 6.557e+07 × H4 | O(6.88e+16) |

Source: https://sacworkshop.org/SAC20/files/preproceedings/18-IndexCalculus.pdf (Table 1). These are heuristic system counts and asymptotic LA proxies, **not measured timings**. H1–H4 are different, unmeasured per-system solve costs. The Frobenius rows require a subfield curve, an invariant usable factor base and the claimed independent orbit relations; no measured candidate is assigned these gains automatically.

Dimension check: ord_131(2)=130, so no Frobenius-invariant F_2-linear subspace of F_2^131 has dimension 32. The invariant-vector-space rows are formal substitutions here, not applicable constructions. Nonlinear invariant bases need separate evidence.
