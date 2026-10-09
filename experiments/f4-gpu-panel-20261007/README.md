# Two changes to the GPU large-matrix elimination (2026-10-07)

The device elimination of large Boolean Macaulay matrices
(`suite/cuda/f4_gf2_echelon.cuh`, on by default since #119) runs four
steps per 64-column panel: gather, a single-block panel step that finds the
pivots, materialise, and update. This record measures two attempts to make it
faster, each against the merged #119 kernel (`4eb0194d`) on the same device.
`pod_ab.sh` is the exact script.

- **Merged-basis panel step: reverted, 1.5–5.3× slower.** Each panel's
  pivots were found across the whole grid: per-chunk bases, then pairwise
  merges in one block. Commits `81d4fddb`, reverted in `7caa12d1`.
- **Tiled update: kept, 1.11–1.49× faster.** Each block loads its pivots'
  words for a 32-word tile into shared memory, so pivots are read from there
  instead of global memory. Commit `21b4d779`.

Every number is a stage diagnostic of one oracle matrix, not an ECDLP cost.

## Setup

- Runpod pods with one NVIDIA H100 80GB HBM3 (driver 580.126.09, Xeon
  Platinum 8470 host), rented and deleted by `cloud/runpod_pod.py`. The two
  runs used two pods of the same type.
- Rust 1.99.0; kernels compiled by NVRTC 12 at start-up.
- `f4_matrix_bench`: one decomposition-system matrix, `F4_F2_ECHELON=cuda`.
  The device time is the elimination's own, from `F4_F2_ECHELON_VERBOSE`,
  after the process's one-time CUDA start-up. Each cell ran old, then new,
  three times; the medians are below, and the repeats agree within 1%.

## Device time (ms, median of 3)

| matrix | rows × words | old (#119) | tiled update | speedup | merged-basis panel (reverted) |
|---|---|---:|---:|---:|---:|
| `K_0/2^13` m=2 D=5 | 30,225 × 842 | 137.5 | 107.4 | 1.28× | 611.7 (4.4× slower) |
| `K_0/2^9` m=3 D=5 | 33,147 × 1,362 | 103.2 | 69.4 | 1.49× | 294.1 (2.9× slower) |
| `K_1/2^11` m=2 D=5 | 14,861 × 332 | 43.1 | 38.8 | 1.11× | 227.9 (5.3× slower) |
| `K_1/2^11` m=2 D=6 | 68,156 × 939 | 524.1 | 456.5 | 1.15× | 1,416.3 (2.7× slower) |
| `K_0/2^13` m=2 D=6 | 168,363 × 2,941 | 4,780.8 | 3,585.7 | 1.33× | 7,170.7 (1.5× slower) |

The old column is from the tiled-update run. The merged-basis slowdowns are
against the old kernel in its own run, whose times were within 0.5% of these.

Upload adds 4–700 ms and is unchanged.

## Correctness

- **Same answers.** Old and new give the same rank, refutation and pinned
  variables on every matrix and repeat (`receipts/*/matrix-*.json`). The
  tiled update also gives the same pivots and word counts, since only where
  pivot words are read from changed.
- **Cross-path assertions.** `f4_degree_bench --max-degree 5` with the
  device on asserts that its dense, sparse, fast and fast + F5 paths agree
  (`degree-new.log`).
- **Same sweep tables.** `dreg_sweep`'s solving-degree and first-fall-degree
  tables are the host's with both changes (`walls.txt`).
- **Emulator tests.** The emulated kernels, the same source compiled as C,
  match Gaussian elimination on 54 random cases in the unit tests. For the
  merged-basis panel these also forced 1- and 3-row chunks.

## Where the time goes

`F4_F2_ECHELON_PROFILE` synchronises every launch (`receipts/*/profile-*.log`):

| step | old, `K_0/2^13` D=6 | merged-basis | tiled update | old, `K_1/2^11` D=6 | tiled update |
|---|---:|---:|---:|---:|---:|
| gather (local, merged-basis) | 40 | 290 | 39 | 9 | 9 |
| panel (merge, merged-basis) | 1,916 | 3,877 | 1,916 | 314 | 312 |
| materialise | 136 | 253 | 136 | 51 | 46 |
| update | 2,766 | 2,844 | 1,566 | 174 | 107 |

- **The update was the biggest step,** not the panel. A warp per remaining
  row read about half of up to 64 pivot rows from global memory for every
  word. Tiling cut it 1.6–1.8×.
- **The merged-basis panel lost** because each merge rebuilds a 64-word
  echelon in thread-local memory, about 4,000 merges in 12 rounds per panel.
  That cost twice the single-block panel it replaced. Its local step was also
  7× the plain gather, and its reduced-echelon pivots made materialise
  denser.
- **The single-block panel step is now the largest cost** on the biggest
  matrix (1.9 of 3.6 s). It is the next target. Its candidates' words leave
  shared memory past 2,048 rows, and the merged-basis result shows that
  replacing it needs a cheaper merge than one thread per pair.

## Reproduce

```sh
cloud/runpod_pod.py run panel --out experiments/f4-gpu-panel-20261007/receipts/rerun -- \
  'bash experiments/f4-gpu-panel-20261007/pod_ab.sh experiments/f4-gpu-panel-20261007/receipts/rerun'
```

`BASE=<commit>` in the environment compares against another commit. The
run took about 8.5 minutes on an H100 pod at $3.49/hr.
