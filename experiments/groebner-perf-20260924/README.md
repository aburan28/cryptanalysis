# F4/F5 performance campaign, 2026-09-24

The verifier and larger-matrix GPU follow-up is documented in [round3/README.md](round3/README.md), with frozen paired certificate timings, independent validation, and tiled Metal measurements.

The next iteration is documented in [round2/README.md](round2/README.md), with a complete batched GPU RREF prototype, an exact evaluation/interpolation solver, stronger basis certificates, and further measurements.

This first iteration contains a source review, frozen controls, correctness
repairs, CPU optimizations, paired measurements, and an executable Metal GF(2)
panel prototype. It establishes local progress, not a global speed record.
The high-regularity and new-algorithm work is specified in `RESEARCH.md`.

## Results retained

| Component and workload | Corrected control | Optimized | Evidence |
|---|---:|---:|---|
| Prime-field F4 symbolic preprocessing, Semaev fb=3 | 0.988 ms; 1,212 rows | 0.423 ms; 608 rows | 2.34x, 21 alternating samples |
| Prime-field F4 symbolic preprocessing, Semaev fb=4 | 0.967 ms; 980 rows | 0.485 ms; 572 rows | 1.99x, 21 alternating samples |
| Native Boolean F5B-family basis, 6 variables | 0.288 ms CPU | 0.190 ms CPU | 1.49x geometric mean of five paired seed ratios |
| Native Boolean F5B-family basis, 9 variables | 3.778 ms CPU | 2.730 ms CPU | 1.36x geometric mean of five paired seed ratios |
| F5/M4RI hybrid basis, 12 variables | 40.600 ms CPU | 28.021 ms CPU | 1.42x geometric mean of five paired seed ratios |
| Complete verified hybrid query, 12 variables | 145.183 ms elapsed | 110.680 ms elapsed | 1.45x geometric mean of five paired seed ratios |

CPU times in the native and hybrid basis rows are medians across the five per-seed medians;
the geometric mean is computed from individual seed ratios, not the ratio of
the displayed aggregates. The native confirmation used 31 inner computations
per process, the hybrid 15, with seven recorded alternating process pairs per
fixture and warmups. Constructors are outside the inner basis timer; build,
input generation, extraction of curve points, and independent verification are
excluded. Process wall/CPU and individual samples are also retained.

For the 12-variable hybrid, per-seed CPU speedups were 1.38–1.49x; per-seed
elapsed basis speedups were 1.34–1.57x. Median elapsed basis time across seeds
fell from 49.336 to 36.539 ms. The smaller hybrid fixtures were noisy, including
some regressions; no uniform small-matrix hybrid improvement is claimed.

This is a shared Apple M4 Pro host with substantial concurrent work (observed
load average above 40). CPU time helps with preemption but does not remove
core migration, thermal, cache, or memory contention. Repeat on an otherwise
idle host before using these numbers as publication results. Initial screens
are retained separately from confirmation; the Rust kernel baseline and the
first hybrid baseline overlapped and are diagnostic only.

Raw evidence: `results/native-confirmation.json`,
`results/hybrid-confirmation.json`, `results/gbrl-preprocess.json`,
`results/query-confirmation.json`.

The query benchmark uses nine recorded alternating repetitions per seed. It
includes serialization, process launch, basis computation, Python verification,
root extraction, original-equation checks and curve replay; instance generation
and compilation are excluded. Per-seed speedups are 1.21–2.17x, with identical
bases and identical first accepted assignments. `query-before-filter.json` and
`query-filter-screen.json` retain the intermediate experiments.

## Changes

In `../pdp-scaling/boolean_f5b_native.cpp`:

- Complete pairs against implicit Boolean field equations as well as pairs
  between basis polynomials.
- Reduce using a descending leading-word cursor and XOR only the active
  polynomial prefix. Reduction-table entries have their prescribed leading
  monomial, so its bit also tests whether a reducer exists.
- Obtain polynomial degree from the leading term under degree-compatible
  grevlex. Avoid allocating and scanning term vectors in interreduction sorting.

In `../pdp-scaling/boolean_f5b_m4ri.cpp`:

- Materialize each generator's term masks once, screen multiplier degree
  bounds from high-degree terms first, and initialize a packed row only after
  it is admissible. The admission condition remains exactly the old condition,
  including checking terms that might subsequently cancel.
- Populate M4RI using reversed packed words instead of one bit write per term.
  Retain the bit path for universes smaller than 64 columns.
- Use the repaired scalar completion through the included native engine.

In the Python native/matrix runners:

- Reuse the verifier's reduction table for both Gröbner checks and reduction
  of original generators. Profiling identified repeated generic normal forms
  as a significant cost after the native computation.
- Evaluate the computed basis before testing each assignment against the
  original large ANF system. Surviving candidates still undergo the original
  equations and curve replay. Enumeration order and the accepted assignment
  remain unchanged. In the fifth 12-variable fixture this reduces original
  system evaluations from 2,477 assignments to one candidate.

In `/Volumes/SSD990/crypto/research/gbrl/src/f4.rs`:

- Process each symbolic monomial once. The old `(reducer, multiplier)` visited
  set allowed a repeated monomial to fall through to additional basis
  reducers. The replacement reduces work and matrix rows while keeping
  symbolic closure.
- Restore the selected pair bucket when a matrix cap is exceeded, allowing a
  correct retry. Previously the cap discarded unfinished work.
- Correct stale comments that described implemented code as unimplemented and
  asserted an unsupported generic speedup.

The existing dirty work in both repositories was preserved. The production
Boolean Koblitz F4 reducer was reviewed and measured but not changed here;
its existing block-6 optimization belongs to the earlier campaign.

## Correctness

The old Python `is_groebner` accepted `[xy+1]` as a Boolean Gröbner basis. It
checked only basis/basis S-pairs, missing pairs against `x_i^2+x_i`. The native
completion had the same omission. Consequently, matrix-degree 0 and 1 could
return `[xy+1]` as verified, whereas degree 2 returned `[x+1,y+1]`.

For every basis polynomial `g` and variable dividing `LM(g)`, completion now
processes the Boolean reduction of `x_i*g`. The Python checker verifies the
same condition. This is necessary even for singleton bases. The fixes apply
to the Python engine, native engine, and hybrid fallback.

`validate.py` checks 126 fixed and randomized ideals using five paths per
ideal (630 runs): Python, native, and the matrix hybrid at degrees 0, min(2,n),
and n. Canonical bases match Sage/Singular over GF(2), with explicit field
equations and grevlex. A separate set-arithmetic checker verifies S-pairs,
field pairs, reducedness and source-generator reductions. Exhaustive Boolean
truth tables prove equality of the two ideals' full root sets. The 15 PDP
fixtures also pass these checks, including 12-variable cases, and all timed
variants return identical canonical bases.

The ordinary-ring oracle avoids depending on the packed implementation's own
verifier. Root equality alone would not establish that a basis is Gröbner;
S-pairs and field pairs alone would not establish equality with the input
ideal. Both are checked.

The focused repository suite passes 11 tests, including complete point
decomposition and curve replay. The prime-field F4 suite passes seven tests,
including nonlinear completion checked against Buchberger and every S-pair,
symbolic deduplication, and retry after a matrix cap. See validation JSON and
test logs in `results/` for the exact runs.

UndefinedBehaviorSanitizer builds also pass the 630-run differential suite
with recovery disabled. The external M4RI library itself was not instrumented.
AddressSanitizer-instrumented executables timed out without output even on the
two-variable singleton probe after 45 seconds; no ASan pass is claimed. The
earlier attempted combined ASan/UBSan run's timeout is retained in
`results/sanitizer.log`.

## GPU experiment

`panel.metal` and `metal_panel.mm` implement an exact Four Russians trailing
panel update over GF(2). Both scalar and uint4 vector versions have executed
on the Apple M4 Pro GPU. Every output word and every cleared pivot pattern is
checked against the CPU result on every repetition.

The vector version uses a two-dimensional grid to remove per-word division
and handles 128 coefficient bits per thread. In the retained vector run:

| Panel | CPU ms | GPU execution ms | GPU including dispatch/wait ms | CPU / GPU including dispatch |
|---|---:|---:|---:|---:|
| 1,024 × 4,480 bits | 0.0128 | 0.0165 | 0.4216 | 0.03x |
| 8,192 × 16,384 bits | 1.2954 | 0.2044 | 1.7707 | 0.73x |
| 32,768 × 32,768 bits | 9.2910 | 1.4587 | 3.7683 | 2.47x |
| 65,536 × 32,768 bits | 8.2448 | 2.8496 | 4.1948 | 1.97x |

The nonmonotonic CPU times show host contention. These are panel measurements
against a single-threaded, optimized CPU control. Buffers are preallocated in
shared memory; shader compilation, table construction, matrix construction,
allocation and pivot selection are excluded. This is **not a complete GPU
F4/F5 solver**, a CUDA result, or an end-to-end solver speedup. Small matrices
should stay on CPU. Device-resident batches and multiple panel updates per
submission are the next GPU experiments. The input/output buffers are distinct
to prevent a race between reading pivot patterns and clearing pivot columns.

## Remaining bottlenecks and constraints

1. The native Boolean engine allocates a full `2^n` monomial universe and
   fixed 64-word polynomials, imposing a 12-variable ceiling. Divisor tables,
   rewrite tables and eager reducer multiples are also exponential. Removing
   that representation limit matters more than further tiny-loop tuning.
2. Its signature pass is a bounded F5-family prepass followed by ordinary
   reductions/completion. The unrestricted ordinary reduction after signature
   reduction does not maintain a classical F5 signature invariant. Treat it
   as a verified hybrid, not a benchmark of a complete pure F5 implementation.
3. The native 12-variable default (`signature_limit=128`, seed limit -1)
   exceeded the first 60-second control budget. A structured three-second
   probe censored all five seeds for both old and optimized versions. The
   matrix backend finishes these inputs; no finite speedup is assigned to
   native timeouts. Historical shorter native results were not reproduced by
   this configuration; audit exact flags and input ordering before comparison.
4. The Koblitz Rust path rebuilds polynomial multiples, row term vectors,
   column dictionaries and packed rows at each uncached degree/branch. Its
   dense reducer allocates pivot clones and a new combination table per
   block. Measure symbolic construction separately before optimizing more XORs.
5. The separate generic `crypto/src/cryptanalysis/groebner_f4.rs` is
   Buchberger, despite its filename. It scans leading terms, clones polynomial
   maps and does arbitrary-precision field operations. Its 5,000-step cap
   returns a plain vector without a completion status. That API remains a
   correctness/reporting follow-up; this campaign did not change it.
6. The prime-field research F4 backend still uses dense, scalar modular
   Gauss–Jordan elimination and incomplete pair-pruning heuristics. It needs a
   sparse-to-dense block strategy and same-machine external comparisons.

## Reproduction

Use Python >= 3.10. Sage is needed only for the differential oracle and the
existing tests that import SymPy. `M4RI_PREFIX` may be set explicitly; the
current runner also knows the local Sage installation.

```sh
cd /Volumes/SSD990/cryptanalysis
sage -python experiments/groebner-perf-20260924/build.py
GB_BENCH_INNER=31 sage -python experiments/groebner-perf-20260924/benchmark.py \
  --variant corrected:native:experiments/groebner-perf-20260924/build/batch-corrected-native \
  --variant optimized:native:experiments/groebner-perf-20260924/build/batch-optimized-native \
  --nvars 6 9 --repeats 7 --output /tmp/native-confirmation.json
GB_BENCH_INNER=15 sage -python experiments/groebner-perf-20260924/benchmark.py \
  --variant corrected:m4ri:experiments/groebner-perf-20260924/build/batch-corrected-m4ri \
  --variant optimized:m4ri:experiments/groebner-perf-20260924/build/batch-optimized-m4ri \
  --repeats 7 --output /tmp/hybrid-confirmation.json
sage -python experiments/groebner-perf-20260924/validate.py \
  --native experiments/groebner-perf-20260924/build/cursor-native \
  --m4ri experiments/groebner-perf-20260924/build/screened-m4ri \
  --output /tmp/validation.json
sage -python experiments/groebner-perf-20260924/query_benchmark.py
experiments/groebner-perf-20260924/build/metal-panel-vector \
  experiments/groebner-perf-20260924/panel.metal vector > /tmp/metal-panel.json
cd /Volumes/SSD990/crypto/research/gbrl
cargo test --release --lib f4::tests
cargo run --release --example f4_preprocess_bench
```

`baseline/` preserves the original source; `corrected/` preserves the Boolean
correctness repair before performance changes. `results/build-manifest.json`
records source, corpus, library and binary hashes plus reconstruction commands.
Compiled executables are ignored. Rebuilding on another compiler or machine
may change binary hashes; compare identical inputs and validated outputs.
