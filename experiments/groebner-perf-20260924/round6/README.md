# Single-matrix GPU fusion screen

This is an opt-in, **negative** GF(2) matrix experiment. It does not change
F4/F5 dispatch, implement a complete GPU polynomial solver, or establish an IC
speedup. PR #123 merged the separate algebraic certificate work; this follow-up
experiment is retained locally for the next GPU iteration.

The hypothesis was that eliminating the separate Four-Russians table dispatch
would reduce latency for one matrix. `eliminate_direct` instead XORs the selected
panel words directly into each non-panel row. New panel rows have zero masks
and are immutable during that dispatch. This reduces each eight-pivot panel
from three dispatch stages to two, but repeats work across row/word threads.
A second screen reduced the pivot threadgroup from 256 to 32 threads.

Neither screen established a single-matrix advantage. The corrected 256-thread
run compares against M4RI with `k=5`, the previously identified CPU setting:

| Frozen matrix | CPU median | GPU wall median | GPU device median |
| --- | ---: | ---: | ---: |
| Seed 1, 2915 by 4096 | 22.420 ms | 34.251 ms | 30.167 ms |
| Seed 2, 2915 by 4096 | 22.473 ms | 35.464 ms | 29.573 ms |

These are independent single-matrix invocations, with one retained warmup and
nine measured CPU/GPU pairs per matrix. Arm order alternates. Both timings
include fresh allocations, copies and rank/RREF extraction; GPU time also
includes dispatch, synchronization and buffer destruction. Initialization is
reported separately. Correctness comparison is outside timing. No target
batch average is substituted for single-query latency, and this is not the
complete polynomial-query boundary.

Every run checked 848 matrices against exact M4RI RREF **and rank**, including
exhaustive tiny matrices, word boundaries, duplicate/zero rows, pivot gaps,
unequal ranks in correctness-only batches, and uncached large-row cases. The
32-thread screen was slower, reaching approximately 73--77 ms on the captured
input. Its device time also increased, so host scheduling alone does not
explain that regression. Separate screens do not establish a paired
old-GPU/new-GPU speedup; the shared host had substantial timing variation.

## Retained limitation and source versions

The original round-three harness cycled through a pool of equal-shaped real
matrices. Its initial single-matrix adaptation still selected pool element zero
for both seed-labelled cells. Thus `fused-screen.json` and
`fused-32-screen.json` each timed seed 1 twice, under different labels. They are
retained as negative exploratory screens, with their source snapshots, and
must not be represented as two independent captured workloads.

`fused-corrected-256-screen.json` fixes that selection: each cell consumes the
exact named frozen matrix. The current source also records pivot width and
M4RI `k`. `baseline/` preserves the original 256-thread code;
`baseline/pivot-threads/` preserves the configurable code used for 32 threads.
The matrix file is the existing `../round3/matrices.json.gz`.

`results/manifest.json` binds these retained sources, binaries and outcomes.
It is explicitly a **post-run inventory**, not a contemporaneous launch
receipt. Historical load samples, exact initial compiler command lines, and
per-run peak memory were not captured and remain unknown. `summarize.py`
audits the retained files and reports paired CPU/GPU ratios with 95% bootstrap
intervals. Those intervals concern repeated invocations on this shared host,
not a population of independent targets.

Reproduce the corrected source on a Mac with Metal and M4RI installed:

```sh
mkdir -p experiments/groebner-perf-20260924/round6/build
gzip -dc experiments/groebner-perf-20260924/round3/matrices.json.gz > experiments/groebner-perf-20260924/round6/build/matrices.json
clang++ -O3 -std=c++17 -fobjc-arc -DFUSED=1 -DPIVOT_THREADS=256 -DM4RI_K=5 \
  experiments/groebner-perf-20260924/round6/fused_rref.mm \
  -I/path/to/m4ri/include -L/path/to/m4ri/lib -lm4ri \
  -framework Foundation -framework Metal \
  -o experiments/groebner-perf-20260924/round6/build/fused-rref
experiments/groebner-perf-20260924/round6/build/fused-rref \
  experiments/groebner-perf-20260924/round6/fused_rref.metal \
  experiments/groebner-perf-20260924/round6/build/matrices.json > /tmp/gpu-fused-new.json
python experiments/groebner-perf-20260924/round6/summarize.py
```

The current default-width shader matches the 256-thread host build. A different
width requires prefixing the same `PIVOT_THREADS` definition to the shader;
changing only the host flag is invalid. The CPU remains the default. The next
GPU hypothesis should address pivot dependency and synchronization, followed by
measurement of a complete single query with independent verification.
