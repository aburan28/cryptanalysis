# RTX PRO 6000 benchmark and audit preset

Run from the `ecc2k130` directory with Modal installed and authenticated:

```bash
make bench-rtx-pro6000
make audit-rtx-pro6000
```

The first target runs three complete walk benchmarks. The second performs
GPU arithmetic and integration checks, three benchmarks, and three DP
collection runs; it writes `build/rtx-pro6000-audit.json`. Both allocate one
RTX PRO 6000 Blackwell Server Edition through Modal. Set `MODAL=/path/to/modal`
when using a specific client environment.

The preset selects CUDA 13.0.0, the packed backend, batch 32, 256 threads per
block, minBlocks 2, 192,512 worker threads, 1,024 steps per launch and 32 launches.
The selected worker count is twice the automatic count on the tested 188-SM
server GPU. Set `RTX_PRO6000_WORKERS=0` to use automatic workers, or provide
an explicit count to either Make target. Existing checkpoints still require
their original worker and batch counts; benchmark and audit presets do not
resume user checkpoints. It enables the single
polynomial product, denominator cache, by-value operands, both Frobenius
networks, polynomial chains, explicit inversion schedule and paired products.
The preset also enables [polynomial coordinate storage](POLYNOMIAL-STATE.md)
and [direct-order polynomial reduction](DIRECT-REDUCTION.md).
These settings retain the existing iteration, DP report and packed-checkpoint
semantics. The linked comparison validates normal-to-polynomial resume and
the reverse direction, and measures both modes on one GPU.

CUDA 13.0 requires a compatible driver; the tested driver is 580.95.05.
NVIDIA lists 580.65.06 for the Linux CUDA 13.0 GA toolkit in its
[release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html#cuda-driver).

The measured hardware ceilings that bound this preset are in
[THROUGHPUT-CEILING.md](THROUGHPUT-CEILING.md).

## Direct-order reduction comparison

The [paired reducer comparison](benchmarks/direct-reduction/comparison.json)
uses identical B32/T256/min2 settings, 192,512 workers and
201,863,462,912 scalar updates per sample on one GPU. Three alternating
benchmark confirmations and three collection runs per mode measured:

| Workload | Previous reducer | Direct reducer | Change |
|---|---:|---:|---:|
| Benchmark median B scalar updates/s | 6.826154 | **6.906059** | +1.17% |
| DP34 collection median B scalar updates/s | 6.722592 | **6.799047** | +1.14% |

The new reducer was faster in every paired repetition. All six collections
produced identical sorted record multisets: 5,149 records, 164,768 bytes and
zero drops. GPU arithmetic, complete client integration and whole-state
comparisons passed before timing. Warm-ups are excluded from these medians.
[DIRECT-REDUCTION.md](DIRECT-REDUCTION.md) records ranges, derivation, the
instruction/spill tradeoff and source/binary provenance.

The [updated native preset audit](benchmarks/direct-reduction/native-audit.json)
runs the normal `make audit-rtx-pro6000` entry point on a separate allocation:

| Workload | Median B scalar updates/s | Range across three repetitions |
|---|---:|---:|
| Complete walk benchmark | **6.905227** | 6.884149–6.928427 |
| DP34 collection | **6.767191** | 6.765677–6.767747 |

Every repetition completed 201,863,462,912 scalar updates with reducer mode 1.
Each collection recorded 5,149 points, 164,768 bytes and zero drops. The expanded
GPU arithmetic suite and full client validation passed before timing. This
native audit validates the published command; the paired comparison above
estimates the reducer's gain. Source, binary and separate audit-entry-point
hashes are recorded in [DIRECT-REDUCTION.md](DIRECT-REDUCTION.md).

## Historical launch and worker tuning

The [configuration comparison](benchmarks/launch-tuning/configuration-comparison.json)
uses one GPU, with three alternating confirmations and three collection runs
per selected configuration. Both modes execute the same 100,931,731,456 scalar
updates with 96,256 workers. Changing the block shape preserves the worker
population, walk rule and checkpoint contents.

| Workload | 128 threads, minBlocks 4 | 256 threads, minBlocks 2 | Change |
|---|---:|---:|---:|
| Benchmark median B updates/s | 6.548444 | **6.689864** | +2.16% |
| DP34 collection median B updates/s | 6.418022 | **6.558691** | +2.19% |

All eight candidate binaries passed GPU arithmetic and normalized-state
checks. The control and winner passed the full integration suite. Each of
these six collection runs produced identical record multisets, 2,633 records,
84,256 bytes and zero drops. The winning configuration disables both
experimental shared spilling and signless Y; those experiments are not part
of the preset or this implementation change.

A separate [worker-grid comparison](benchmarks/launch-tuning/worker-comparison.json)
uses the winning block shape, with the same 113,548,197,888 total updates for
every grid. Three alternating confirmations and collections measured:

| Workload | Automatic 96,256 workers | 192,512 workers | Change |
|---|---:|---:|---:|
| Benchmark median B updates/s | 6.661737 | **6.741471** | +1.20% |
| DP34 collection median B updates/s | 6.577144 | **6.654030** | +1.17% |

The grids have different numbers of seeded walks and per-walk lengths.
Automatic-grid collections each contain 2,943 records; doubled-grid
collections each contain 2,922. All report zero drops, and record multisets
match within each grid's repeated workload. Their different corpora are not
treated as an error. Cache capacity and buffer allocation probes are included;
they do not measure cache hits or prove that a working set stays resident.

The [clean-source block-only audit](benchmarks/launch-tuning/block256-auto-audit.json)
measured 6.720825 B/s benchmark and 6.606040 B/s collection medians with automatic
workers. It ran on a separate allocation and does not independently estimate
the block-shape gain.

The [combined-preset native audit](benchmarks/launch-tuning/combined-native-audit.json)
uses the normal `packed_audit.py` entry point with 256-thread blocks,
minBlocks 2 and 192,512 workers. Its three-repetition results are:

| Workload | Median B scalar updates/s | Range |
|---|---:|---:|
| Complete walk benchmark | **6.803077** | 6.788477–6.855009 |
| DP34 collection | **6.692647** | 6.690176–6.696499 |

Every repetition completes **201,863,462,912 scalar updates**: 6,160,384 walks
through 32 launches of 1,024 steps. Each collection reports **5,149 records,
164,768 bytes and zero drops**. GPU arithmetic and full integration/replay
gates pass before timing. The final timer includes pending reseeds; setup and
CPU reference replay are outside the timed interval. The wrapper validates the
requested workers and completed scalar counts before accepting any rate.
Benchmark variation within this audit is shown explicitly; it is not a new
paired estimate of the combined speedup.

All comparisons retain compiler, GPU, source and binary identity. Experimental
source was used to screen configurations; the promoted settings disable those
experiments. These historical native audits build the production C++/CUDA source before
the direct-reduction change.
Their source digests identify the frozen audit snapshots; the final PR also
adds a count-integrity regression test after measurement.
Do not multiply percentage gains or compare absolute rates across allocations
to infer an additional combined speedup.

## Historical standalone CUDA 13 audit with normal storage

The [standalone audit](benchmarks/cuda13/native-audit.json) used the normal
`packed_audit.py` launch path with the earlier normal-storage preset parameters,
on the CUDA 13.0.0 image:

| Workload | Median B scalar iterations/s | Range across three repetitions |
|---|---:|---:|
| Complete walk benchmark | **6.317452** | 6.301125–6.317701 |
| DP cutoff 34 collection | **6.185531** | 6.185358–6.193231 |

This audit used a different GPU allocation from the compiler comparison
below. Its absolute rates should not be used to estimate the compiler's
isolated gain. Both sets of results retain their full environment identity.

## Compiler comparison on one GPU

The [complete comparison](benchmarks/cuda13/compiler-comparison.json) compiled
the same source with nvcc 12.8.93 and 13.0.48, then ran both binaries on the same
RTX PRO 6000 allocation. Both used native sm120 code and identical build knobs.
Three repetitions alternated CUDA 12.8 then CUDA 13.0 for each workload.

| Workload | CUDA 12.8 median B iterations/s | CUDA 13.0 median B iterations/s | Change |
|---|---:|---:|---:|
| Complete walk benchmark | 6.205207 | **6.268586** | +1.02% |
| DP cutoff 34 collection | 6.075874 | **6.159745** | +1.38% |

Benchmark ranges were 6.171362–6.209920 B/s for CUDA 12.8 and
6.245650–6.309846 B/s for CUDA 13.0. Collection ranges were 6.075587–6.079389
and 6.158061–6.162090 B/s, respectively. Rates drifted downward during the
comparison; the CUDA 13 binary remained faster in every paired repetition.
The compiler gain in this comparison was modest.

Every timed run completed 100,931,731,456 scalar walk iterations. Each
collection repetition wrote 2,633 records, dropped zero, and matched its
corpus-file size. Walk synchronization, prior-launch restarts and host report processing were
timed; initial setup was excluded. These historical binaries did not wait for
any remaining final asynchronous reseed before stopping the timer. Current
binaries include that final wait; see the polynomial-state comparison for
measurements of the corrected timing boundary. CPU trail replay is disabled during timing
after separate correctness checks pass.

Both binaries passed 3,120 GPU Frobenius vectors, 1,261 reductions, 18,185
individual polynomial products and 18,185 paired cases checking both outputs.
Integration checks cover report replay across launches and restarts, exact
resume, scalar accounting, preservation of incompatible checkpoints and the
overdue-walk guard. Checkpoints from both compilers match byte-for-byte at
common worker and step counts.

The measured source is commit `4bd7f5d1142896f53be7ed4fe73249dbe3fa4f25`,
with source digest `69912aa7bd5afcef721bc97030d5741515c5eb40cb4820d7e59210a63587d95b`.
The original preset added command aliases around those build and runtime
options; the current preset also selects polynomial coordinate storage. Compiler versions, binary hashes, GPU identity and complete raw
output are included in the comparison artifact.

These measurements count complete scalar walk iterations. They do not
establish 60 B iterations/s, performance on other GPUs, or live clock traces;
the GPU-state metadata is a snapshot taken before validation.
