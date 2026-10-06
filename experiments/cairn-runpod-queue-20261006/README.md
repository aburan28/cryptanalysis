# The cairn job queue on a Runpod GPU runner (2026-10-06)

An end-to-end run of `cloud/cairn_queue.py`: one Runpod GPU pod made into a
cairn runner, seven jobs submitted from a cloud-agent VM, run one at a time
by cairn's host agent, and brought back with their receipts. It checks the
tooling, not an index-calculus (IC) method. Every number below is a stage
diagnostic or a wall time of the queue itself; no IC candidate is named or
compared.

## Setup

- **Runner.** `cloud/cairn_queue.py up cairn-runner-1` made one pod: an RTX
  5090 (driver 570.195.03), 32 vCPUs of an AMD EPYC 9354, 124 GB, image
  `runpod/base:1.0.2-ubuntu2404`, at $0.99/hr. The pod was up for about 55
  minutes and was deleted afterwards.
- **cairn.** Release 1.17.0 (musl, sha256-checked) ran
  `cairn agent run --sandbox none --parallel 1`. It registered with a private
  `cairn run` node on the pod's loopback.
- **Jobs.** Each job ran unconfined on the pod and asked for `gpus: 0` (see
  *Caveats*). Every job saw the pod's GPU, as its `status.json` shows; the
  matrix, sweep and degree jobs used it.
- **Shipping.** The first three jobs ran on commit `b7a2f0ea`, which shipped
  a 288 MB tarball per tree. The later ones ran on the `cloud/ship.py` and
  `cloud/install_tree.py` that this run led to. Each job's `job.json` names its
  commit (`JOB_COMMIT`) and tree (`JOB_TREE`).

## Jobs

Times are the receipts' (`receipts/<job>/receipt.json`). No two jobs overlap:
each started after the one before it finished.

| job | ran | wall | exit | build | result |
|---|---|---:|---:|---:|---|
| `ic-k1-n23` | 21:14:45–21:16:16 | 91.3 s | 0 | 50.0 s (cold) | `ca-ic run --degree 23 --curve-a 1`: complete, recovered 53 = expected, verified. `gpu.devices` lists the RTX 5090; no matrix was large enough to offload |
| `matrix-k1n11d6-gpu` | 21:16:17–21:17:07 | 49.9 s | 0 | 45.1 s | `K_1/2^11` m=2 D=6 (68,156 × 60,040) on the device by default: eliminate 0.453 s, build + eliminate 1.75 s; rank 46,747, not refuted, nothing pinned |
| `matrix-k1n11d6-host` | 21:17:07–21:18:16 | 69.5 s | 0 | 45.1 s | the same matrix with `F4_F2_ECHELON=host`: eliminate 20.6 s, total 21.4 s; the same rank, refutation and pins |
| `dreg-sweep-auto` | 21:35:52–21:36:02 | 10.0 s | 0 | 0.47 s | `dreg_sweep` with no flags: its 14,861 × 332-word matrices went to the device (about 32 ms each) |
| `degree-bench-auto` | 21:36:03–21:39:22 | 198.6 s | 0 | 0.04 s | `f4_degree_bench --max-degree 5` with the device on by default: wherever its dense, sparse, fast and fast + F5 paths ran, they agreed on rank, refutation and pins (the bench asserts it) |
| `ic-k1-n23-again` | 21:50:45–21:50:49 | 3.9 s | 0 | 0.76 s | the first job again, on a newer commit: verified |
| `ic-k1-n25` | 21:52:06–21:52:09 | 2.7 s | 1 | 0.04 s | refused by `ca-ic`: the default factor base at degree 25 has dimension 20, over its materialization limit of 13. Kept as the failure row: the receipt, `wait` and `fetch` all report exit 1 |

The node's roster at the end (`receipts/node-hosts.json`) listed the runner
as live, with `completed: 6, failed: 1, capacity: 1`.

## What the run changed

- **Shipping.** Uploading the 288 MB checkout from the VM took 366 s (about
  0.8 MB/s). `cloud/ship.py` now has the pod fetch the checkout's newest
  commit that GitHub has, and sends only the changed files.
  - A cold shallow fetch on the pod took 37 s once and 110 s an hour later;
    the first submit shipped this way took 134 s.
  - The next submit, from a newer commit, took 241 s: the cache kept no ref,
    so the fetch offered GitHub nothing and got the whole tree again. With
    the previous commit kept as a ref, the same kind of fetch took 1.0 s.
  - Pods now start that fetch at boot. With the ref, a submit from a new
    commit took 8.9 s, and a submit of a tree already on the runner took 5 s.
  - A one-off `cloud/runpod_pod.py run` on a fresh 8-vCPU CPU pod took 153 s
    in all: create, fetch, ship, install, toolchain, command and delete. Its
    command, a diagnostic, exited 128 on a `git log` in the bare cache; the
    steps around it worked.
- **Warm builds.** Every early job rebuilt the suite for about 45 s. Each job
  had unpacked a fresh checkout, and `cryptanalysis-sys`'s build script
  watches the `src/` and `include/` directories, which the fresh copy made
  new. `cloud/install_tree.py` now rewrites only files whose content
  differs, so later builds took 0.04–0.8 s.

## Caveats

- **`gpus: 0`.** A Runpod pod is a container with no engine or KVM inside.
  cairn 1.17.0 hands a GPU only to a job a container engine runs, and refuses
  an unconfined GPU job. Each spec therefore says `gpus: 0`, with a `note`
  saying why. The receipts say `sandbox: none` and list
  `isolation: unconfined run on the host` under `unenforced`.
- **The roster over-reports.** cairn's probe reads the host's PCI bus and
  memory, so the roster shows three GPUs (two RTX 5090s and the host's VGA
  device) and 257 GB for a pod that rented one GPU and 124 GB. `nvidia-smi`
  in the pod, the jobs' `status.json` (`RUNPOD_CPU_COUNT`, `RUNPOD_MEM_GB`)
  and the IC reports' `gpu` block are what the jobs actually had.
- **Hardware differs from the earlier experiment.** These matrix times come
  from a different machine than
  [`../f4-gpu-runpod-20261006`](../f4-gpu-runpod-20261006/RESULT.md)
  (EPYC 9354 here, Xeon Gold 6530 there). Compare within one experiment only.

## Files

- `outputs/` holds what the jobs wrote and `fetch` merged back: the `ca-ic`
  reports, the matrix and degree benches' JSON, and the sweep's table.
- `receipts/<job>/` holds what `fetch --into` kept:
  - `receipt.json` and `job.json` (the cairn receipt and spec);
  - `stdout` and `stderr`;
  - `out/log.txt`, `out/status.json` and `out/outputs.txt`, from
    `cloud/job_runner.sh`.
- `receipts/hosts.txt`, `receipts/jobs.txt` and `receipts/node-hosts.json`
  are the roster and queue at the end, and `receipts/runner-logs.txt` is the
  agent's and the boot script's log.

## Reproduce

Needs `RUNPOD_API_KEY`. From the repository:

```sh
Q=cloud/cairn_queue.py OUT=experiments/cairn-runpod-queue-20261006/outputs
$Q up cairn-runner-1 --gpu "NVIDIA GeForce RTX 5090"
$Q submit cairn-runner-1 --id ic-k1-n23 --out $OUT/ic-k1-n23.json -- \
  "mkdir -p $OUT && cd suite && cargo build --release --locked --bin ca-ic --example f4_matrix_bench && \
   ./target/release/ca-ic run --degree 23 --curve-a 1 --out ../$OUT/ic-k1-n23.json"
$Q submit cairn-runner-1 --id matrix-k1n11d6-gpu --out $OUT/matrix-k1n11d6-gpu.json -- \
  "mkdir -p $OUT && cd suite && cargo build --release --locked --example f4_matrix_bench && \
   ./target/release/examples/f4_matrix_bench --cell 1:11:2:301 --degree 6 --out ../$OUT/matrix-k1n11d6-gpu.json"
$Q jobs cairn-runner-1
$Q wait cairn-runner-1 ic-k1-n23 matrix-k1n11d6-gpu
$Q fetch cairn-runner-1 ic-k1-n23 matrix-k1n11d6-gpu --into experiments/cairn-runpod-queue-20261006/receipts
$Q down cairn-runner-1
```

The other jobs' commands are in their `receipts/<job>/job.json` (`env.JOB_CMD`).
