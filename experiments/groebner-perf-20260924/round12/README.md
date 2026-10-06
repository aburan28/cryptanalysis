# Sparse reduction order and pivot-key ablations

This opt-in experiment removes two costs identified by sampling the sparse
Boolean F4 proof producer. It does not change production dispatch, the
independent checker, pair selection, reducer priorities, monomial order,
or the mathematical algorithm. It is not an F5 signature change or a new F6
method. The baseline remains available and all measured failures are retained.

## Changes and invariants

`native_engine.cpp` is derived from the unchanged round-five Engine. Two
compile-time switches enable independent ablations:

- `PERSISTENT_ORDER`: normal-form reduction sorts its working polynomial once
  into descending grevlex order, then preserves that order by merging XOR
  operands. Shifted reducers are canonicalized in the same order; repeated
  Boolean monomials cancel modulo two. The result is converted back to numeric
  mask order before returning. Basis rows and the public ABI keep their previous
  representation. This replaces repeated whole-polynomial sorting with ordered
  linear merges; constructing a shifted reducer still needs sorting.
- `PIVOT_KEYS`: matrix output sorting uses each pivot map's existing leading
  monomial key. It sorts iterators and moves rows once, eliminating repeated
  leading-term scans from the comparator. Keys are unique and immutable during
  this step, so the emitted row order is the same.

Both retain the original logical work charges, reduction choices, and DAG
operations. Those charges are a reproducibility limit, not machine instruction
counts. Representation-dependent allocation/sorting overhead can change and is
included in timings. Exact proof and counter equality are checked against a
separately compiled, hash-pinned original Engine. The baseline does not rely on
switching the new implementation's optimizations off.

`build.py` builds four producers (`baseline`, `pivots`, `ordered`, `combined`)
and optimized/UBSan trap versions. It reuses the unchanged round-eleven packed
ABI adapter and independent native checker. `query.py` loads a private copy of
the unchanged Python wrapper for each producer; library selection does not
modify another caller's module globals. Every computation allocates fresh
numeric state. The only shared library is the independent checker, whose
arithmetic is call-local. No target results or numeric matrix state are cached.

## Qualification

The four test groups cover all eight producer builds. All 96 randomized
controls verify against both the independent algebraic checker and the Python
truth/staircase oracle, with exact basis, derivation DAG, and logical counter
parity. Explicit cases include Boolean multiplication cancellation, repeated
input terms, zero/unit ideals, field pairs, and masks up to 64 variables.
Work/node/row budgets, alternative batch sizes, recovery after exhaustion, and
32 concurrent tasks exercise reuse and failure boundaries. The local suite
passed in 8.650 seconds; `results/validation.log` retains the output. CI repeats
these tests with GCC on Linux and Clang on macOS.

The unchanged checker retains both ideal inclusions, reducedness, all required
basis critical pairs and Boolean field pairs. Its prior adversarial qualification
is recorded in round eleven. There is no enumeration limit in this algebraic
checker; the producer still has a 64-variable mask representation.

## Measurement boundary

`benchmark.py` repeats the same 23 frozen inputs used by round eleven with four
packed producer arms and the evaluation/interpolation reference on PDP inputs.
Algebra runs start with the same ANF coefficients and end with a materialized,
independently certified basis. PDP runs start at a frozen target coordinate,
regenerate target coefficients, solve, certify, extract a solution, evaluate
the original equations, replay the curve relation, and check the untouched
reference ANF. The proof arms use identical bounded extraction over at most
4096 assignments; this extraction is separate from non-enumerative certification.

Fixture generation, shared libraries, and ring-only descent-plan setup are
outside query time and reported separately. There is one target per timed query.
Repeated measurements are repetitions of that query, not batch amortization.
All arms run in-process with the same work/node/row/retention limits and no hard
wall timeout. Both wall time and process CPU time are retained. Wall time is the
primary metric; CPU time is diagnostic and does not replace it.

Each screen or confirmation contains 200 paired groups and 920 attempts,
including one warmup per arm and input. The predeclared policy is 15 measured
repetitions for structured algebra and six-variable PDP controls, and three
for difficult algebra and nine-/twelve-variable PDP controls. Each run retains
696 verified outcomes and 224 inconclusive budget exhaustions. A faster budget
exhaustion is not a solved-query speedup. No ratio is published for a case unless
both paired arms verify on every measured repetition.

The machine is an Apple M4 Pro with 14 logical CPUs and 48 GiB RAM. It is under
substantial unrelated load. The frozen runs retain load averages, exact sources,
binaries, compiler flags, inputs, setup costs, exclusive phase diagnostics,
all failures, and paired uncertainty. The screen and confirmation both remain
in `results/`; no run is discarded because its result is inconvenient.

These are planted correctness controls and algebra-stage diagnostics, not
natural relation-yield estimates or full index calculus. `candidate_id`,
`IC_online_ms`, and `rho_online_ms` remain null. A full IC claim requires a
previously unseen public target, verified logarithm recovery with every
failed target-dependent attempt charged, and a paired rho reference.

## Results

The confirmation does **not** establish a complete-query improvement. All five
six-variable PDP wall-time intervals include one; the 21-variable structured
algebra control regresses in the confirmation. CPU diagnostics on the five
PDP controls are roughly 1.06–1.14 times faster for the combined variant, but
that does not meet the wall-time promotion gate. Evaluation/interpolation still
solves the small PDP controls faster. Keep existing dispatch.

The table reports confirmation medians and paired geometric ratios of original
to combined wall time. A ratio above one favors the combined variant. Ratios
are computed from paired repetitions, not by dividing the marginal medians.
All these cells have 15 measured repetitions; warmups are excluded.

| Frozen control | Original median ms | Combined median ms | Paired ratio [95% bootstrap] |
|---|---:|---:|---:|
| pair-products-21 | 0.157 | 0.165 | 0.744 [0.526, 0.959] |
| pair-products-32 | 0.348 | 0.317 | 0.860 [0.553, 1.361] |
| pair-products-64 | 1.539 | 0.762 | 0.949 [0.601, 1.413] |
| free-variables-64 | 0.086 | 0.066 | 0.715 [0.377, 1.229] |
| pdp-6-seed-1 | 15.824 | 14.438 | 1.238 [0.854, 1.772] |
| pdp-6-seed-2 | 12.737 | 12.880 | 1.042 [0.737, 1.509] |
| pdp-6-seed-3 | 8.824 | 7.065 | 1.063 [0.685, 1.616] |
| pdp-6-seed-4 | 22.855 | 18.572 | 1.164 [0.667, 2.031] |
| pdp-6-seed-5 | 13.373 | 7.368 | 1.160 [0.697, 1.781] |

The dense-MQ controls below all exhaust the same logical work budget in both
arms. These are median process-CPU costs to **inconclusive termination**, not
solve times or speedups. Three measured repetitions are retained per cell.

| Inconclusive control | Original CPU ms | Combined CPU ms |
|---|---:|---:|
| planted-dense-mq-12 | 214.815 | 134.244 |
| planted-dense-mq-16 | 119.288 | 68.702 |
| planted-dense-mq-21 | 86.630 | 42.421 |

The screen and confirmation each retain all 224 inconclusive attempts.
The all-source audit checks exact logical counter and outcome parity in both
runs; it refuses survivor-only speedup ratios.

The final cleanup removes one trailing blank line from the Engine source.
The exact measurement-time Engine and audit are retained as compressed sources
in `measured/`. Rebuilding the cleaned source produces byte-identical optimized
libraries, recorded in `results/formatting-build-receipt.json`. The original
profiler sample is also stored compressed without changing its bytes.

## Profile provenance

`profile/` retains the original sampling command, logs and receipts for a
frozen planted 16-variable dense MQ input. The first attempt ended before
sampling captured a useful stack; it is preserved in `profile/first/` and is
not used as evidence. The second attempt has 2,376 samples: 1,335 under normal
reduction and 1,025 under matrix processing. Repeated normal-form sorting and
matrix output comparators occur in those stacks. Inclusive stack counts must
not be added across nested frames.

The sampled process ultimately exhausted its one-billion logical-work budget.
Its wall time includes profiler overhead and is not a benchmark result. The
archived profiling scripts retain their original local paths to preserve their
recorded hashes; normal reproduction uses the portable commands below.

## Reproduction

```sh
python3 experiments/groebner-perf-20260924/round12/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round12 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round12/verify_evidence.py
```

For a new benchmark, build the evaluation reference with
`python3 experiments/groebner-perf-20260924/round4/build.py`, then invoke
`round12/benchmark.py --output /tmp/new-reduction-comparison.json.gz`.
Use a new output path to preserve historical evidence. `CXX=g++` selects GCC.

## Next experiment

The largest remaining normal-form cost is repeated divisor testing and scanning
of terms already found irreducible against the same reducer set. A bounded
follow-up can test a per-reduction divisor cache or a descending reduction
frontier, retaining independent certification and explicitly validating the
term-order invariant. Do not infer a full-query improvement from lower kernel
CPU time. GPU promotion still requires one complete verified query to beat the
best CPU method; evaluation remains an essential comparison on small rings.
