# Faster Boolean F4 for the index-calculus oracle, and F4/F5 on a GPU

**Result: `PASS_LOCAL` as a PDP-stage improvement; the GPU path is built,
emulator-verified and compiled, but unmeasured on a device.** On one core,
with every verdict, relation, solver counter and recovered logarithm
unchanged, the Gröbner decomposition oracle runs **7.5–7.7×** faster inside
complete `ca-ic run --solver groebner` DLPs at degree 23, **1.9–10.4×** on the
frozen stage ladder, and the research degree sweeps run **190–280×** faster.
With four cores the degree-23 run collects its relations in **1.49 s against
the original 41.9 s**. The end-to-end total in a calibrated operation unit,
`S`, and the rho ratios stay **unknown**: the pipeline prices no phase in
operations.

Source: commit `62489c0` (records hash these files as of that commit).
Host: Intel Xeon VM, 4 vCPU, 15 GiB, no GPU; Rust 1.98.1 release profile.

## 1. Baseline and where the time went

`ca-ic run --degree 23 --curve-a 1 --solver groebner --batch 1` on the
original binary (`receipts/baseline-original/run_23_1.json`): relation
collection is **41.88 s of 41.88 s**; the relation matrix takes 0.14 ms.
`K_0/2^23` is 70.21 s of 70.21 s. The decomposition oracle *is* the DLP.

Inside it (`groebner_stage_bench`, original binary, `stage-frozen.json`):

| rung | F4 calls | rows × cols / call | build | reduce | readback | wall |
|:-----|---------:|-------------------:|------:|-------:|---------:|-----:|
| `K_1/2^23` | 9 850 | 276 × 438 | 2 911 ms (31%) | 3 509 ms (38%) | 2 627 ms (28%) | 9.26 s |
| `K_0/2^19` (holdout) | 432 | — | 576 ms | 401 ms | **760 ms** | 1.76 s |

Elimination was never the whole cost: building each matrix (a SipHash map
from monomial to column, two sorts, a heap `Vec` per row, and an
environment-variable read per row for the size cap) and reading every
reduced row back into a re-sorted polynomial cost as much again. A GPU RREF
alone would have been capped near **1.6×** on the largest rung — the same
lesson as ROADMAP row 20's Metal RREF, 9–21× slower than M4RI.

## 2. What changed

| change | why the answers cannot move |
|:-------|:----------------------------|
| **Rank-indexed build** (`f4_gf2`): a column's index is `base[deg] + Σ C(cᵢ, i)` — descending DegRevLex — through a stamped array; rows written by XOR, so Boolean collisions cancel with no sort | same column order, same rows |
| **Decision without full reduction**: forward elimination over the degree ≥ 2 columns only, then an RREF of the ≤ 65-bit linear block (`u128` rows) | the rows left with a zero high part span exactly the row space ∩ linear span, whose RREF is the low block of the full RREF; refutation and forced variables live there |
| **No rows over absent variables**: multipliers range over the variables still occurring | such rows sit in columns of their own and give a linear row only alongside a refutation; the caps are still applied in the reference builder's units (`Σ_{j≤s} C(N, j)` per row of slack `s`), so a matrix is oversize exactly when it was |
| **F5 row pruning**: F5 criterion (`t` leads the degree-`D − deg fᵢ` row space of `f₀…f_{i−1}`) and the Boolean field-equation criterion (`f² = f`, so `s·f = Σ_{a∈supp f}(s·a)·f`) | every dropped row is a sum of rows of smaller key; by induction every reduced echelon form is unchanged |
| **Lockstep search** (`f4_batch`): the recursive solver as an explicit state machine, so a batch of searches hands every round's matrices to one backend call | each search takes the same steps; tested against the recursive solver including exhausted budgets and capped solution counts |

`matrix_f4_f2` returns the reference rows bit-for-bit; `F4_F2_RREF=reference`
keeps the original kernel in the binary as the paired control.

## 3. Results

### PDP stage inside complete, verified DLPs (paired, one core)

Same binary, arm selected by `F4_F2_RREF`, three blocks, alternating order.
Records: `runs.jsonl` (validated by `../ic-candidate-catalog/analyze.py`),
manifests: `manifests/`. Curve IDs `EC1N23Cka1h7ef98b42c1e8`,
`EC1N23Cka0hd721efe98d4e`.

| workload | baseline candidate (reference kernel) | candidate (f4_gf2 + F5) | correct | PDP wall, baseline / candidate (95% CI) | calibrated total | `S` | rho ratio |
|:---------|:--------------------------------------|:------------------------|:-------:|:-----------------------------------------|:----------------:|:---:|:---------:|
| `W35c075f41d7b` (`K_1/2^23`, `[53]G`) | `IC1N23Cka1fb2071PDP2f4RCsampleLAgaussTDdirectISO0hc16a334307d3` | `IC1N23Cka1fb2071PDP2f4RCsampleLAgaussTDdirectISO0ha8c82a7d1d6a` | 3/3 both, same log | **7.52×** [7.36, 7.81] | null | null | null |
| `W793f7a80cc3f` (`K_0/2^23`, `[53]G`) | `IC1N23Cka0fb2025PDP2f4RCsampleLAgaussTDdirectISO0hffc66d027711` | `IC1N23Cka0fb2025PDP2f4RCsampleLAgaussTDdirectISO0h4692377ff0a8` | 3/3 both, same log | **7.70×** [7.66, 7.74] | null | null | null |

Both arms made the same queries, found the same relations, refuted the
same targets (189 of 303 at `K_0`; no budget exhaustion) and ran the same
F4 reductions. The word XORs fall 3.6× (`4.79e9 → 1.34e9` at `K_1`). The
whole-run wall ratio equals the PDP one (7.51×, 7.69×): nothing else moved.

With the cores: `--batch 16` collects the `K_1/2^23` relations in **1.489 s**
(`receipts/e2e-batch/`), against 41.88 s for the original binary on one
core; the lockstep path with the host kernel takes 1.893 s and with the
emulated GPU kernel 5.59 s, all with the same 64 trials, 27 relations,
23 351 reductions and logarithm 53.

### Frozen stage ladder (paired, one core, three repetitions)

Every verdict digest, reduction, infeasibility certificate, propagation,
split, oversize event and reference row/column count is identical
(`summary.json` → `stage_ladder`).

| rung | wall ratio (95% CI) |
|:-----|:-------------------:|
| `K_0/2^9`, m = 2 | 4.33× [4.28, 4.39] |
| `K_0/2^9`, m = 3 | 10.43× [9.96, 10.80] |
| `K_0/2^13`, m = 2 | 7.70× [7.61, 7.87] |
| `K_1/2^15`, m = 2 | 1.94× [1.81, 2.02] |
| `K_1/2^17`, m = 2 | 5.72× [5.61, 5.81] |
| `K_1/2^23`, m = 2 | 7.29× [7.28, 7.30] |

On `K_1/2^23` build falls 5.6×, elimination 6.1×, readback from 2.6 s to
under 1 ms.

### One large matrix per degree (research sweeps)

`examples/f4_degree_bench.rs` (`receipts/degree/`): all four paths report the
same rank, refutation and pinned variables (asserted).

| matrix | rows × cols | dense reference | sparse (previous sweep path) | fast | fast + F5 (F5 rows) |
|:-------|------------:|----------------:|-----------------------------:|-----:|--------------------:|
| `K_0/2^13`, m=2, D=5 | 30 225 × 53 871 | 25.0 s | 162.8 s | 6.38 s | **3.90 s** (1 993) |
| `K_1/2^11`, m=2, D=5 | 14 861 × 21 196 | 2.68 s | 21.4 s | 0.48 s | **0.25 s** (1 125) |
| `K_0/2^9`, m=3, D=5 | 33 147 × 87 118 | — | 4.08 s | 1.40 s | **0.93 s** (1 115) |

F5 leaves out only ~7% of the rows but saves 1.2–1.8×: they are the rows
that would have been reduced to zero through the longest pivot chains.
`solving_degree` and `first_fall_degree` now use this path, and
`dreg_sweep --d-max 5 --trials 4 --n-max 13` prints the **identical table**
(`receipts/dreg/`) while its `n = 11, m = 2` cell drops from 594.3 s to
3.1 s and `n = 13, m = 2` from 169.4 s to 0.6 s.

### Batched decisions and the GPU kernel on the emulator

`examples/f4_batch_bench.rs` (`receipts/batch/`), 64 targets on each
degree-23 curve: `sequential`, `rayon`, `lockstep:cpu` and
`lockstep:emulate` produce the same verdict digest and counters. Replaying
the 20 000 matrices those searches requested:

| backend | decisions / s |
|:--------|--------------:|
| host kernel, 1 thread | 9 936 |
| host kernel, 4 threads | 38 981 |
| device kernel, emulated (4 threads × one serial 256-thread block) | 10 034 |

The emulator executes the CUDA source one emulated thread at a time; its
rate says nothing about a GPU and it exists to prove the source correct.

`suite/cuda/build_kernel.sh` with CUDA 13.3 (`receipts/cuda/`): sm_75,
sm_80, sm_86, sm_89, sm_90 and sm_120 all build with 48–64 registers,
10 640 B of shared memory, **no spills**; NVRTC 12.9 compiles the embedded
source.

## 4. The GPU design

- **Batch, don't offload.** One 276 × 438 matrix is ~16 KB and ~100 µs on a
  core even with the fast kernel; a launch per matrix loses to its own
  latency. Relation collection
  has thousands of independent targets, so `f4_batch` runs their searches
  in lockstep and each round becomes one launch of thousands of matrices.
- **Everything on the device, one block per system.** Build (a rank bitmap,
  block-wide prefix popcounts for dense columns — no hashing, no sorting),
  reference-unit caps, forward elimination by (leading column, row) minimum
  so empty columns cost nothing, and the linear-block RREF. Only the
  equations go down and 64 bytes per system come back.
- **F5 on the device as a row mask.** The host's symbolic preprocessing
  (`f4_gf2::f5_row_mask`) marks rows in the kernel's candidate order; the
  kernel counts them for the caps and eliminates the rest — the host picks
  rows, the device does the linear algebra.
- **Tested without a device.** `cuda/f4_gf2_device.cuh` is the common subset
  of C11 and CUDA, written as barrier-separated phases in which each thread
  writes only its own locations or uses an atomic, so
  `cuda/f4_gf2_emulate.c` runs that very source on the host. The emulator
  already caught one real bug (a double-buffered pivot slot left stale by a
  column without a pivot, now triple-buffered and race-free on a device).
- **No new dependency.** `libcuda` and NVRTC are `dlopen`ed through `libc`;
  the default build is unchanged, and the emulator is behind the
  `gpu-emulator` feature because it needs a C compiler.

### Running it on a GPU host

```sh
cd suite && cargo build --release --examples --bin ca-ic
# The kernel's answers against the host kernel, then its throughput:
./target/release/examples/f4_batch_bench --degree 23 --curve-a 1 --targets 1024 \
    --modes rayon,lockstep:cpu,lockstep:cuda --replay-cap 200000 --out /tmp/f4-gpu
# A complete DLP with relation batches decided on device 0:
./target/release/ca-ic run --degree 23 --curve-a 1 --solver groebner --batch 4096 --f4-backend cuda:0 --json
```

`CA_NVRTC_LIB` / `CA_CUDA_LIB` point at the libraries when they are not on
the loader path; `CA_F4_PTX` loads the PTX `build_kernel.sh` writes instead
of compiling with NVRTC; `CA_F4_THREADS` and `CA_F4_SCRATCH_MB` size the
launch. Every answer is still checked: the bench aborts on any decision
that differs from the host kernel's.

## 5. What this is not

- **Not a GPU measurement.** No device was available. The kernel compiles
  and the emulator agrees with the host kernel on every decision, cap,
  F5 row and lockstep search tested; device throughput is unknown until
  `f4_batch_bench --modes lockstep:cuda` runs on one.
- **Not an end-to-end calibrated speedup.** The records are `kind: "stage"`
  with every operation count, the total, `S` and the rho ratios `null`, as
  `AGENTS.md` requires when phases are unpriced. The wall ratios are
  same-host diagnostics of the PDP stage, which is essentially the whole
  run here.
- **Not a change in what the oracle can reach.** Decomposition rates,
  factor bases and relation yields are untouched; degree 23 remains a toy.
  Nothing here bears on ECC2K-130.

## 6. Next steps

- **Panel M4RI on the device** for single large matrices (the D ≥ 5 sweeps):
  a warp reduces a 32-column panel of `u32` words, then the whole block
  applies the recorded combinations; for very large trailing updates, GF(2)
  GEMM on binary tensor cores (AND + POPC, parity bit).
- **The whole search on the device**: one block per target with its stack
  in global memory, so the host no longer substitutes between rounds —
  the search's own bookkeeping (~20 µs a node on `K_1/2^23`: 1.20 s of wall
  against 1.10 s in the kernel over 4 934 nodes) bounds lockstep throughput
  today.
- **Reuse across nodes**: the degree-2 rows are a sub-matrix of degree 3, and
  a child system differs from its parent by one substitution.

## Files

- `run_paired.sh` — the paired end-to-end and stage-ladder runs.
- `records.py` — manifests, IDs, contract run records and `summary.json`.
- `runs.jsonl`, `summary.json`, `manifests/` — generated by `records.py`.
- `receipts/` — every raw report: `baseline-original/` (the original binary),
  `e2e/`, `e2e-batch/`, `stage/`, `degree/`, `batch/`, `dreg/`, `cuda/`.
