# KernelAgent bridge to the ECC2K-130 CUDA walk

- **Status:** `investigating`
- **Kind:** implementation gap; access/tool limit (separately identified below)
- **Affected work:** [ECC2K-130 production runner](../ecc2k130/runner/README.md), [optimization probe](../ecc2k130/runner/research/kernelagent-20261013/README.md)
- **Next action owner:** ECC2K-130 GPU engineering
- **Last updated:** 2026-10-13

## Problem

The requested PyTorch KernelAgent optimization cannot yet operate on the production compatible ECC2K-130 GPU walk: the pinned KernelAgent implementation accepts a verified Triton kernel and a PyTorch reference, while the walk is an inlined CUDA C++ kernel with custom GF(2^131) carryless arithmetic, shared Frobenius tables, batched inversion, DP32 output, and checkpoint state.

The affected workload is the `certicom-ecc2k130-frobenius-v1` walk, 120,320 threads, batch 16, 640-thread blocks, four-warp inversion, and checkpoint version 2, as specified by [`build.json`](../ecc2k130/runner/build.json). A faster isolated field operation or a different walk does not establish production compatible useful-step throughput.

## Evidence and uncertainty

- **Observed:** PyTorch KernelAgent commit `e0647170da36ef9b059ac0bd3d60103aa4ed378b` documents a Triton/PyTorch input and uses Nsight Compute for the optimization loop. The current production source is [`packedfrobeniusfused.cuh`](../ecc2k130/runner/include/packedfrobeniusfused.cuh) and [`packed131.h`](../ecc2k130/runner/include/packed131.h) at cryptanalysis commit `1f8e6847de9e207880bd3be63835c3f56eb182d5`. There is no Triton walk or PyTorch reference for its full state transition in this checkout. The local host is macOS with no CUDA device or `ncu`; neither `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, nor `LLM_RELAY_URL` was set in this session's shell. The repository's [profiler diagnostic](../ecc2k130/runner/TUNING.md#if-preparation-still-fails-with-the-pinned-profiler) records a bounded failure of Nsight Compute on one Modal allocation; that does not establish that profiling fails on every GPU host.
- **Derived or proved:** Direct invocation of the documented KernelAgent optimization API on this CUDA source is unsupported by that pinned implementation. A separate native CUDA screen can test a candidate without resolving this integration gap.
- **Suspected explanation:** Whether a full Triton port can match or exceed the inlined CUDA walk is unknown. Device metrics and a validated port are needed to distinguish code generation limits from arithmetic or memory bottlenecks.
- **Missing capability:** A verified KernelAgent input for the same state transition, a configured LLM provider or relay, and a CUDA 13.3 / `sm_120` profiling host with accessible counters.
- **What this evidence does not establish:** Any new kernel speedup, regression, inability to optimize the walk, or a limit on ECC2K-130 computation.

## What would unblock it

- [ ] Supply either a Triton implementation of the full frozen walk that passes the production known-answer, DP32 corpus, and fresh/checkpoint/resume comparisons, or extend the pinned KernelAgent optimizer to accept native CUDA while retaining those checks.
- [ ] Run the optimizer with a configured provider and working Nsight Compute counters on an isolated CUDA 13.3 `sm_120` device; retain code revisions, hardware metrics, generated candidates, failures, and timing logs.

Those conditions would establish that KernelAgent can search this workload. An integrated speed improvement would still require matched production GPU runs, independent replay, and complete reporting of the kernel and cloud costs.

## Next discriminating step

- **Action or proof obligation:** Implement and validate a GF(2^131) field-operation input for KernelAgent as a compatibility probe, then determine whether the full state transition can be represented without an extra launch or state transfer. The [native arithmetic screen](../ecc2k130/runner/research/kernelagent-20261013/README.md) proceeds independently.
- **Inputs and controls:** Use the same polynomial, limb order, exact field product vectors and production CUDA output; preserve the original binary as the control. Compare any full-walk candidate on the frozen DP32 corpus and checkpoint/resume cases.
- **Execution limits and stop condition:** One isolated GPU at a time; stop a candidate on any arithmetic, DP, checkpoint or source-identity mismatch. Device watchdogs protect the machine and are not a campaign budget.
- **Outcomes and next actions:** Passing field multiplication permits a full-walk port attempt, not a speed claim. A mismatch requires a corrected implementation and new receipt. A full-walk compatibility pass allows paired timing. An unavailable profiler or provider leaves the integration open and requires a different authorized host or configured relay.
- **Recheck trigger:** A verified Triton full-walk candidate, native CUDA support in KernelAgent, an accessible profiler host, or provider configuration.

## Resolution and history

- 2026-10-13: Recorded the source/API mismatch and local capability check at the commits above. Unresolved.

Completing this record or merging its PR does not establish a speed improvement.
