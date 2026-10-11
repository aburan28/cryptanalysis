# Index-calculus performance plan

A standing plan for making the whole index-calculus attack faster, run as
a loop: **measure → change one thing → re-measure against the frozen
baseline → keep or revert → record**. Every step lands with its before
and after numbers, and every change that moves a pinned counter freezes a
new reference beside the old one rather than overwriting it
(`docs/ic/ci/README.md`, `AGENTS.md` §3 and §7).

Started 2026-09-24 on `main` at `9250d0cc` (after #694).

## 1. Where the time goes today

| stage | what exists | measured cost | measured in CI? |
|:--|:--|:--|:--|
| Whole pipeline, m = 3, pair table | `ic workflow`, three frozen rungs | k0n53: 1.65 s end to end (collection 0.95 s, descent 0.70 s) | **yes**, `ic-e2e-benchmark.yml`, reference v5 |
| Decomposition by summation polynomial + Gröbner, m = 2 | `koblitz_groebner` matrix-F4 + splitting | ≤ 0.2 s per stage ladder rung; Macaulay **build** ≈ 60× the **reduce** | no (`groebner_stage_bench`, compared by hand) |
| Same, m = 3 (chained S₃) | same | solving degree 6; 20,240 × 20,686 matrix, 27.4 s dense / 2.9 s sparse; 17-variable cell 82–494 s end to end; 27-variable cells estimated at days | no |
| m = 4 | enumeration arm only; Gröbner builder capped at 64 variables | no recorded Gröbner decomposition | no |
| m = 5, 6 | S₅, S₆ exist symbolically (`semaev_leading_form`, S₆ = 190,252 monomials) and are never Weil-descended | nothing recorded | no |
| GPU | `gpu/semaev`, `gpu/macaulay` | never run on a GPU; no GPU on the dev host | no |

The four blockers for m = 5 and 6, from the code survey:

1. **Monomials are `u64` masks** (`MAX_VARS = 64`) in every F₂ solver.
   Chained m = 4 already needs 66 variables at n = 21; m = 5, 6 cannot
   be expressed.
2. **Elimination** is M4RI with block width 4, scalar XOR loops, a
   serial pivot search, and no sparse–dense split in the solving path —
   although the diagnostic sparse path was already measured 9.6× faster
   on the m = 3 degree-6 matrix.
3. **Macaulay construction** (HashMap column index, full products
   `t·fᵢ` with no symbolic preprocessing) costs more than the
   reduction on every stage rung.
4. **No symmetrised binary S₅/S₆ system and no fast exhaustive or
   hybrid solver above degree 2**. FES/Monica is quadratic-only, and
   chaining pays `(m−2)·n` extra full-field unknowns to stay at degree 3.

## 2. The measurement suite (built first)

A change is kept only if it moves one of these, and it has to leave
correctness untouched.

| layer | harness | unit | gate |
|:--|:--|:--|:--|
| **L0 kernel** | `examples/gf2_elim_bench.rs` (new): reduces frozen Macaulay matrices dumped from real decomposition systems (m = 2, 3; degrees 3–6), plus random matrices of the same shape | ns per row-word; rank and a digest of the reduced basis must match | frozen JSON reference, compared by `scripts/pdp_bench.py` |
| **L1 oracle** | `examples/pdp_bench.rs` (new): a PDP ladder over m = 2…6 with **planted** targets (sum of m factor-base points, so a decomposition is known to exist) and random targets, per solver engine | seconds per decided target, success on planted targets, degree reached, largest matrix, word XORs | frozen reference `docs/ic/perf/pdp-reference-v1.json`; a cell that times out is recorded as *unreached*, never as a negative result |
| **L2 stage** | `groebner_stage_bench` (exists) | word XORs, build/reduce/read split | by hand against `research/groebner_stage_20260915` |
| **L3 end to end** | `ic workflow` + ρ, `ic-e2e-benchmark.yml` (exists) | pinned counters + same-host ρ/IC ratio | CI, reference v5 |

The PDP ladder has three tiers so the frontier stays visible:
**reach** (cells solved today, which pin regressions), **frontier**
(cells that are slow today: chained m = 3 at ℓ ≥ 5, m = 4 at small n)
and **aspiration** (m = 5, m = 6 at the smallest sizes that make sense).
A new reference is frozen whenever a cell moves tier.

## 3. Targets, in order

Each item says what it changes, which layer should move, and how the
change could turn out not to help.

**A. Elimination kernel (L0, then L1, L2).**
1. M4RI with block width 8 and multiple Gray-code tables; AVX-512 row
   XOR (512-bit lanes, `vpternlogq` for three-way XOR) with a portable
   fallback selected at runtime, as the scan kernel does.
2. A parallel pivot search: rows split across threads, and the table
   application parallelised from a lower threshold.
3. A Faugère–Lachartre sparse/dense split in the **solving** path:
   eliminate the sparse pivot block with sparse rows first, then run the
   dense kernel on the remaining Schur complement only. This is the
   measured 9.6× from the diagnostic path, moved into production.
   *Falsifier:* at small sizes the build dominates, so L1 may not move
   until B lands.

**B. Macaulay construction (L2, L1).**
1. Rank monomials with the combinatorial number system (graded
   reverse-lex rank is closed form) instead of hashing them.
2. Symbolic preprocessing: only the products `t·fᵢ` whose leading
   monomials are needed (true F4 selection; `pq_f4_f2` already has the
   skeleton), with the F5 criterion on by default where it proves
   useless rows.

**C. Wide monomials (unblocks m ≥ 4).** A width-generic monomial type
(`[u64; W]`, W = 1, 2, 4) for the F₂ solvers. W = 1 must stay exactly
as fast as today (checked at L0/L1), and W = 2 makes chained m = 4 at
n ≥ 21 and m = 5 representable.

**D. Algorithms for m = 5, 6 (L1: the aspiration tier).**
1. **Symmetrised binary S₅ and S₆.** Express them in e₁…e_m (FGHR
   symmetrisation) from the cached symbolic S₅/S₆ and Weil-descend them
   in the symmetric frame. This divides the solution count by m! and
   lowers the degree the solver has to reach.
2. **Hybrid guess-and-solve** (Bettale–Faugère–Perret): fix k
   variables, walking the 2^k guesses in Gray-code order so consecutive
   systems differ by one substitution (the `inherited_f4` idea, made
   systematic), and choose k by measured cost rather than by formula.
3. **Bitsliced exhaustive search for degree ≤ 4** (FES generalised
   beyond quadratic: Gray-code enumeration with k-th derivatives, 512
   candidates per AVX-512 register), as the leaf solver under the hybrid
   and as the baseline every Gröbner path must beat on the same cell.
4. Crossbred (exists, single-threaded) parallelised and put on the
   ladder as an engine.
   *Falsifier:* if the degree of regularity at m = 5 grows as the notes
   predict (Boolean degree m(m−1)), Gröbner cells may stay unreached,
   and the exhaustive and hybrid solvers set the frontier. That is a
   result, and it is recorded as one.

**E. End-to-end pipeline (L3).**
1. Descent is now 43 % of the k0n53 rung. Candidates: an AVX-512
   batched two-summand walk key, and a pair-table width priced for the
   descent as well as for collection.
2. Selection and table build at larger bases (`what_is_left` in
   `koblitz-collection-aim-20260922.json`: 23 % and 29 %).
3. When D reaches it, an **m = 4 rung** on the e2e gate, so the
   decomposition oracle's progress shows up end to end.

**F. GPU.** Port the L0 kernel and the D.3 exhaustive leaf to CUDA
(`gpu/macaulay` is the starting point). Everything is written to
compile in the existing `nvcc-compile` CI job. It **cannot be measured
here**, because the dev host has no GPU. It is benchmarked only once a
GPU host is available, and is never claimed from CPU numbers.

## 4. How each step is reported

Each step is a commit (or small PR) carrying a before/after table from
the layers it claims to move and a statement of the layers it did not
move. The step is classified by `AGENTS.md` §3: a faster kernel is
**engineering**; a lower degree of regularity or fewer unknowns for the
same decomposition question is an **algorithmic** change and says so. A
regression on any gated layer is reverted, not explained away.

## 5. Log

| date | step | layer moved | before → after | reference |
|:--|:--|:--|:--|:--|
| 2026-09-24 | #694 AVX-512 scan kernel | L3 | k0n53 collection 4.45 s → 3.55 s | v4 (counters identical) |
| 2026-09-24 | #694 windowed, aimed collection rungs | L3 | k0n53 IC 4.41 s → 1.65 s | v5 |
| 2026-09-24 | A.1 + A.2: `gf2_elim` Four Russians kernel (up to four adaptive-width Gray-code tables per pass, word-strip pivot search, BMI2 `pext` pattern gather, AVX-512 row update, rayon) replaces block-width-4 M4RI for the oracle's reduced row echelon form | L0; L1 dense solving | m = 3, degree 6 (20,240 × 20,686): elimination 4.12 s → 0.55 s (7.5×); dense `solving_profile` 3.84 s → 0.86 s, now ahead of the sparse path (1.98 s). Stage ladder unmoved: its matrices sit below the kernel's size gate, and the build dominates it (B) | `gf2-elim-reference-v1.json`; reduced form bit-identical on every cell |
| 2026-09-24 | B (part): decomposition systems instantiated from a per-thread `DecompositionTemplate` memo; Macaulay row cap read once per matrix | L2 | system build was 29 % of an m = 2 decomposition at n = 23 (callgrind); stage-ladder wall within its noise (tens of ms) | equations identical (new test) |
| 2026-09-24 | L1 frozen: `examples/pdp_bench.rs`, balanced ladder m = 2…6 | — | see §6 | `pdp-reference-v1.json` (a few frontier timings overlapped another job on the host; hits and statuses are unaffected) |
| 2026-09-24 | E.1: descent walk steps all 64 walks with `add_many_lazy(G, walks)` (the AVX-512 kernel) instead of `add_pairwise` | L3 | k0n53 descent 0.729 s → 0.622 s (−15 %, paired, 3 runs each); k0n41 unchanged within noise | v5, every counter identical |
| 2026-09-24 | E.1: the workflow's solve stage decides its targets in parallel (rayon, state written per target under a lock) | L3 wall only | solve-stage wall: k0n53 0.756 s → 0.183 s (4.1×), k0n41 0.212 s → 0.068 s (3.1×). The gated `descent_seconds_total` sums per-target walls, so the gate prices the same work as before — by design, since ρ runs on one core | v5, every counter identical |
| 2026-09-24 | D.2 probe: summand-first splitting (`SOLVER_SPLIT_RULE=lowest`) at n = 31, m = 3 | L1 | planted 0/2 → 1/2, at 63 s a target against meet in the middle's 0.1 ms | exploratory; default unchanged |
| 2026-09-24 | E.2: the windowed and aimed collection scan (`witnesses_fast_scan`) forms its rests with `add_many_lazy` — the AVX-512 kernel the full scan already used — completing ordinates only for keys the filter admits | L3 | k0n53 unit of 2048 probes on one thread 90 ms → 60 ms; precompute 0.95 s → 0.80 s, IC whole process ≈ 1.39 s | v5, every counter identical |
| 2026-09-24 | E.3: the folded table's orbit keys (`keys_of`, used by the full scan, the windowed/aimed scan and the descent) are computed in bulk by `FrobeniusCanon::canon_in_place`, a branch-free all-rotations minimum on AVX-512, sixteen keys per call | L3 | paired, 3 runs each: k0n53 IC whole process 1.43 s → 1.05 s (−26 %; descent 0.61 → 0.43 s, precompute 0.82 → 0.62 s); k0n41 0.30 s → 0.21 s (−29 %). In isolation the bulk key is slower than the scalar one (16.6 vs 13.4 ns); in the scan it is faster, for a reason not established | v5, every counter identical |
| 2026-09-24 | *Tried, dropped:* two-stage prefetch in the scans (filter word at 2·lookahead, the admitted key's table run at the lookahead) | L3 | no change within noise (k0n53 precompute 0.648 → 0.632 s, paired 3×3). The hypothesis that false positives' table-run misses dominate the lookup loop is falsified | reverted |
| 2026-09-24 | *Tried, dropped:* a larger pair-table filter (16 bits a key instead of 4–8) | L1 micro | scan 61.7 → 54.1 ns a summand, but +50 % table memory at the 4 GiB budget, and the filter layout is a persisted format (`examples/load_fold_table.rs`) | not landed |
| 2026-09-24 | *Measured, open:* where a windowed scan's time goes at n = 53 (window 1024, one thread): subtraction 10.9 ns, bulk key 9.5 ns, filter test 3.1 ns, and **resolving the 12.3 % of keys the filter admits 13–15 ns** — about 75–110 ns an admitted key, almost all in `compact_contains`. A prefetch of the run and a branch-free AVX-512 tag compare each left it unchanged, so it is neither the run's cache miss nor the run scan's branches; not yet explained | L1 micro | — | nothing landed |
| 2026-09-24 | C: `wide_groebner` — the chained system in `u128` monomials (≤ 128 unknowns), solved by branching on summand bits only with a linearisation step (`gf2_elim`) at every node and a group lift at the leaves | L1 | n = 31, m = 3: planted 0/2 → **2/2** (82 s a target); n = 31, m = 4 (86 vars): **1/1 planted, 241 s** — the first m = 4 Gröbner decomposition at this size; n = 39, m = 3 (78 vars) and n = 31, m = 5 (123 vars): no target decided in 400 s; n = 31, m = 6 (154 vars) exceeds 128. Meet in the middle on the same cells: 0.1–0.6 ms, 7 ms (m = 5), 0.21 s (m = 6) | engine agrees with enumerate on every reach cell |
| 2026-09-24 | D (symmetry): `wide_groebner` searches only summands in non-decreasing order, branching each summand from its highest coordinate down (`KIC_WIDE_ORDER=0` / `KIC_WIDE_BRANCH=low` are the controls) | L1 | s a target, unordered → ordered: n = 15, m = 3 0.090 → 0.067; n = 15, m = 4 0.88 → 0.38; **n = 15, m = 5 4.95 → 0.62 (8×)**; n = 31, m = 4 241 → 75 (the branch order; ordering itself flat there) | answers identical |
| 2026-09-24 | **Correction:** the wide engine's "n = 31, m = 3: 2/2 planted at 82 s a target" (row C) did not reproduce. Rerun with the same seeds, both the commit that reported it (d8c4df66) and the current one fail to decide the cell's first target within 600 s. Whatever produced the earlier figure, it is not a property of the engine; the cell is recorded as unreached | L1 | — | row C's n = 31, m = 3 figure withdrawn |
| 2026-09-25 | D (hybrid finish): once m − 1 summands are fixed the last is looked up in the base (≤ 2^(m−1) additions) instead of branched over (`KIC_WIDE_FINISH=0` control) | L1 | s a target: n = 15, m = 4 0.39 → 0.24; n = 15, m = 5 0.56 → 0.44; n = 31, m = 4 75 → 57, and all four targets decided within the budget | answers identical |
| 2026-09-25 | C (past 128 unknowns): when the whole chain does not fit, branch on the k trailing summands with the chain *suffix* that does (`WideSystem::build_suffix`, k·(ℓ + n) unknowns) and decompose the remainder recursively | L1 | makes n = 31, m = 6 (154 unknowns) runnable at all; recursion tested on small curves by lowering the cap | new test |
| 2026-09-25 | Engineering: linearisation columns laid out by a counting pass and indexed with `FxMap` (a comparator sort and SipHash were ~50 % of a search) | L1 | n = 31, m = 4, ℓ = 5: 0.97 → 0.76 s and 3.86 → 2.74 s a target, node counts identical | same search |
| 2026-09-25 | **Degree experiment** (`KIC_WIDE_PROLONG=D`, off by default): prolong every node's system to degree D (each equation of degree < D times every variable present) before splitting. n = 31, m = 4, ℓ = 5, two planted targets | L1 | nodes 1,639 / 4,505 → 993 / 3,745 (D = 3) → 931 / 3,443 (D = 4); leaves 191 / 1,308 → 1 / 1; time 0.67 / 2.77 s → 15.6 / 46 s (D = 3) → 56 / 255 s (D = 4) | see below |
| 2026-09-25 | Engineering: `wide_groebner` searches its tree's subtrees in parallel (breadth-first frontier, rayon, shared budget and stop flag); constant substitutions without a multiplication | L1 | 4 cores, s a target: n = 31, m = 4 57 → **21** (all 4 targets decided); n = 31, m = 5 planted 13.5 → **1.65**; **n = 31, m = 6 (154 unknowns, suffix recursion): 2/2 planted at 9.6 s** — the first m = 6 Gröbner decompositions at this size here. Random targets at m = 5, 6 (almost surely no decomposition, so a full refutation) are still undecided within 700 s; meet in the middle answers them in 7 ms and 0.21 s | answers verified in the group |
| 2026-09-25 | D (point branching): `wide_groebner` fixes a whole summand a node, over the coordinate vectors whose abscissa is a factor-base point's, in non-decreasing order (`KIC_WIDE_POINTS=0` restores bit-by-bit branching). A summand bit the linearisation already eliminated as `v = g` now keeps `g + value` as an equation when it is assigned, instead of dropping it | L1 | 4 cores, s a target, baseline → new: n = 15, m = 4 0.104 → 0.056; n = 15, m = 5 0.23 → 0.12; n = 15, m = 3 0.022 → 0.053 (slower: ℓ = 5, m = 3 has little to prune); **n = 31, m = 4 15.1 → 2.5**; **n = 31, m = 5 214 (3 of 4 targets in 300 s) → 34.9, all four decided — both random targets fully refuted**, the first complete m = 5 cell at n = 31 | verdict digests identical on every cell both decided |
| 2026-09-25 | D (suffix symmetry): the suffix recursion's k summands are the k largest, so the recursive head searches only abscissae ≤ the least of them | L1 | **n = 31, m = 6 (154 unknowns): complete — 2/2 planted (1.7, 2.8 s), both random targets refuted (≈ 231 s each)**; before, no random target was decided in 700 s. Meet in the middle on the same cell: 0.21 s. **Correction** to the parallel-search row: its m = 6 "2/2 planted at 9.6 s" was the luck of the parallel search order — a rerun of the same baseline decided no target in 200 s | suffix test covers it |
| 2026-09-25 | *Measured, dropped:* at n = 31, m = 6 the suffix recursion with k = 3 is pure enumeration — a random target visits all C(34, 3) = 5,984 sorted suffix triples (the free-`w_0` suffix system prunes none), then ≈ 46,000 inner m = 3 searches, 6.1 M linearisations in all. Peeling one summand instead (k = 1, the m = 5 remainder in one 118-unknown search) is worse: 742,048 finish-lookup leaves and ≈ 840 s for one random target against ≈ 220 s | L1 | — | not landed |
| 2026-09-25 | Engineering: `wide_groebner` polynomial bookkeeping. Callgrind (n = 15, m = 4, one thread) put sorting and substitution at ~70 % of a search and elimination under 2 %. A branch assigns a summand's ℓ constants in one masked pass (`assign_constants`), a linearisation substitutes its whole batch of linear consequences in one pass a polynomial (`substitute_all`, sound because reduced form clears every pivot column from every other row; the leading variable is now the row's pivot column), and the columns are deduplicated by hash instead of sorting every term | L1 | instructions 8.95 G → 4.60 G. 4 cores, s a target, main → new: n = 15, m = 3 0.052 → 0.024; n = 15, m = 4 0.053 → 0.042; **n = 31, m = 4 2.82 → 1.33; n = 31, m = 5 39.8 → 31.1; n = 31, m = 6 154 → 49** (random refutation ≈ 300 → ≈ 97 s) | verdict digests identical on every cell |
| 2026-09-25 | *Tried, dropped:* the admitted-key cost in the windowed scan (the open row above). Timed at n = 53, window 1024, one thread: skipping resolution entirely 33 → 24.5 ns a summand, and `compact_contains` alone accounts for all of it. Prefetching each admitted key's `bucket_start` entry and run, staged ahead of the probe (16 and 8 keys; with and without hashing each key once a block), left it unchanged or worse: 33–37 ns against 33–39 ns (±3 ns run-to-run), and the k0n53 gate's IC total 0.90 / 1.00 / 0.91 s against 0.87 / 0.99 / 0.86 s. The k0n53 table stores 1.1 M pairs, about 4.4 MB of runs, so it mostly fits in the last-level cache: the cost is not DRAM latency, and prefetching cannot hide it | L1 micro | — | not landed |
| 2026-09-25 | Engineering: `wide_groebner` reads each reduced row back without a sort — columns ascend within a degree, so a row is one ascending run a degree, merged pairwise (`merge_degree_runs`); row term lists and the column index are preallocated. A k-way merge picking the least head each step was tried first and cost as much as the sort (dropped) | L1 | instructions, one thread: n = 15, m = 5 3.00 → 2.44 G; n = 15, m = 4 4.60 → 3.76 G. 4 cores, s a target, main → new: n = 31, m = 4 1.40 → 1.30; **m = 5 34.1 → 27.4**; m = 6 57.2 → 53.8 (m = 4 and m = 6 within run-to-run spread: main's m = 6 measured 49 earlier the same day) | verdict digests identical |
| 2026-09-25 | **Measured:** where k0n53's whole method goes (ρ off; callgrind, one thread, scalar paths — valgrind has no AVX-512). The logs stage is relation collection, not linear algebra: its extension is 71,680 of 73,728 trials (147 relations for 144 columns), linear algebra 0.7 ms. Collection scan 68 % of instructions (`add_many_lazy` 48 % incl. `batch_inv` 28 %; Frobenius canonicalisation 24 %; the admitted-key lookup < 2 %), descent 19 %, pair table 4.6 %, setup ≈ 4 %, selection and linear algebra < 1 % each. Natively SIMD takes the method from ≈ 4.0 to 2.5 CPU-s | L3 | wall, 4 threads: k0n53 1.00–1.05 s (collect 0.13–0.17, logs 0.57, solve 0.17–0.20); k0n41 0.18–0.23 s | ranks the next E2E targets: relation yield a trial, then the batch inversion and the canonical key |

## 6. What the L1 ladder says (pdp-reference-v1)

Balanced cells (`m·ℓ ≈ n`), seconds per decided target, planted hits:

| cell | vars | Gröbner | SAT | meet in the middle | enumerate |
|:--|--:|:--|:--|:--|:--|
| n = 23, m = 2, ℓ = 11 | 22 | 10 ms, 8/8 | 1.5 s, 8/8 | 0.1 ms, 8/8 | 1.3 ms |
| n = 15, m = 3, ℓ = 5 | 30 | 35 ms, 8/8 | budget | < 0.1 ms | 0.9 ms |
| **n = 31, m = 3, ℓ = 10** | 61 | **3.7 s, 0/2 planted** (node budget) | budget | 0.1 ms, 2/2 | 0.9 s |
| n = 15, m = 4, ℓ = 4 | 46 | 69 ms, 4/4 | budget | < 0.1 ms | 2 ms |
| n = 15, m = 5, ℓ = 3 | 60 | 1.8 s, 1/1 | budget | 0.3 ms | 1.6 ms |
| n = 7, m = 6, ℓ = 1 | 34 | 14 ms, 4/4 | 2.3 ms | < 0.1 ms | < 0.1 ms |
| n = 31, m = 4 / 5 / 6 | 86 / 123 / 154 | not buildable (64-bit monomials) | — | 0.2 ms / 7 ms / 0.21 s | 55 ms / 0.75 s / — |
| n = 39, m = 3, ℓ = 13 | 78 | not buildable | — | 0.6 ms | — |

Reading it honestly:

1. On every cell the summation-polynomial + Gröbner oracle is **two to four
   orders of magnitude slower** than the exact meet-in-the-middle oracle
   the end-to-end pipeline already uses. The elimination kernel (A) moved
   a constant; it did not touch that gap.
2. At n = 31, m = 3 it is also **incomplete**: its splitting search
   exhausts 20,000 nodes (and 200,000, at 38 s a target) without finding
   decompositions that exist. The default split rule branches on the
   31-bit intermediate abscissa first. Guessing a summand instead and
   solving the m = 2 remainder is the obvious fix, and it would still cost
   about |F| × 5 ms ≈ 7 s a target, against 0.1 ms.
3. m ≥ 4 at n ≥ 31 could not even be written down until the monomials
   were widened (C). With `wide_groebner` it can: m = 4 at n = 31 decides
   a planted target in 241 s (75 s after the D row's branch order), m = 5 decides none in 400 s, and m = 6
   needs more than 128 unknowns. Meet in the middle answers the same
   cells in 0.2 ms, 7 ms and 0.21 s. Summand-first branching fixed the
   completeness failure; it did not change the verdict.

So the plan's order stands for the Gröbner track (C, then D.2 hybrid
guessing with summand-first splitting), with its success criterion stated
in advance: **a Gröbner cell counts as progress when it decides planted
targets that it previously missed, or when its seconds per target fall on
an unchanged cell; it counts as a crossover only when it beats the
meet-in-the-middle column on the same cell.** End-to-end work (E) proceeds
alongside it.

## 7. What raising the degree does (and does not do)

The degree experiment is the question behind "high degree of regularity"
asked directly, on a cell where the answer can be measured (n = 31,
m = 4, ℓ = 5, chained system of 80 unknowns). Prolonging each node's
system from its own degree (3) to degree 3 and 4 behaves the same way
at both degrees:

- **Near the leaves it is decisive.** Leaves fall from hundreds to one:
  once enough summands are fixed, the degree-3 matrix pins the rest down
  algebraically.
- **Above that it barely prunes.** Nodes fall only 1.2–1.7×, while each
  node's matrix grows from 93 × 7,378 to 4,728 × 24,527 (D = 3) and
  7,084 × 251,572 (D = 4). Net: 20× (D = 3) to 100× (D = 4) slower.

The search tree is the number of partial summand assignments that are
still consistent. For a first summand fixed, the chain's first link has
about 2|F| solutions (x₂, u₁), and no Macaulay degree below the system's
regularity can refute those, because they are real. So an algebraic
search like this one enumerates about |F|^(m−2) partial decompositions
before algebra finishes them. Exact meet in the middle does the same
enumeration with a table lookup in place of each finish. That is why the
Gröbner route trails it by orders of magnitude, and why neither faster
elimination nor higher degree has closed the gap.

Nor does a change of formulation escape it. With the summands as the
only unknowns (the symmetrised S_{m+1}), a first summand P₁ is
consistent exactly when R − P₁ decomposes into m − 1 base points; in a
balanced cell that holds for about m/|F| of the choices, so refuting the
rest early *is* solving an (m − 1)-point decomposition problem. Any
algebraic formulation enumerates about |F|^(m−2) partial decompositions
unless that smaller problem is cheap at low degree, which is what a
small degree of regularity would mean, and what the measurements here
(and the repository's FFD and solving-degree ladders) do not show. What
remains for the Gröbner route at m = 5, 6 is engineering: the constant
per node and the use of every core.
