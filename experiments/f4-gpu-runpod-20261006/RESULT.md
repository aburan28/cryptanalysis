# F4 on a real GPU: an RTX 5090 on Runpod (2026-10-06)

**Result: the degree-6 Macaulay matrices are built and eliminated 25 to 75
times faster with the GPU, with the host's ranks, refutations and pinned
variables; the batched per-node path is correct on the device but no
faster than the host's default engine.** The new large-matrix elimination
(`F4_F2_ECHELON=cuda`, `suite/cuda/f4_gf2_echelon.cuh`) turns the
`K_0/2^13` degree-6 matrix (168,363 × 188,203) from 426 s on the pod's Xeon
into 5.7 s, and the solving-degree sweep (`dreg_sweep`, default arguments)
from 18.8 s into 8.2 s, with an identical table. The batched decider of
September decides correctly on the device: every mode and every replayed
decision agrees with the host kernel, and complete DLPs recover the same
verified logarithm. But it decides about as fast as 13 host threads, and
the inherited engine the suite now uses by default is 4.4 times faster on
the host than the device path.

Every number here is a stage diagnostic: one oracle matrix, one sweep, or
the decomposition oracle on a fixed target set. No IC candidate is compared
end to end, so no candidate or run IDs are assigned (`AGENTS.md`).

## Hardware and method

One Runpod secure-cloud pod: an **NVIDIA GeForce RTX 5090** (sm_120,
32 GB, driver 580.126.09), on an **Intel Xeon Gold 6530** host whose cgroup
gives the pod 13.6 CPUs (`cpu.max 1360000 100000`; rayon ran 13 threads),
`runpod/base:1.0.2-ubuntu2404`, Rust 1.99.0, NVRTC 12 from NVIDIA's pip
wheel. The kernels were compiled by NVRTC to SASS for sm_120. The host and
device runs share the binary, built at `00036803` with the
`gpu-emulator` feature; the host runs came first, with the device idle.
`pod_matrix.sh` is the exact script, `receipts/host.json` the hardware,
`receipts/walls.txt` every process wall.

The pod was rented and driven with what is now `cloud/runpod_pod.py`
(then `experiments/f4-gpu-20260925/runpod_bench.py`), which hands the pod
an SSH key through its `PUBLIC_KEY` variable and caps its lifetime; it was
deleted afterwards.

## Large matrices

`f4_matrix_bench`: the decomposition system's Macaulay matrix at one
degree, built and decided once, F5 requested. On the device path the build
skips F5's symbolic half (it costs more host time than the rows it drops
save there), so more rows are eliminated; the answer cannot change, since
F5 only drops rows in the span of the others.

| matrix | rows × cols | host build + eliminate | device build + eliminate | speedup |
|---|---|---:|---:|---:|
| `K_0/2^13` m=2 D=6 | 168,363 × 188,203 | 6.34 + 419.46 = **425.8 s** | 1.39 + 4.31 = **5.70 s** | **74.7×** |
| `K_1/2^11` m=2 D=6 | 68,156 × 60,040 | 1.13 + 25.63 = 26.75 s | 0.26 + 0.79 = 1.05 s | 25.5× |
| `K_0/2^13` m=2 D=5 | 30,225 × 53,871 | 0.13 + 4.16 = 4.29 s | 0.11 + 0.41 = 0.52 s | 8.3× |
| `K_0/2^9` m=3 D=5 | 33,147 × 87,118 | 0.15 + 0.96 = 1.11 s | 0.15 + 0.34 = 0.48 s | 2.3× |
| `K_1/2^11` m=2 D=5 | 14,861 × 21,196 | 0.03 + 0.32 = 0.36 s | 0.03 + 0.26 = 0.29 s | 1.3× |

The device column includes each process's one-time CUDA start-up and NVRTC
compile, about 0.25 s, in its first elimination: on the small matrices it
is most of the time. Without it (`F4_F2_ECHELON_VERBOSE`, same pod) the
`K_0/2^13` D=5 matrix spends 22 ms uploading and 104 ms on the device
against 4.16 s on the host, and the D=6 one 0.6 s uploading and 3.5 s on the
device against 419 s. Ranks, refutations and pinned variables are the
host's in every row; the word counts differ because the pivots do.

## Every path asserted

`f4_degree_bench --max-degree 5` asserts, cell by cell, that the dense
reference, the sparse reference, the fast kernel and the fast kernel with
F5 agree on rank, refutation and pinned variables. With
`F4_F2_ECHELON=cuda` the fast paths of the large cells run on the device;
both runs print "All paths agree" (`receipts/degree-host.log`,
`receipts/degree-gpu.log`). In one process, with the start-up paid once,
the fast kernel with F5 takes 4.18, 1.13 and 0.35 s on the host on the
three largest cells (`K_0/2^13` m=2, `K_0/2^9` m=3 and `K_1/2^11` m=2, all
D=5) and 0.24, 0.27 and 0.06 s with the device.

## The solving-degree sweep

`dreg_sweep`, default arguments, 8 trials per cell: **18.8 s on the host,
8.2 s with the device**, and the solving-degree and first-fall-degree
tables are identical (`receipts/dreg-*.log`). The time moves where the
matrices are large:

| cell | host | device |
|---|---:|---:|
| `n=11 ℓ=10 m=2` (20 vars) | 8.8 s | 2.0 s |
| `n=17 ℓ=8 m=2` (16 vars) | 3.9 s | 0.9 s |
| `n=13 ℓ=12 m=2` (24 vars) | 1.8 s | 0.9 s |
| the other 13 cells | 4.4 s | 4.3 s |

The offload threshold, 1 Mi words (8 MiB), was set from this sweep: at
4 Mi words it took 13.3 s, at 1 Mi 8.8 s, at 256 Ki 8.6 s. Below it a
matrix stays on the host, where many small ones run in parallel on the
cores instead of in turn on one device.

## The per-node path

`f4_batch_bench` on `K_1/2^23`, 1,024 targets, 13 threads.  Lockstep
implements the from-scratch engine, so these runs set `KIC_F4_INHERIT=0`;
the last row is the default inherited engine (`receipts/batch-*`).

| mode | wall | F4 decisions |
|---|---:|---:|
| from-scratch, searches across the cores | 6.64 s | 763,444 |
| from-scratch, lockstep, host decider | 8.47 s | 764,236 |
| from-scratch, lockstep, **RTX 5090 decider** | **5.57 s** | 764,236 |
| **inherited engine (default), across the cores** | **1.25 s** | 764,698 |

All from-scratch modes reach the same verdict digest and 382,119
reductions. Replaying 200,000 recorded decisions: 9,029 per second on one
host thread, 114,584 on 13, **127,356 on the RTX 5090**, every one checked
against the host kernel.

Why the device is not faster here: the matrices are small (half of them
23 rows by about 144 columns, the other half about 400 by 500 to 1,460
columns), and every decision ships its whole system, about 690 terms,
from the host. Packed on one thread, a batch was no faster to prepare than
to decide: one thread of the 4-vCPU VM packs 166 thousand systems a second,
and the pod's replay, packed that way, reached 108 thousand. So
`PackedBatch::pack` now packs on every core, which took the lockstep run
from 7.34 to 5.57 s and the replay from 108 to 127 thousand decisions a
second. Beyond that, the inherited engine spends about a fifth of the time
per node by specialising its parent's basis, and a GPU would need the whole
search, its state included, on the device to compete.

The first hardware run (`receipts/first-run-matrixf4/`, before parallel
packing) also ran complete `K_1/2^23` DLPs through `ca-ic run
--f4-backend cuda`: at batch 64 and 1,024 the device recovered the same
verified logarithm with the same 1,024 trials, 407 relations and 378,367
reductions as the cores. Its one failing check is the frozen stage ladder,
whose digests predate the base branch's changes to the search.

## Context: the oracle at the sizes `ca-ic run` reaches

On this cloud VM (4 vCPU), a complete `K_1/2^23` DLP took 0.28 s with the
Gröbner oracle, 0.06 s by enumeration, 0.07 s with the pair table and
0.05 s with `mq-fes`; three summands on `K_0/2^23` took 0.78, 0.13 and
0.09 s with the first three. At the sizes the toy pipeline reaches, F4 is
not the fastest oracle. Its matrices become the bottleneck only in the
higher-degree studies above, which is where the device pays.

## What this is not

- **Not an ECDLP speedup.** No IC candidate is timed end to end; the
  matrices and sweeps are stage diagnostics.
- **Not a tuned kernel.** The panel step, one block per 64 columns, is
  still most of the device time (300 of 460 ms on `K_1/2^11` D=6 under
  `F4_F2_ECHELON_PROFILE`), and the host build is now as long as the
  device elimination on the largest matrix.
- **Not one GPU's verdict on others.** One RTX 5090; nothing here was run
  on another device.

## Reproduce

```sh
cloud/runpod_pod.py run f4 --gpu "NVIDIA GeForce RTX 5090" \
    --out experiments/f4-gpu-runpod-20261006/rerun -- \
    'bash experiments/f4-gpu-runpod-20261006/pod_matrix.sh experiments/f4-gpu-runpod-20261006/rerun'
```

The run takes about 25 minutes, seven of them the host's D=6 `K_0/2^13`
matrix (`SKIP_HOST_D6=1` leaves it out).

## Files

- `pod_matrix.sh` — every measurement above, on the pod.
- `receipts/` — `host.json`, `walls.txt`, and per measurement its JSON and
  log: `degree-{host,gpu}`, `matrix-<cell>-{host,gpu}`, `dreg-{host,gpu}`,
  `batch-{matrixf4,default}`; `first-run-matrixf4/` is the first hardware
  run of `../f4-gpu-20260925/gpu_bench.py`.
