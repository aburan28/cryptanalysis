# Independent Boolean verification and larger GPU matrices

This iteration targets the 18-variable query whose earlier diagnostic spent
4.700 seconds in independent Python certification and 0.913 milliseconds in
basis computation. The retained implementation adds a native independent
certificate, removes redundant Python canonicalization and copies, and adds
batched Metal reduction for matrices larger than threadgroup memory.

These are **algebra component and PDP phase diagnostics**, not complete IC
candidate comparisons. There is no fully specified relation-collection,
final relation-LA, descent, or DLP-recovery pipeline in this experiment.
Complete DLP cost and natural relation yield are unknown. Planted inputs are
correctness controls. No IC1 identity, usable factor-base count, or natural
relation yield is inferred from them. The matrix kernel is internal PDP work,
not the final relation-LA stage. There is no global speed-record or new F6
asymptotic claim.

## Verifier implementation

The native implementation is in
[`boolean_certificate.cpp`](../../pdp-scaling/boolean_certificate.cpp), with
[`boolean_certificate_native.py`](../../pdp-scaling/boolean_certificate_native.py)
as its transport. It accepts raw input equations and the proposed basis.
It never reads solver-provided roots, ranks, or completion flags, and includes
no solver source. The solver uses a subset transform across packed equations;
the verifier uses direct ANF evaluation across packed assignments.

1. Split an assignment into six low bits and the remaining high bits. Each
   low-variable monomial has a fixed 64-bit truth word.
2. XOR these words for terms with the same high-variable mask. Scatter each
   resulting word to all high assignments containing that mask. This directly
   evaluates the ANF on every assignment in 64-assignment blocks.
3. Intersect surviving roots after each equation. Process shorter equations
   first and switch to direct scalar evaluation on survivors when the exact
   operation-count estimate favors it. Every eliminated point has already
   violated an input equation; no unexamined point is discarded.
4. Check every proposed basis row on the independently established roots.
   Count squarefree monomials outside the proposed leading-monomial ideal.
   Require equal root/staircase counts, minimal leading monomials, and standard
   tails. All arithmetic is exact over GF(2).

In the Boolean quotient every ideal is radical and determined by its points.
If G vanishes on all input roots Z, then `<G> ⊆ I(Z)` and
`|Z| ≤ dim(R/<G>) ≤ |S|`, where S is the proposed staircase. Equality of the
outer counts proves both ideal equality and the Gröbner property. Minimal
leading terms and standard tails certify the reduced basis. The proof is the
same as the Python oracle; the evaluation implementation is different.

The bound remains **1–20 Boolean variables**. Certification supports any
root count inside that universe; the returned `solutions` list is omitted
(`null`) above 256 roots. The dual solver separately has a 256-root capacity
and returns inconclusive beyond it. The verifier does not inherit that solver
capacity. Enumeration remains exponential in the number of variables.

The evaluator's three truth-word arrays use `3 * ceil(2^n/64) * 8` bytes, plus
input/basis storage and a 64-word low-variable table. This is a working-array
bound, not a measured process-RSS claim. `scatter_words` and `scalar_terms`
are implementation counters, not calibrated complete operation totals.

## Frozen paired measurements

`inputs.json` freezes ten exact equation/basis workloads and their full
SHA-256 identifiers. Five 18-variable seeds (201–205) were added after writing
the implementation. The original seed 101 and earlier 12/16/20-variable MQ
and 15-variable PDP controls are also retained.

`results/certificate-benchmark.json` records one warmup pair and five measured
pairs per input. Arms alternate. Both take resident Python lists and produce a
complete certificate. Native timings include packing, fresh native allocations,
evaluation, checking and result unpacking. No numerical result cache is used.
Library initialization was 4.72 ms and is recorded separately; compilation
and input file loading are excluded. Every warmup is retained and charged in
per-case totals. All 120 measured/warmup certificate calls verified.

| Frozen algebra input | Python median | Native median | Paired geometric mean speedup | 95% paired bootstrap interval |
|---|---:|---:|---:|---:|
| 18 variables, original seed 101 | 2,712.30 ms | 4.18 ms | 656.8x | 612.7–699.3x |
| 18 variables, seed 201 | 2,908.77 ms | 4.33 ms | 671.4x | 608.2–741.2x |
| 18 variables, seed 202 | 2,796.31 ms | 4.00 ms | 701.4x | 660.9–732.4x |
| 18 variables, seed 203 | 2,622.29 ms | 4.34 ms | 634.3x | 590.6–681.2x |
| 18 variables, seed 204 | 3,499.28 ms | 3.81 ms | 902.6x | 796.4–1,039.9x |
| 18 variables, seed 205 | 3,937.23 ms | 5.20 ms | 725.5x | 643.0–830.8x |
| 15 variables, seed 101 | 186.65 ms | 2.02 ms | 89.8x | 46.0–169.5x |
| Dense MQ, 20 variables | 73.05 ms | 2.25 ms | 32.2x | 29.5–35.1x |

Ratios are geometric means of paired sample ratios, not ratios of the displayed
medians. Intervals describe repeated runs on this shared host; they are not
population estimates. The old 4.700-second observation is historical context,
not the denominator of these speedups. Host load, versions and source/binary
hashes are in the raw receipt. No other benchmark from this task ran concurrently.

The initial native transport copied through Python lists. The final transport
uses contiguous `array('I')` buffers and ctypes views. `baseline/native-list-packing.py`
and `results/packing-benchmark.json` retain that experiment. `canonical_terms`
also recognizes sets/frozensets as already unique, preserving XOR cancellation
for input sequences. The dual solver's input transfer uses contiguous buffers.
In a separate 11-pair comparison, array transport made the complete native
certificate another **4.08–4.38x** faster than its first list-based version on
the six 18-variable inputs (ratio of per-arm medians). This improvement is
already included in the Python-versus-native table, not multiplied into it.

`round2/solve_dual.py` now selects the native certificate when its library is
built. `--verifier python` forces the independent Python oracle;
`--verifier native` requires the library; `--verifier auto` falls back to Python
only when the library is absent. Native failures are not silently replaced by
Python results. Other F4/F5 solver dispatch defaults are unchanged.

`results/query-check.json` records four freshly computed queries for each of
six 18-variable planted inputs, including original equations and curve replay.
Instance construction is timed separately. The first query retains library
loading; subsequent queries reuse code only. `results/query-profile.txt`
identifies the remaining input preparation cost. Profiled timings are not
used as performance measurements. Earlier query diagnostics are preserved in
`query-check-before-packing.json` and `query-profile-before-packing.txt`.
For seed 101 the final resident-code query median was **47.29 ms**. The first
process query took **425.37 ms**, and instance construction separately took
118.49 ms. Subsequent-query medians across all six seeds were 44.82–51.81 ms.
Those are query diagnostics, not a paired complete-pipeline speedup against
the earlier 4.810-second observation. Input equation construction is now the
largest component in the diagnostic profile.

## GPU experiment

`tiled_rref.metal` adapts the existing `sage-gf2-metal-reuse` eight-pivot panel
method to independent matrix batches. Each matrix has its own pivot state and
Four-Russians table. Elimination streams through global matrix storage in
row/word tiles; the whole matrix no longer has to fit on chip. Pivot selection
uses SIMD minima before atomic updates. For at most 4,096 rows, a coherent
32-column slice is cached in threadgroup memory. Larger row counts use the
uncached path. The host bounds inputs to 8,192 rows/columns and 256 matrices;
these are allocation bounds, not a claim that every shape was benchmarked.

`matrices.json` contains two exact 2,915 x 4,096 matrices captured from the
existing Boolean hybrid on frozen seed-1/seed-2 inputs. Synthetic batches use
independent matrices. Captured-matrix batches cycle through the two inputs;
they are throughput controls, not new target queries or natural relation
samples. Both seed-labelled large-batch cells therefore have the same input
pool. No F5 signature semantics are implied by unrestricted GF(2) RREF.

`results/gpu-tiled.json` contains the final measurements, including every warmup,
while `results/gpu-run.json` binds the sources, shader, input, binary, M4RI and
host loads. Each of six shapes has batches of 1, 8 and 32, with one retained
warmup and five timed pairs. CPU and GPU order alternates. CPU M4RI is one
thread. Both timings include allocation, input/output copying and full rank/
RREF extraction; GPU also includes dispatch, synchronization and buffer
destruction. Shader compilation and pipeline initialization are separate.

The final run checked **2,264 matrices** exactly. Representative captured
matrix measurements are below; batches in the two rows labelled A/B cycle
through the same two captured matrices and are not independent workload
families. Initialization was 61.20 ms, excluded from per-call GPU timings.

| Capture-pool run | Batch | CPU median | GPU median | Ratio of medians | Paired geometric mean (95% interval) |
|---|---:|---:|---:|---:|---:|
| A | 1 | 22.02 ms | 34.23 ms | 0.64x | 0.64x (0.56–0.72x) |
| A | 8 | 216.20 ms | 52.03 ms | 4.16x | 3.91x (3.62–4.23x) |
| B | 8 | 180.13 ms | 51.62 ms | 3.49x | 3.75x (3.39–4.21x) |
| A | 32 | 756.33 ms | 206.16 ms | 3.67x | 3.58x (3.26–3.81x) |
| B | 32 | 821.08 ms | 210.58 ms | 3.90x | 4.06x (3.81–4.46x) |

Earlier screens had captured-batch ratios around 2.4–2.7x. CPU wall times
varied materially with the shared host, while the final GPU needed about
52 ms for eight matrices. Single-matrix execution remains slower on GPU.
The small synthetic 256 x 1,024 shape also regressed in final confirmation.
No universal GPU advantage or stable 4x claim is justified by this run.

The atomic-only, SIMD-only, and column-cache screen runs remain in
`gpu-tiled-atomic-pivots.json`, `gpu-tiled-simd-pivots.json`, and
`gpu-tiled-cache-screen.json`. The first two show that reducing atomic
contention alone did little for elapsed GPU time. Shared-host CPU variation
prevents interpreting changes in CPU/GPU ratios across separate screens as
GPU-only improvements. These screens are not pooled with confirmation.

The GPU prototype remains opt-in and standalone. It is not a complete GPU
F4/F5 solver, and no production single-query GPU dispatch was installed.

## Correctness and reproduction

`validate.py` checks 202 independently computed Sage/Singular ideals against
the native certificate and Python oracle, including explicit field equations.
It also checks arbitrary corrupted bases, nonreduced candidates, missing
Boolean field pairs, wrong larger ideals, duplicate cancellation, empty/unit
ideals, variable/word boundaries through n=20, large root counts, malformed ABI
offsets and concurrent calls. The suite performs 2,633 differential checks,
rejects 2,302 invalid candidate bases, and runs 128 concurrent calls.
`results/validation-ubsan.json` records the undefined-behavior-sanitized build.
Existing Boolean solver tests and transport/fallback checks are also retained.
All 15 existing targeted Python tests passed. After changing the dual solver's
packing, its 202-ideal Singular comparison also passed, including all 550
invalid-basis checks and the explicit root-cap failure. Six transport/verifier
combinations agreed, and the absent-library fallback passed.

The GPU checks exact packed canonical RREF **and rank** against M4RI. Controls
include exhaustive tiny matrices, padding boundaries, zero/duplicate rows,
unequal ranks inside a batch, pivots with wide column gaps, and the uncached
4,097-row/8,192-row paths. Every timed input is checked as well.

From the repository root, using Python 3.10+ (this machine's system Python 3.9
cannot run the Python oracle's `int.bit_count`):

```sh
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round3/build.py
DOT_SAGE=/private/tmp/groebner-round2-sage sage -python experiments/groebner-perf-20260924/round3/validate.py
DOT_SAGE=/private/tmp/groebner-round2-sage sage -python experiments/groebner-perf-20260924/round3/validate.py --library experiments/groebner-perf-20260924/round3/build/boolean-certificate-ubsan.dylib --output experiments/groebner-perf-20260924/round3/results/validation-ubsan.json
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round3/benchmark_certificate.py
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round3/benchmark_packing.py
DOT_SAGE=/private/tmp/groebner-round2-sage sage -python experiments/groebner-perf-20260924/round3/query_check.py
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round3/run_gpu.py
/opt/homebrew/bin/python3 experiments/groebner-perf-20260924/round3/summarize.py
```

Run timing commands serially. The GPU command requires local Metal access.
Reconstruction of the frozen inputs is in `freeze_inputs.py` and
`capture_matrices.py`; use the existing frozen files for matched comparisons.
Source controls are in `baseline/`; build recipes and hashes are recorded in
`results/build-manifest.json`. Kernel errors and timeouts remain explicit.
