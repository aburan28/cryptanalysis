# Faster GPU large-matrix elimination (2026-10-07)

The device elimination of large Boolean Macaulay matrices
(`suite/cuda/f4_gf2_echelon.cuh`, on by default since #119) runs four
steps per 64-column panel: gather, a single-block panel step that finds the
pivots, materialise, and update. This record measures attempts to make it
faster against the merged #119 kernel (`4eb0194d`) and against each other.
Two changes were kept:

- **Tiled update.** Each block loads its pivots' words for a 32-word tile
  into shared memory, so pivots are read from there instead of global
  memory. Commit `21b4d779`.
- **Eager and lazy pivot search.** A panel whose candidates fit in shared
  memory (at most 1,920, two a thread) keeps the single-pass search: each
  column's pass eliminates it from every candidate and finds the next
  column's pivot. A larger panel is searched lazily. Its candidates are
  put in row order, then each column scans them one block-wide chunk at a
  time, bringing each candidate up to date with the pivots it has missed,
  until a chunk has the column. One pass at the end brings the rest up to
  date for the update. The pivots are the same lowest rows. Commits
  `b540e781`, `055a7267` to `f248f913`.

Every number is a stage diagnostic of one oracle matrix, not an ECDLP cost.

## Result: device time against #119 (ms, median of 3)

`pod_ab.sh` on one pod per device, old (#119) and new alternated:

| matrix | rows × words | RTX 4090 #119 | RTX 4090 new | speedup | H100 #119 | H100 new | speedup |
|---|---|---:|---:|---:|---:|---:|---:|
| `K_0/2^13` m=2 D=5 | 30,225 × 842 | 101.5 | 80.6 | 1.26× | 137.2 | 107.8 | 1.27× |
| `K_0/2^9` m=3 D=5 | 33,147 × 1,362 | 66.7 | 46.1 | 1.45× | 103.0 | 65.9 | 1.56× |
| `K_1/2^11` m=2 D=5 | 14,861 × 332 | 29.4 | 25.5 | 1.15× | 43.1 | 36.3 | 1.19× |
| `K_1/2^11` m=2 D=6 | 68,156 × 939 | 434.9 | 258.8 | 1.68× | 516.8 | 337.2 | 1.53× |
| `K_0/2^13` m=2 D=6 | 168,363 × 2,941 | 3,562.6 | 2,182.1 | 1.63× | 4,737.7 | 2,578.3 | 1.84× |

Receipts: `receipts/final-rtx4090`, `receipts/final-h100`. The H100
repeats agree within 1%. On the RTX 4090 they agree within 2% on the D=6
cells and within 11% on the D=5 cells, whose first repeat is sometimes the
slow one. Upload adds 2–1,900 ms, mostly host page-in, and is unchanged.

Per kernel (`F4_F2_ECHELON_PROFILE`, every launch synchronised), RTX 4090:

| step | #119, `K_0/2^13` D=6 | new | #119, `K_1/2^11` D=6 | new | #119, `K_0/2^9` m=3 | new |
|---|---:|---:|---:|---:|---:|---:|
| gather | 66 | 67 | 10 | 12 | 13 | 10 |
| panel | 1,406 | 810 | 265 | 163 | 37 | 34 |
| materialise | 119 | 105 | 35 | 37 | 18 | 16 |
| update | 2,141 | 1,300 | 133 | 79 | 36 | 14 |

The update is now the largest step on the big matrices.

## Setup

- Runpod pods rented and deleted by `cloud/runpod_pod.py`: one RTX 4090 or
  one H100 80GB HBM3. Each `host.json` names the GPU, driver and host CPU.
- Rust 1.99.0; kernels compiled by NVRTC 12 at start-up.
- `f4_matrix_bench`: one decomposition-system matrix, `F4_F2_ECHELON=cuda`.
  The device time is the elimination's own, from `F4_F2_ECHELON_VERBOSE`,
  after the process's one-time CUDA start-up.
- `pod_ab.sh` builds BASE (default #119) from GitHub beside the checkout,
  and runs each cell old then new, `REPS` times. `pod_variants.sh` builds
  copies of `f4_gf2_echelon.cuh` from `variants/` into one checkout and
  alternates them.

## How the panel step got there

Each row is an A/B on one RTX 4090 pod, unless noted, against the base its
receipts' `host.json` names: #119 up to the per-warp keys, the staged
panel (`b540e781`) after them, or the other variants of one pod. The same
base measured on different pods differs by up to 8%.

| attempt | commits | outcome |
|---|---|---|
| Merged-basis panel: per-chunk bases on the whole grid, merged pairwise | `81d4fddb`, reverted `7caa12d1` | 1.5–5.3× slower (H100) |
| Stage the panel's candidates in shared memory, up to 1,920 | `b540e781` | panel 1,489 → 1,490 ms on `K_0/2^13` D=6: no change |
| Reduce the next pivot's key per warp, not one shared minimum | `17795b35`, reverted `59bcdf10` | panel 1,510 → 1,639 ms; D=5 cells 0.75–0.90× |
| Build pivots and expand histories in shared memory | `5f822f41`, reverted `37e030c4` | panel 1,395 → 1,386 ms: no change |
| Track each candidate's sum over original pivot rows | `ffa9ae5d`, reverted `049a359d` | panel 1,491 → 1,844 ms |
| Lazy search, every panel put in row order | `055a7267` | D=6 1.31–1.49×, `K_0/2^9` m=3 0.64× |
| Order only panels of several chunks | `d579606b` | m=3 0.84× |
| Stage one-chunk panels, no barrier per pivot | `e72ac17f` | no change |
| Scan up to 2 chunks as one; expand histories with a shared atomic XOR per earlier pivot | `f5efbb8d` | m=3 0.80×; against the serial expansion on another pod, an estimated 500 cycles a round |
| Expand histories serially in shared memory | `5c4822ca` | m=3 0.85× |
| Stage up to 1,920 candidates | `bcc47b28` | m=3 0.86× |
| Eager search below 1,920 candidates, lazy above | `f248f913` | 1.02–1.50× on every cell |

Two measurements turned the search:

- **Cycle counts** (`variants/clock.cuh`, `panel_clock.py`, receipts in
  `receipts/panel-clock`). Thread 0 of the panel block timed each phase.
  On `K_0/2^13` D=6, 2,203 of 2,941 panels have more than 4,096 candidates
  (median 12,285, max 55,940), and they spent 94% of their cycles in the
  per-column rounds, at about 1.5 cycles per candidate per round. The
  history expansion was 4.7%. So the earlier attempts, which targeted
  atomics, staging and expansion, could not help; reading fewer candidates
  per round could.
- **A diagnostic that changes the answer misleads.** Skipping the history
  expansion (`receipts/shared-hist`, variant `noexpand`) cut the panel by
  a third, but its rank was 168,363 instead of 130,583. The wrong pivot
  rows changed every later panel's work. Diagnostics after that kept the
  answer.

The lazy search lost on small panels for a reason not found. On
`K_0/2^9` m=3, the lazy panel kernel took 40–48 ms against 32–36 ms.
Neither row ordering, staging, the barrier per pivot, nor registers (40
against 30, no spills) accounted for it. The eager search for small
panels removes the loss rather than explaining it. The lazy search's
cycle counts are in `receipts/lazy-clock` (`variants/clock-lazy.cuh`,
instrumenting the kernel of `e72ac17f`).

`receipts/lazy-staged-blackwell-noisy` is an RTX PRO 6000 Blackwell pod
whose repeats varied up to 3×. Its gather took 10× the RTX 4090's, so it
supports no ratio.

## Correctness

- **Same elimination.** Old and new give the same rank, refutation,
  pinned variables, pivot count and word-XOR count on every matrix and
  repeat (`receipts/*/matrix-*.json`, `walls.txt`). The word count fixes
  which rows were pivots, so both searches pick the same lowest rows.
- **Cross-path assertions.** `f4_degree_bench --max-degree 5` with the
  device on asserts that its dense, sparse, fast and fast + F5 paths agree
  (`degree-new.log`).
- **Same sweep tables.** `dreg_sweep`'s solving-degree and first-fall-degree
  tables are the host's (`walls.txt`).
- **Emulator tests.** The emulated kernels, the same source compiled as C,
  match Gaussian elimination on 84 random cases. Each case runs with 1, 7,
  64 and 1,024 emulated threads, which send its panels down the lazy or
  the eager search and gather candidates out of row order. The word counts
  must agree across thread counts. The test fails when the lazy search
  takes its pivot by position in gather order, or skips row ordering.

## Reproduce

```sh
cloud/runpod_pod.py run panel --gpu "NVIDIA GeForce RTX 4090" \
  --out experiments/f4-gpu-panel-20261007/receipts/rerun -- \
  'bash experiments/f4-gpu-panel-20261007/pod_ab.sh experiments/f4-gpu-panel-20261007/receipts/rerun'
```

`BASE=<commit>` compares against another commit, `REPS` sets the repeats
and `PROFILE_CELLS` the profiled cells. A run takes about 15 minutes, most
of it two release builds: about $0.20 on an RTX 4090 at $0.74/hr, $0.90
on an H100 at $3.49/hr. The panel work here used about 20 such pods.
