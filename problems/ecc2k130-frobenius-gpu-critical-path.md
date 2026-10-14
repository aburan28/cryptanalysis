# ECC2K-130 Frobenius GPU critical path is not localized

- **Status:** `investigating`
- **Kind:** empirical bottleneck; missing instruction-level attribution
- **Affected work:** [production-compatible GPU optimization report](../ecc2k130/runner/research/kernelagent-20261013/README.md), [production runner](../ecc2k130/runner/README.md)
- **Next action owner:** ECC2K-130 GPU engineering
- **Last updated:** 2026-10-14

## Problem

The current measurements do not identify a source change that improves production-compatible ECC2K-130 Frobenius-walk throughput: the isolated profiler reports aggregate compute and stall activity, while the bounded arithmetic and barrier changes tested so far are flat or slower. The source instruction or dependency chain responsible for the remaining issue stalls has not been localized.

The affected workload is the `certicom-ecc2k130-frobenius-v1` walk at pinned source `1f8e6847de9e207880bd3be63835c3f56eb182d5`: curve 131, batch 16, 120,320 workers, 640-thread blocks, four-warp grouped inversion, run ID 11000 and DP32. A production improvement must preserve the sorted DP corpus, zero-drop behavior, arithmetic, and fresh/checkpoint/resume state, then beat a same-allocation paired baseline beyond A/A noise. A local instruction-count or profiler change alone does not meet that requirement.

## Evidence and uncertainty

- **Observed:** The [isolated 64-step profile](../ecc2k130/runner/research/kernelagent-20261013/production-compute-profile-isolated.json) and [raw-counter profile](../ecc2k130/runner/research/kernelagent-20261013/production-stall-profile.json) used CUDA 13.3, driver 610.57.04 and one RTX PRO 6000 Blackwell Server Edition. They reported 89.57% SM compute throughput, 41.11% achieved occupancy, 96 registers/thread, zero local spilling requests and 16 barrier slots. Raw stalled-warps-per-active-issue-cycle ratios were 1.645498 for barriers and 1.618835 for math-pipe throttle. All 22 application-replay passes had fresh DP files and matching output. `SourceCounters` did not provide a usable printed per-instruction stall breakdown.
- **Observed:** Frozen paired screens against the pinned source retained the 355-record sorted DP32 SHA-256 `c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90` with zero drops. [Full top CLMAD](../ecc2k130/runner/research/kernelagent-20261013/top-clmad-screen.json) had median paired ratio 0.839956; [half-top CLMAD](../ecc2k130/runner/research/kernelagent-20261013/top-half-clmad-screen.json) 0.930688; [zip-based normal square](../ecc2k130/runner/research/kernelagent-20261013/zip-square-screen.json) 0.997502; [static 640-thread barriers](../ecc2k130/runner/research/kernelagent-20261013/static-barrier-screen.json) 0.992947 and static 128-thread geometry 0.856411. [Root-only barrier removal](../ecc2k130/runner/research/kernelagent-20261013/root-barrier-screen.json) was inside its A/A spread. These are two-pair screens, not five-pair confirmation results. Host field and walk checks passed for the new half-top and zip-square arithmetic switches.
- **Derived or proved:** The listed variants did not satisfy their predeclared advancement gate under this exact workload. No hardware lower bound or universal limit follows from the screens.
- **Suspected explanation:** Math-pipe pressure, inverse barriers and dependency latency may interact; the aggregate counters cannot determine which source sequence dominates. The `FP64` pipeline label alone does not map carryless SASS instructions to a physical execution unit.
- **Missing capability:** A retained, source-correlated PC/SASS stall profile of the pinned walk with enough attribution to select a specific source-level dependency or instruction reduction.
- **What this evidence does not establish:** It does not rule out other source changes, another launch geometry, a different compiler or GPU, or a useful speedup. It does not establish an end-to-end cloud or ECDLP attack-cost advantage. The direct KernelAgent integration gap is tracked separately in [the CUDA bridge problem](ecc2k130-kernelagent-cuda-bridge.md).

## What would unblock it

- [ ] Retain a source-correlated PC/SASS profile for the pinned production walk with the executable and report hashes, profiler command, all application-replay pass outputs, and an instruction-level stall or issue attribution that names the dominant sequence. Each replay pass must use a fresh DP file and preserve the expected profile output with zero drops.
- [ ] Implement a default-off source change targeted at that sequence; pass independent host arithmetic, GPU DP32 corpus and fresh/checkpoint/resume checks, then exceed the A/A range in both 64-launch screening pairs and improve all five warmed 128-launch confirmation pairs against the pinned production build.

The first condition makes the next optimization choice reviewable; it is not a speed result. The second would establish a same-GPU useful-update improvement for the frozen walk. Cloud cost, other GPUs, long-run DP collection, and any ECDLP attack-cost claim would still need separate accounting.

## Next discriminating step

- **Action or proof obligation:** Reprofile the unchanged pinned walk with source/SASS correlation and per-PC issue-stall sampling. Archive the native report and the imported instruction table, then identify one source-level sequence to change. If the profiler cannot supply those samples, record that limit and use compiler SASS plus a bounded, correctness-checked microbenchmark of the candidate sequence before another full-walk screen.
- **Inputs and controls:** Same pinned source, CUDA 13.3 `sm_120`, run ID 11000, 120,320 workers, 64 steps, DP32, application replay with a fresh output file per pass. Keep the prior raw-counter profile as a control and the frozen 355-record production screen corpus for any later timing comparison.
- **Execution limits and stop condition:** One isolated Modal GPU allocation, bounded to the profiler's configured function timeout. Stop interpretation if any replay pass reloads prior DP data, drops a record, selects a different kernel, or lacks source/instruction attribution; preserve the failure receipt.
- **Outcomes and next actions:** A stable hot sequence supports a single frozen candidate and paired screen. Ambiguous or absent attribution calls for a narrower compiled-sequence benchmark, not a claimed bottleneck. A faster screened candidate advances to independent compatibility and five-pair confirmation. A slower or incorrect candidate remains a scoped negative result. A profiler failure remains infrastructure evidence only.
- **Recheck trigger:** A source-correlated report, new compiler/profiler support, or a correctness-checked arithmetic reduction with a frozen paired production screen.

## Resolution and history

- 2026-10-14: Recorded the isolated profiler and five bounded screen outcomes. The critical path and an advancing production candidate remain unresolved.

Completing this record or merging its PR does not establish a speed improvement.
