# Wider GPU pivot panels and trailing updates

This opt-in GF(2) RREF experiment improves the previous GPU implementation on
the two frozen captured matrices. It **does not establish a GPU advantage over
CPU or complete the single-query GPU acceptance gate**. CPU solver dispatch is
unchanged. This is internal matrix work, not final IC relation linear algebra;
candidate identity, complete target recovery cost and rho comparison remain
unknown. No F5 signature semantics or new F6 algorithm are claimed.

## Changes and correctness argument

`local_panel.metal` retains the eight- or sixteen-row active pivot panel and
virtual reduction masks in threadgroup memory. Only physical row moves require
device visibility during pivot selection; panel reduction uses threadgroup
barriers. The panel is committed once. The host checks the actual pipeline's
static and dynamic memory requirements and uses the original global-memory
panel when the local allocation does not fit.

A sixteen-pivot panel uses two independent eight-bit Four-Russians tables.
Splitting the coefficient mask into two bytes makes its update the XOR of two
table entries. Table storage grows linearly with panel width instead of using
a 65,536-row table. This halves the number of panel dispatch groups and reduces
full-matrix passes relative to the original eight-pivot implementation.

Every active pivot row has zero words before the first pivot column. Table
construction and elimination therefore skip that word prefix. For row strides
divisible by sixteen bytes, four adjacent words are processed per thread.
Other strides retain scalar accesses. Earlier pivot rows still receive the
trailing update, so the result is canonical RREF, not just forward echelon form.

## Interleaved confirmation

`confirm.mm` runs CPU M4RI (`k=5`), original GPU, and revised GPU in one process
on each exact input, with shuffled arm order, one retained warmup and fifteen
measured repetitions. CPU QoS is explicitly `USER_INITIATED`; thread CPU time
is recorded as a scheduling diagnostic. **Wall time remains the comparison
metric.** Both GPU arms allocate fresh numerical buffers per call. Timings
include allocations, transfers, dispatch, synchronization and output extraction.
Pipeline initialization, input loading and exact output comparison are separate.

Apple M4 Pro, macOS 26.6, shared host:

| Frozen 2915 by 4096 input | Original GPU wall median | Revised GPU wall median | Paired old/new wall ratio, 95% bootstrap interval |
| --- | ---: | ---: | ---: |
| Seed 1 | 38.354 ms | 29.788 ms | 1.412x [1.064, 1.904] |
| Seed 2 | 50.464 ms | 35.000 ms | 1.372x [1.070, 1.769] |

Device medians fell from 30.320 to 19.460 ms and from 30.342 to 19.313 ms.
Paired device ratios are 1.549x [1.531, 1.568] and 1.573x [1.553, 1.596].
These are improvements over the old GPU kernel, not complete query speedups.

CPU wall medians were 34.472 and 34.269 ms, while thread CPU medians were 19.699
and 18.168 ms. Scheduling variation is material. The paired CPU/revised-GPU wall
ratios were **0.964x [0.640, 1.388]** and **0.896x [0.650, 1.276]**; neither
establishes a CPU/GPU crossover. Do not use a ratio of the displayed medians as
the paired result. Additional independent synthetic shapes and a duplicated-row
control remain in the confirmation, including regressions on the small matrix.
The intervals describe repeated invocations on this host, not independent target
populations. Complete polynomial construction, basis completion, independent
certificate checking and curve replay are not included in these matrix timings.

## Screens, profiling and qualification

The original GPU reference, local panel alone, sixteen-pivot panels, and final
vectorized trailing updates each passed **848 exact rank/RREF comparisons**.
Controls include exhaustive tiny matrices, zero/duplicate rows, unequal ranks,
word boundaries, pivot gaps, and uncached 4097/8192-row cases. The interleaved
confirmation adds **192 exact comparisons**. These are local Metal execution
receipts. CI audits the receipts and compiles both panel-width host variants;
it does not claim to execute GPU shaders on hosted workers.

Local panel caching alone did not produce a clear speedup. Wider panels and
trailing vectorization were retained after exploratory screens, then evaluated
against the old implementation in the separate interleaved confirmation.
Earlier negative fusion and 32-thread screens remain in `../round6/`, including
their disclosed seed-label issue. The current harness consumes each exact named
matrix rather than cycling a capture pool under multiple labels.

The device exposes stage-boundary counters but no dispatch-boundary counters.
`profile_rref.mm` places each kernel in a separate encoder, which changes
synchronization and adds overhead. Its instrumented captured-matrix samples
attribute about 15 ms to panels, 14--15 ms to elimination, and 2.5 ms to tables;
the command-buffer total is larger because of inter-pass gaps. These are
diagnostics only, not uninstrumented performance claims. Timestamp handling
follows Apple's [Metal counter profiling documentation](https://developer.apple.com/videos/play/tech-talks/10001/).
The first manual profile has a post-run inventory with missing historical load
metadata explicitly null. Subsequent screens have contemporaneous launch
receipts, source snapshots, binary/input/library hashes, loads and all samples.

## Reproduction

On a Mac with Metal and M4RI, use a new label to avoid overwriting outcomes:

```sh
python experiments/groebner-perf-20260924/round7/run_gpu.py \
  --variant local --panel-width 16 --label new-screen \
  --m4ri-prefix /path/to/m4ri
python experiments/groebner-perf-20260924/round7/run_gpu.py \
  --variant confirm --panel-width 16 --label new-confirmation \
  --m4ri-prefix /path/to/m4ri
```

The evidence audit is intentionally frozen to the retained five receipts and
336 sample groups, including warmups; put new experiments in a separate evidence
set or deliberately extend the audit. Run the historical audit on Python 3.10+:

```sh
python experiments/groebner-perf-20260924/round6/summarize.py
python experiments/groebner-perf-20260924/round7/audit.py
```

Next work must demonstrate a reliable CPU/GPU crossover and then integrate the
winning path into a complete independently verified query. This experiment does
not close either requirement. Structural F6 hypotheses and the full verified
one-target IC/rho comparison also remain open.
