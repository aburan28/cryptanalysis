# PDP oracle speedup: the cryptanalysis-side tasks

**Status.** Plan; nothing here has run.  **Class.** Accounting (a plan moves no
operation count).  The program, its boundary, its other seven tasks and their
frozen protocols live in the `crypto` repository:
[`research/pdp_oracle_speedup_20261011/PLAN.md`](https://github.com/aburan28/crypto/blob/main/research/pdp_oracle_speedup_20261011/PLAN.md).
This directory holds only the two tasks whose code lands here, so that the
plan is not duplicated and cannot drift.

## Why this repository

The C/CUDA core, the cloud runners (`cloud/`), the isolated-benchmark service
(`scripts/isolated_bench.py`, [docs/ISOLATED_BENCHMARKS.md](../../docs/ISOLATED_BENCHMARKS.md))
and the suite's own copy of the oracle live here:
`suite/src/cryptanalysis/semaev_decomp.rs` (pairs-and-solve, diverged from the
`crypto` copy by about 1,500 diff lines), `suite/src/cryptanalysis/fes_gpu.rs`
(byte-identical to `crypto`'s today) and `suite/src/cryptanalysis/mq_fes.rs`.
The existing scaling experiment [`../pdp-scaling`](../pdp-scaling/README.md)
measures the same problem with off-the-shelf solvers and is the context for
this work, not part of it.

## Boundary (copied, not restated)

Reference: pairs-and-solve, one-word field, `gcd(q, L_V mod q)`.  Floor: any
enumerating oracle leaves relation collection `Θ(2^n)` independent of the
factor-base dimension `ℓ`, so these tasks are constant-factor work and cannot
move ECC2K-130's ratio.  Unit: counted bit operations per pair, with pairs per
second as the practicality note.  Expected class for both tasks: engineering.

## Task PS-3b: port the CPU kernel into the suite

Needs the `crypto` PS-3 kernel merged.  Paired PR.

- **Hypothesis.**  The kernel ports to `suite/src/cryptanalysis/` with the
  PS-0 corpus digests unchanged, although the two oracle modules diverged.
- **Frozen inputs.**  PS-3's merged commit; PS-0's corpus and digests (the
  corpus is data and is copied byte-for-byte with its hash); the suite's tests
  (`cargo test --release`, about 10 minutes on four cores) and its CI.
- **Success.**  Digests reproduce from the port; the suite's tests and CI are
  green; per-core pairs per second within the A/A spread of `crypto`'s PS-3
  figure on the same host class.
- **Stop.**  A faithful port needs the other module refactored first: stop,
  report the minimal refactor as its own task, do not fork the algorithm.
- **Wall-time numbers.**  A CPU wall-time speedup is promoted only with a
  receipt from the isolated-benchmark service (see
  [AGENTS.md](../../AGENTS.md), "CPU performance isolation gate").  The
  shared containers used for development cannot give one, so the port reports
  digests and counted operations as its evidence and labels any wall figure
  exploratory; it claims no speedup of its own.

## Task PS-5: GPU kernel

Needs PS-3 and an owner-approved allocation.

- **Hypothesis.**  PS-3's straight-line program (XOR, AND, ternary logic as a
  hashed list of operations) executes on a CUDA device with logic mapped to
  `lop3`, one pair per lane and the Gray position per warp, at least 50× the
  single-core pairs per second of PS-3.  The expected ratio is the device's
  32-bit logic throughput over one core's 512-bit logic throughput, filled
  from the datasheet and a microbenchmark at the start of the task.
- **Layout.**  Follow the existing pattern in `suite/cuda/`
  (`f4_gf2_kernel.cu`, `f4_gf2_device.cuh`, `f4_gf2_emulate.c`,
  `build_kernel.sh`): a device kernel plus a CPU emulation of it, so digest
  parity is checkable on a CPU-only host and in CI without a device.  The
  Rust bridge extends `fes_gpu.rs`; that file is byte-identical in both
  repositories, so a change lands here first and is mirrored in `crypto` in a
  paired PR.
- **Frozen inputs.**  PS-3's program (hash), the PS-0 corpus and digests,
  `ℓ` from 11 to 15 (16 if time allows), and the device's `gpu` block.
- **Gate before any timing.**  The whole corpus is replayed on the device with
  identical digests; the CPU emulation passes first.
- **Hosts and rules.**  Run through `cloud/runpod_pod.py`,
  `cloud/cairn_queue.py` or `cloud/modal_run.py --image cuda` as
  [AGENTS.md](../../AGENTS.md) ("Run index calculus on a GPU") describes;
  keep each report's `gpu` block (an empty `gpu.devices` is labelled a
  CPU-only measurement); delete or stop every pod started; write no
  credentials into the tree.
- **Spend.**  This plan authorises none.  A launch needs the owner's explicit
  approval and a cap (planning cap 8 GPU-hours); nothing is started by
  merging this directory.
- **Unit.**  Pairs per second per device, counted bit operations per pair, an
  A/A run on the device, ABAB against PS-3 on one core of the same host, with
  the number of contended runs reported.
- **Success.**  ≥ 50× PS-3 on one core, digests identical.  **Stop.**  Below
  20×.
- **Hardware classes.**  A result holds for the device measured.  Metal
  (`gpu/fes/fes.metal` in `crypto`), Arm64 and FPGA are named, not implied.

## Status of requirements

| item | status |
|:--|:--|
| Scope the cryptanalysis-side tasks with frozen protocols | **verified complete** by this PR |
| PS-3b, PS-5 | **not attempted** |
| Any speedup claim | **none made** |

## Graphs checked

No canonical graph or table in this repository carries a number that this plan
changes; none was edited.
