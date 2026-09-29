# Compact row maps and exact zero-word skipping for Metal RREF

This opt-in GF(2) matrix experiment replaces physical pivot-row movement
with a compact row permutation. It also skips a column word only after
proving that every remaining virtual row is zero there. The frozen GPU
comparison is round29's 512-thread, direct-dispatch, 16-pivot implementation;
the CPU reference is the same M4RI `k=5` implementation used in round29.
The solver's portable CPU dispatch is unchanged.

The timing scope is one internal matrix reduction, including fresh buffers
and final ordered output. It excludes polynomial construction, basis
completion, independent algebraic certification and curve replay. It does
not establish complete-query performance, F5 signature compatibility, a new
F6 algorithm, or single-target IC speed. Matrix gains must not be multiplied
into previously measured full-query or IC results.

## Algorithm and correctness argument

Each invocation initializes a logical-to-physical row permutation. Matrix
rows remain immutable during pivot selection and table construction. A swap
changes the permutation and the active rows' cached column words and masks;
it does not copy or reduce the entire selected row. A new column word is
reconstructed from the selected raw rows and their forward mixing masks.
The cached word is then updated as each additional pivot is selected.

Let `S` be the selected raw rows, and let `G` be their invertible submatrix at
the selected pivot columns. The canonical panel is `C = G^-1 S`. The kernel
forms its mixing masks from the unit upper triangular forward pivot block,
then materializes independent eight-bit lookup tables. Those tables must be
complete before any matrix row changes.

For an unselected row `a` with raw pivot bits `v`, the update is `a + v C`.
For selected row `j`, it is `a + (v + e_j) C = C_j`. The unit correction is
essential: omitting it erases even the rank-one matrix `[1]`. Earlier pivot
rows receive the same elimination update; selected raw rows are zero in
earlier pivot columns, so those columns remain canonical. An ordered gather
materializes the final RREF and is included in the wall interval.

When a column has no pivot, a SIMD/threadgroup OR combines the cached word
of **every** remaining virtual row. Bits below the current column are masked
out. The next set bit identifies the next possible pivot; an empty union
allows the whole remaining word to be skipped. This is an exact test, with
zero padding enforced at input. It helps long dependent or zero suffixes
without making a rank prediction. Both skip-enabled and skip-disabled
kernels execute in the correctness and paired timing controls.

The host checks pipeline thread limits and static plus dynamic shared-memory
requirements. Matrices that exceed the row-map scratch budget use the frozen
round29 route, with fallback identified explicitly. Unsupported pipelines
fail explicitly. No numerical pivots, coefficients, roots or answers are
reused between inputs. Apple Metal capability checks do not establish CUDA,
OpenCL, HIP or physical Intel/AMD compatibility.

## Measurement contract

Each of six frozen matrices has one warmup and 31 measured groups. Five arms
run in shuffled order: CPU, frozen round29 GPU, mapped16, mapped32 and mapped32
with the opposite word-skip setting. The default setting enables skipping.
The CPU uses `USER_INITIATED` QoS. Initial, per-group and final one-minute
host load must not exceed the reported logical CPU count. Rejected runs stay
in the exploration record and are not timing wins.

Input loading and pipeline creation are outside timing. Fresh allocations,
permutation initialization, input transfers, command submission, device
synchronization, ordered output extraction and buffer destruction are inside.
Every paired sample must match the CPU's exact rank and complete RREF;
comparison is mandatory and excluded from the kernel interval.
No repeated-call result is an independent-target throughput estimate.

Medians describe absolute times. Ratios are paired geometric means with
individual, unadjusted 95% bootstrap intervals from 5,000 resamples. These
intervals describe repeated calls on the measured host and frozen matrices.
They do not describe variation across targets or hardware.

## Source-bound physical confirmation

The final-source five-arm confirmation ran on a physical Apple M4 Pro
(14 logical CPUs, macOS ARM64). Every admission gate passed. The primary
candidate uses **512 threads, 32 pivots and exact word skipping**. All eight
runtime/harness source hashes match this patch. The receipt's Git `head` is
its pre-commit checkout context; the source inventory identifies the actual
uncommitted files that were built and executed.

| Matrix | CPU ms | Previous GPU ms | Mapped32 GPU ms | Previous / mapped32 [95%] |
| --- | ---: | ---: | ---: | --- |
| Captured seed1 | 14.5220 | 14.8595 | 11.5209 | 1.280 [1.260, 1.299] |
| Captured seed2 | 15.3590 | 14.7818 | 11.6855 | 1.266 [1.248, 1.284] |
| Random 256 × 1024 | 0.1833 | 0.9499 | 0.8387 | 1.175 [1.115, 1.256] |
| Random 1536 × 3072 | 2.7133 | 5.9319 | 5.2054 | 1.143 [1.115, 1.171] |
| Random 2048 × 4096 | 5.3915 | 8.6123 | 7.3162 | 1.155 [1.081, 1.211] |
| Captured seed1 with duplicate rows | 8.1381 | 12.0768 | 7.6443 | 1.565 [1.526, 1.602] |

The paired no-skip/skip capture ratios are **1.071 [1.051,1.089]** and
**1.083 [1.060,1.106]**. The duplicate-row control gains
**1.211 [1.182,1.239]** from skipping. The three full-rank random controls
show no clear independent word-skip benefit. The full five-arm samples,
including mapped16 and the ablation, remain in `results/measure.json.gz`.

The simultaneous CPU/mapped32 capture ratios are
**1.276 [1.231,1.325]** and **1.340 [1.265,1.430]**. These are admitted,
within-run observations, **not a quiet-host or general CPU superiority
claim**: other CPU-heavy jobs were active, and earlier M4RI capture medians
were about 12.4 ms. The load gate permits some contention and does not fix
CPU frequency or core placement. CPU wins all three random controls; the
duplicate-row CPU comparison is inconclusive. Keep CPU routing unchanged
until stronger CPU controls and complete-query timings justify a decision;
the separate lower-load run below narrows this particular uncertainty.

### Separate lower-load confirmation

After the code commit, host load fell and a second run used the same eight
sources without modifications. Initial/final one-minute load was 5.77/6.54,
versus a 14-logical-CPU admission limit. All controls and measurements passed;
`results/lower-load/` retains its separate receipt, raw samples and audit.

| Matrix | CPU ms | Previous GPU ms | Mapped32 GPU ms | CPU / mapped32 [95%] |
| --- | ---: | ---: | ---: | --- |
| Captured seed1 | 12.6779 | 14.5041 | 11.2643 | 1.106 [1.092, 1.120] |
| Captured seed2 | 12.5328 | 14.4433 | 11.2440 | 1.106 [1.093, 1.120] |
| Random 256 × 1024 | 0.0742 | 0.9217 | 0.7941 | 0.097 [0.087, 0.109] |
| Random 1536 × 3072 | 2.2154 | 5.8060 | 4.9161 | 0.437 [0.429, 0.445] |
| Random 2048 × 4096 | 4.7140 | 8.6007 | 7.3586 | 0.626 [0.615, 0.637] |
| Captured seed1 with duplicate rows | 5.9120 | 12.0102 | 7.5183 | 0.771 [0.756, 0.784] |

This confirms a **modest matrix-component crossover on the two captures**
against the declared M4RI `k=5` reference: both paired ratios are about 1.106,
with 95% intervals [1.092,1.120]. The previous-GPU gains remain 1.277
[1.260,1.294] and 1.277 [1.258,1.296]. CPU returns near its earlier quieter
medians, reducing the first run's apparent CPU advantage substantially.
These are repetitions on the same frozen captures, not held-out targets.

CPU wins the other four controls. Word skipping gains about 5.8–6.5% on the
captures and 21.8% on duplicate rows, but regresses the random 256 × 1024 and
2048 × 4096 cases by about 4.5% and 3.3% respectively in paired ratios.
Retain both paths; a measured selection policy and fresh CPU tuning are
future experiments. A matrix crossover does not establish complete-query
performance or justify a general GPU default.

## Retained exploration and failures

The initial row-map version passed exact controls but only modestly improved
the 16-pivot path; its 32-pivot capture medians (14.49 and 14.38 ms) did not
beat the frozen GPU (14.32 and 14.34 ms). Caching reduced column words and
adding exact zero-word skipping produced a promising first screen around
11.7–11.9 ms, followed by the separate five-arm confirmation above.

Three intermediate timing attempts were rejected at initial host-load
admission. Their correctness checks passed, but they have no admitted timing
samples and are not wins. `results/exploration.json` retains their statuses,
source inventories, report/receipt hashes and logs, alongside the successful
screens. The full source/binary bundles remain in the task's external
`row-map` evidence archive. Historical screens have their own source hashes;
they must not be presented as final-source measurements.

## Reproduction and validation

Use Python 3.11+, a Metal-capable Mac and a native M4RI installation. Every
output directory must be new; previous receipts are never overwritten.

```sh
python experiments/groebner-perf-20260924/round30/run.py \
  --output /absolute/path/new-run --m4ri-prefix /path/to/m4ri --threads 512
python experiments/groebner-perf-20260924/round30/audit.py /absolute/path/new-run
python experiments/groebner-perf-20260924/round30/test_audit.py \
  --bundle /absolute/path/new-run
python experiments/groebner-perf-20260924/round30/test_model.py
```

`--mode correctness` omits timings. `--threads` accepts 256, 512 or 1024;
`--no-word-skip` reverses which skip setting is the primary candidate, while
retaining the opposite setting as an ablation. These are explicit experiment
options, not automatic device routing.

Each native correctness run requires **6,336 exact rank/RREF comparisons**,
including both panel widths and both word-skip settings. Controls include
exhaustive tiny matrices, zero and duplicate rows, word/panel boundaries,
gapped pivots, large scratch fallbacks, forced fallback, unequal-rank batches,
both captured matrices and three invalid-input rejections. A complete timing
run adds **768 exact comparisons**. The independent Python algebra model uses
ordinary Gauss-Jordan inversion and checks 7,707 small width/instance pairs.

The auditor binds eight source snapshots to the current trusted files,
generated baseline text, compiler flags, native binary, frozen input, loaded
M4RI identity and raw reports. The generated baseline differs from round29
only by renaming its entry point. Corruption tests reject altered inputs,
ranks, arms, warmups, fallback labels, skip configurations, load gates,
timings, binaries, sources, generated baseline and library identity.

CI executes the independent model and retained-record checks on Linux, then
installs native M4RI and rebuilds host code on macOS, then executes Metal controls
at all three thread counts. The actual hosted device identity is retained;
virtualized execution must not be presented as a physical hardware test or a
performance qualification.
