# Batched C half-trace PDP: complete n = 41 index calculus against C rho, one target

This directory holds a faster point-decomposition (PDP) oracle for m = 2 subspace index calculus, and a
complete, verified pipeline that uses it on `EC1N41Ckb1h9d49bc0affd2`. That is the toy Koblitz curve
`y^2 + xy = x^3 + 1` over `F_2^41`, with cofactor 4 and a 40-bit subgroup order r. Paired runs compare it,
one target at a time, with the previous C oracle, with the Python oracle that the `ic-bench` IC1 runs use,
and with parallel-collision Pollard rho in the same C arithmetic.

```bash
python3 pipeline.py prepare --n 41 --family geomtraceu --l 15                       # collection + logs, about 1 min
python3 pipeline.py panel --n 41 --l 15 --targets 64 --variants v1 v0 rho --out panel-n41.jsonl
python3 pipeline.py summarize results/panel-n41.jsonl
python3 -m pytest -q .
```

## What changed in the PDP

The mathematics is the half-trace projection of `../pdp-degree-heuristics/htsolver.py` (Courtois 2016):
for a target abscissa S, the unknowns are the l coordinates of `u = X + Y` and the Artin-Schreier bit
eps. Projecting onto `F / V^(2)` gives a small linear system, and each solution u is split by one half-trace
and kept if `X in V`. Every oracle here returns exactly the same decompositions:

- `test_htfast.py` checks v1 and v0 against `HalfTraceSolver.decompose` on six bases at n = 19 and 23,
  including above-limit and trace-kernel bases.
- In all 256 paired n = 41 runs below, v1 and v0 stop at the same walk attempt index.

| oracle | per attempt |
|---|---|
| py: `HalfTraceSolver.decompose` (the ic-bench `online-ht` IC1 oracle) | Python bookkeeping around ctypes field calls |
| v0: `htfast.c htf_run_v0`, a port of `fb-search/htenum.c ht_attempt_batch` | One affine walk step with its own inversion, an inversion of S, l field multiplications and `nchk * l` parities to build the system, one elimination per eps, one batch inversion per eps branch |
| v1: `htfast.c htf_run` | See the four changes below |

v1 makes four structural changes:

1. **Batched inversions.** W = 32 walk points advance together, with one Montgomery inversion serving the
   32 walk denominators and one serving the 32 values `1/S`.
2. **System built from tables.** The columns `pi(S HT(v_j^2))` and `pi(S)` are linear in S, so they are
   read from byte tables, with no field multiplication.
3. **One elimination.** eps is an unknown, so a single reduced-echelon elimination over `l + 1`
   unknowns replaces two. Its column bits and combination mask share one 64-bit word, and every pass
   over the pivots is branch-free.
4. **Shared candidate inversion.** All candidates of a round share one batched inversion of `u^2`.

Two arithmetic changes apply to v0, v1 and rho alike, so the comparisons stay like-for-like:

- a shift-and-XOR reduction for the sparse moduli in place of folding with carry-less multiplications;
- four interleaved product chains in every batched inversion.

All are built with gcc 13 `-O3 -march=native` (clang 18's unroller made the elimination 3x slower).

**Per attempt on this host, n = 41, geomtraceu seed 1** (W = 32, single core):

| l | effective columns | candidates per attempt | v1 ns | v0 ns | v0 / v1 |
|---|---|---|---|---|---|
| 13 | 4077 | 0.2 | 246 | 2524 | 10.3 |
| 14 | 8172 | 2 | 340 | 3110 | 9.1 |
| 15 | 16346 | 16 | 634 | 3898 | 6.1 |
| 16 | 32909 | 128 | 3124 | 5036 | 1.6 |

**Where v1's time goes.** At l = 15, an attempt costs:

- 35 ns for the walk step and `1/S`;
- 15 ns for the right-hand side;
- 25 ns to build the system;
- about 150-190 ns for the elimination;
- about 22 ns per candidate (5 field multiplications and 12 table reads).

Above the limit the candidates dominate, and their number is `2^(d+1)`. Sec. 4 of
`../fb-search/ABOVE_LIMIT.md` found no sub-`2^d` way to enumerate them. Factor-base families were also
compared at l = 15 and 16:

- **geomtraceu is best.** Every subgroup target has `Tr(sqrt(b)/S) = 0`, so a trace-kernel base loses no
  targets and doubles the yield.
- **Bases outside the trace kernel lose.** geometric and prefix halve the candidates but also the yield,
  and cost 1.6-1.8x more per hit.
- **kertrace and random are unusable.** They have `dim V^(2) = n`, which means 2^15 or more candidates per
  attempt.

## Pipeline

- **Factor base.** `FactorBase` with folded `+-pi_r` columns.
- **Collection (`RCwalk`).** W = 256 walks `R_i = [k0]G + i [a]G`. Every verified decomposition becomes a
  two-term row with right-hand side `k0 + i a`, until there are 2 x columns rows.
- **Relation linear algebra (`LAgraph`).** The rows are edges of a gain graph. One breadth-first pass per
  component writes every column as `alpha t + beta`, and a cycle with nonzero t coefficient fixes t. Every
  row is checked (0 inconsistent rows), and every fixed log is verified as `[x]G = rep`.
- **Descent (`TDpdp`).** `Q + i [a0]G`, until a decomposition evaluates on the logs. The log is checked as
  `[log Q]G = Q` inside the online interval.

**Precompute at n = 41**, one core. This is supplementary, target-independent, and outside the online metric:

| l | columns | relation collection | attempts | rows | gain-graph solve | log checks | columns with a verified log |
|---|---|---|---|---|---|---|---|
| 14 | 8172 | 47 s | 1.34e8 | 16344 | 0.06 s | 0.17 s | 7852 (96%) |
| 15 | 16346 | 44 s | 6.70e7 | 32692 | 0.08 s | 0.33 s | 15743 (96%) |
| 16 | 32909 | 101 s | 3.31e7 | 65823 | 0.19 s | 0.68 s | 31733 (96%) |
| 17 | 65549 | 360 s | 1.67e7 | 131102 | 0.41 s | 1.26 s | 62824 (96%) |

These collections ran under an earlier, slower build of the same v1 kernel. Every row they produced is
verified, and the logs they gave are checked. The roughly 4% of columns without a log sit in small
components. A target that decomposes onto one of them is skipped, and the walk continues; that cost is
charged to the target.

## Results: one target, online, n = 41 (`results/panel-n41.jsonl`)

**Protocol.**

- 64 frozen targets `Q = [s]G`, with `s = 1 + SHA-256("ic-online-c-v1:<curve_id>:<i>") mod (r - 1)`.
- Each target is solved by v1, v0 and rho in the same process, alternating the order.
- **IC interval.** It starts with the first target-dependent operation: `[a0]G`, then the walk. It ends after
  `[log Q]G = Q`. Its five phases (`target_query`, `target_pdp`, `target_relation_check`,
  `target_descent`, `target_recovery_check`) sum to it exactly.
- **Rho interval.** It covers building the Q-dependent walk table and starts, the walk, and the verified
  collision.
- **Rho method.** A 32-entry r-adding walk (`T_j = [c_j]G + e_j Q`), 64 parallel walks with one inversion per
  round, and distinguished points stored in a C hash table. The target-independent `[c_j]G` and `[a_w]G`
  are computed before rho's clock. IC's `[a0]G` stays inside IC's clock.
- **Rho cost measured.** 0.995M steps on average (1.07 x `sqrt(pi r / 2)`), at 20.2 ns per step.

| candidate | online PDP | IC verified | IC online ms, median [IQR] | mean | rho median ms | rho/IC, geometric mean [bootstrap 95%] |
|---|---|---|---|---|---|---|
| `IC1N41Ckb1fb16344PDP2htRCwalkLAgraphTDpdpISO0hda7a2aba913b` (l = 14) | v1 | 64/64 | 2.18 [1.29, 4.64] | 3.30 | 20.9 | 9.30 [7.00, 12.39] |
| `IC1N41Ckb1fb16344PDP2htRCwalkLAgraphTDpdpISO0h691a9d92b8ea` (l = 14) | v0 | 64/64 | 19.9 [10.5, 43.0] | 30.4 | 20.9 | 1.19 [0.83, 1.76] |
| `IC1N41Ckb1fb32692PDP2htRCwalkLAgraphTDpdpISO0hcf3a61dd7ea0` (l = 15) | **v1** | 64/64 | **1.75** [0.71, 3.14] | **2.00** | 20.6 | **13.91** [10.36, 18.89] |
| `IC1N41Ckb1fb32692PDP2htRCwalkLAgraphTDpdpISO0hf4e6b4688ec8` (l = 15) | v0 | 64/64 | 9.89 [3.32, 17.67] | 11.30 | 20.6 | 2.88 [2.06, 4.15] |
| `IC1N41Ckb1fb65818PDP2htRCwalkLAgraphTDpdpISO0h65e7d04563b1` (l = 16) | v1 | 64/64 | 1.61 [0.75, 2.45] | 2.01 | 20.4 | 12.90 [10.24, 16.21] |
| `IC1N41Ckb1fb65818PDP2htRCwalkLAgraphTDpdpISO0h38d49fd9f845` (l = 16) | v0 | 64/64 | 3.07 [1.47, 5.10] | 4.09 | 20.4 | 6.97 [5.36, 9.12] |
| `IC1N41Ckb1fb131098PDP2htRCwalkLAgraphTDpdpISO0h0a240b346b12` (l = 17) | v1 | 64/64 | 3.03 [1.60, 4.47] | 3.59 | 20.4 | 6.53 [5.23, 8.01] |
| `IC1N41Ckb1fb131098PDP2htRCwalkLAgraphTDpdpISO0hc908fa00f498` (l = 17) | v0 | 64/64 | 3.70 [1.93, 5.80] | 4.59 | 20.4 | 5.87 [4.46, 7.69] |

**The Python oracle**, on 6 targets at l = 15 (`results/panel-n41-py.jsonl`):

| candidate | online PDP | IC verified | IC online ms, median | rho/IC, geometric mean |
|---|---|---|---|---|
| `IC1N41Ckb1fb32692PDP2htRCwalkLAgraphTDpdpISO0h621e257c93dd` | py | 6/6 | 542 | 0.06 |
| `IC1N41Ckb1fb32692PDP2htRCwalkLAgraphTDpdpISO0hcf3a61dd7ea0` | v1 | 6/6 | 1.13 | 22.5 |

**Paired v0 / v1 online ratio** (same targets, same logs, same attempt index):

- 7.8x at l = 14;
- 4.8x at l = 15;
- 1.85x at l = 16;
- 1.11x at l = 17.

**Best against best**, by mean online time: v1 at l = 15 (2.00 ms) against v0 at l = 16 (4.09 ms) is 2.0x.
Against the Python oracle on the same targets, v1 is about 480x faster.

### Reading

- **The PDP change is what moves the end-to-end number.**
  - **Below and at the limit (l <= 15)** the old oracle spent most of each attempt on inversions and on
    building and eliminating the system. v1 removes 85-90% of that.
  - **Above it (l = 16, 17)** the `2^(d+1)` candidates dominate both oracles, so the gain shrinks.
  - **The optimum moves down to l = 15-16.** v1's optimum is 2.0 ms mean, against 4.1 ms for v0 at its own
    optimum, l = 16.
- **Against plain rho.** Plain rho costs `sqrt(pi r / 2)` steps in the same arithmetic. IC at l = 15 is
  13.9x faster online [10.4, 18.9], on 64 of 64 verified pairs.
- **Against the Koblitz rho floor (prediction only).** Rho on `{+-tau^j P}` classes needs `sqrt(2n)` = 9.1x
  fewer steps. `rho_floor_estimate_ns` charges those steps at the measured plain step cost, with
  canonicalization free. That estimate is 1.05x IC's mean at l = 15, so IC only ties it. No folded rho
  was implemented; in a polynomial basis, finding the class representative costs about n squarings per step.
- **Against rho with precomputation.** Bernstein-Lange rho with precomputation (`1.77 r^(1/3)` steps, about
  0.3 ms here) remains faster than IC online, as `../fb-search/ABOVE_LIMIT.md` Sec. 4e predicts.

### Caveats

- **Exploratory only.** Wall times come from an unisolated 4-vCPU cloud VM (`host.controlled: false`), so
  this is not a controlled speedup claim under the AGENTS.md isolation gate. Concurrent jobs on this VM
  slowed single-thread kernels by up to 2x. The panels ran alone.
- **Field size.** n = 41 is the only Koblitz `b = 1` size from 37 to 61 here with a small cofactor. With a
  large cofactor, rho gets cheaper while IC's cost still follows 2^n, so other sizes would not be a fair
  scaling series.
- **Further constant factors.** AVX-512 `vpclmulqdq` is available on this host. Vectorizing the candidate
  stage and the elimination would speed up IC by a constant factor. Vectorizing the rho walk would do the
  same for rho, so neither was done.
- **Provenance.** Rows were produced at commit `2271dfe4`. `results/manifests/` holds every candidate and
  workload record, with source digests. The precompute caches (`cache/`, about 3.5 MB) are not committed;
  `pipeline.py prepare` rebuilds them.
