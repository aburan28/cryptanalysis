# ECC2K-130 GPU optimization probe, 2026-10-13

## Requested scope and method

The request is to use [PyTorch KernelAgent](https://github.com/meta-pytorch/KernelAgent/tree/e0647170da36ef9b059ac0bd3d60103aa4ed378b) to speed up the ECC2K-130 GPU code. The first gate is [the CUDA-to-KernelAgent bridge](../../../../problems/ecc2k130-kernelagent-cuda-bridge.md): KernelAgent currently accepts Triton/PyTorch inputs, and the production walk is native CUDA. No KernelAgent optimization result is claimed here.

The independent native screen checks whether the existing `ECC_PACKED_TOP_CLMAD=1` field-product variant helps the *production compatible* Frobenius walk. It is selected by the existing source-level cost analysis in [`packed131.h`](../../include/packed131.h): the candidate moves a three-bit product correction from integer/logic operations to carryless instructions. This is a candidate hypothesis, not a measured gain. It changes no walk equation, DP rule, record layout, or checkpoint format.

After that screen, profile a production-configured build from pinned public source with the standalone Nsight control and the exact application-replay settings that pass it. The next prespecified candidate is `PACKED_TOP_HOIST=1`: it computes the unchanged three-bit correction before the independent carryless products, allowing the compiler to schedule integer/logic and carryless work concurrently. A short paired screen can reject it; only a gain outside the A/A spread advances to the five-pair and compatibility gates. Its output format and walk are identical by construction, but the host and GPU controls still have to check that claim.

The profiler also reported 96 registers/thread, about 41% occupancy and a scheduler with no eligible warp on 45% of cycles. Two follow-up compile-only candidates independently stop inlining the single-product helper (`PACKED_INLINE_POLY=2`) or the pair-product helper (`PACKED_INLINE_POLY=1`), keeping all arithmetic and launch settings the same. Lower caller register pressure might raise occupancy, but call overhead and callee spills can reverse the effect. Screen both with an A/A control and the same frozen DP32 corpus. A candidate advances only if its paired ratio exceeds the A/A spread, then it owes five warmed pairs and the full compatibility checks; any failure or regression is retained.

| Requirement | Gate and evidence |
| --- | --- |
| Same production walk | Commit `1f8e6847de9e207880bd3be63835c3f56eb182d5`, `certicom-ecc2k130-frobenius-v1`, DP32, batch 16, 120,320 workers, 640 threads/block, four-warp inverse |
| Isolated hardware measurement | One RTX PRO 6000 through `tune_frobenius_v3.py`, baseline and candidate built on that GPU with CUDA 13.3 and alternating paired order |
| Correctness | Frozen sorted DP32 corpora and zero drops for every timing sample; full fresh/checkpoint/resume and shared-sigma checks before selection |
| KernelAgent use | A verified same-workload Triton input and an accessible profiler/provider are still required; see the linked problem |
| Performance claim | Exploratory screen only until a five-pair confirmation and end-to-end accounting are complete |

## Frozen native screen

- Control: exact `origin/main` source at `1f8e6847de9e207880bd3be63835c3f56eb182d5`, `PACKED_TOP_CLMAD=0`, all other production v3 settings from [`build.json`](../../build.json).
- Candidate: the same source, `PACKED_TOP_CLMAD=1` only.
- A/A control: a second build with the baseline settings; retain its paired timing spread.
- Workload: run ID `11000`, 120,320 worker threads, 16 slots per thread, DP weight 32, 1,024 steps/launch. The screen uses 64 launches per sample, two alternating pairs, and the existing 64-launch corpus hash in the tuner. If the candidate is correct and exceeds A/A noise, confirmation uses 128 launches per sample, five alternating pairs, 512-launch warmup, the existing 128-launch corpus hash, and the tuner's fresh/checkpoint/resume comparisons.
- Accounting: `billions_per_second` measures GPU client scalar updates and DP collection. It excludes compiler time, periodic S3/RDS work, checkpoint upload, and any target recovery. Record those separately before an end-to-end claim.
- Hardware boundary: temporary single-GPU Modal function, at most 2,700 seconds; no campaign secrets or production worker state. A profiler failure, timeout or run failure is infrastructure evidence, not a speed comparison.
- Profiler boundary: one matching production build and a one-launch Nsight Compute application replay with fixed clocks and cache controls disabled; these counters are diagnostic and never substitute for ordinary paired throughput runs.

### Commands

```sh
python3 -m py_compile ecc2k130/runner/tune_frobenius_v3.py
modal run ecc2k130/runner/tune_frobenius_v3.py --mode screen \
  --selected production,production_top_clmad --production-baseline \
  --baseline-commit 1f8e6847de9e207880bd3be63835c3f56eb182d5 \
  --output research/kernelagent-20261013/top-clmad-screen.json
modal run ecc2k130/runner/profile_diagnostic.py \
  --output ecc2k130/runner/research/kernelagent-20261013/profile-diagnostic.json
modal run ecc2k130/runner/research/kernelagent-20261013/profile_production.py \
  --output ecc2k130/runner/research/kernelagent-20261013/production-profile.json
modal run ecc2k130/runner/tune_frobenius_v3.py --mode screen \
  --selected production,production_top_hoist --production-baseline \
  --baseline-commit 1f8e6847de9e207880bd3be63835c3f56eb182d5 \
  --output research/kernelagent-20261013/top-hoist-screen.json
modal run ecc2k130/runner/tune_frobenius_v3.py --mode screen \
  --selected production,production_single_noinline,production_pair_noinline \
  --production-baseline \
  --baseline-commit 1f8e6847de9e207880bd3be63835c3f56eb182d5 \
  --output research/kernelagent-20261013/inline-screen.json
```

The receipt path is relative to `ecc2k130/runner/`. Save the exact CLI output separately. The screen is a fixed known-corpus comparison; it does not supply held-out confirmation evidence. Preserve regressions and failures rather than replacing the receipt.

## Results

The [top-CLMAD screen](top-clmad-screen.json) completed on an RTX PRO 6000 Blackwell Server Edition, driver 610.57.04, CUDA 13.3. The A/A control median paired ratio was `1.000965` (individual ratios `0.999983`, `1.001948`). The top-CLMAD candidate's median paired ratio was `0.839956` (individual ratios `0.839056`, `0.840856`), with median candidate/control rates of `15.108721` and `17.987533` billion updates/s. Every timed arm reproduced 355 frozen DP32 records with sorted SHA-256 `c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90` and zero drops. This is a clear regression under the tested configuration; retain `PACKED_TOP_CLMAD=0`. The [full run log](top-clmad-screen.log) is retained. The repository's `modal_app.py` also contains an older comment about a slower top-CLMAD configuration; this screen specifically tests the present production Frobenius profile.

The [Modal profiler control](profile-diagnostic.json) passed normal CUDA. Its default launch and counter attempts failed because Nsight Compute tried to lock clocks. Application replay with `--clock-control none --cache-control none` succeeded, so the [production-configured walk profile](production-profile.json) used those settings with Nsight Compute 2025.3.1. It built all 117 source files from the pinned public commit with the same command and CUDA 13.3 compiler as the paired screen. The executable SHA-256 differed across the two builds; the source hashes and build arguments matched, so this is a production-*configured* profile rather than a byte-identical profile of the screen executable. The profile captured one 640-thread-block walk launch on 188 SMs: 96 registers/thread, 40.75% achieved occupancy, 81.28% SM compute throughput, 30.80% memory throughput, 93.47% L2 hit rate, and zero local spilling requests. Nsight's uncontrolled-clock warning and short four-step run limit interpretation. The full [profile log](production-profile.log) and [control log](profile-diagnostic.log) remain available.

The top-hoist candidate's [host arithmetic run](top-hoist-host.json) passed 2,526 polynomial reductions plus independent multiplication, squaring, inversion and walk checks. The broader `make test-clmad` target fails before its host binaries on this unchanged pinned source because `NativeSquareProofTests` rejects the native-square source contract; the [failure receipt](main-test-clmad.json) is retained and does not invalidate the separate host or GPU observations. A network-restricted first profiler invocation and the first production-profile script's remote path error are preserved in [sandbox log](profile-diagnostic-sandbox-failure.log) and [script log](production-profile-runner-path-failure.log).

The [top-hoist GPU screen](top-hoist-screen.json) completed on the same GPU model and driver. Its A/A median paired ratio was `1.000134` (individual ratios `1.000080`, `1.000188`). The hoisted candidate's median ratio was `0.995875` (individual ratios `0.995399`, `0.996351`), with median candidate/control rates of `17.961446` and `18.035853` billion updates/s. Every arm again emitted the same 355-record DP32 corpus and zero drops. Retain `PACKED_TOP_HOIST=0`; the [full log](top-hoist-screen.log) remains available. The candidate was a bounded schedule hypothesis motivated by the NCU compute and occupancy counters; the counter hints did not predict a gain on this build. The screen's two pairs do not estimate a deployment-wide effect, and no five-pair confirmation was triggered by this regression.

The [inlining screen](inline-screen.json) tested both follow-up variants on an RTX PRO 6000 with driver 580.95.05. Its A/A median ratio was `1.002810`. Stopping single-product inlining gave a median ratio of `0.987127` (pairs `0.986826`, `0.987429`); stopping pair-product inlining gave `0.969534` (pairs `0.969430`, `0.969638`). Every arm reproduced the same 355-record DP32 corpus with zero drops. Both variants are rejected for this configuration. The [full log](inline-screen.log) is preserved. This screen is exploratory because its protocol and result are first published together. The different driver from the successful 610.57.04 profile limits a direct counter-to-timing inference, though each candidate was compared with its control on the same GPU allocation and driver. Neither regression warrants the five-pair confirmation.

An independent [JSON receipt check](receipt-validation.json) recomputed all paired ratios, checked one-knob candidate differences and source identity, confirmed every frozen DP32 output and zero-drop marker, and verified that the profiler captured the intended walk symbol. It passed for all three screens and the profile. The check is a replay of recorded data, not an independent GPU rerun.

The measured work did not establish a useful-step improvement or complete cloud cost advantage. Direct KernelAgent optimization still needs the same-workload input and provider described in the linked problem record.

## Longer profiler follow-up (frozen before execution)

The four-step profile includes setup and exposes only aggregate warp scheduling. Profile the unchanged pinned production source for 64 steps with the same worker count, build settings, run ID and DP32 rule. Add Nsight Compute's `ComputeWorkloadAnalysis` and `SourceCounters` sections to identify the busy execution pipe and sampled stall sites. Keep application replay, uncontrolled-clock and cache settings, and a distinct `production-compute-profile.json` receipt. The diagnostic is accepted only if the normal run succeeds, the profiler reports the `eccPacked131::walk` kernel and the added sections return usable counters. A profiler error stays in its own receipt and does not update the earlier profile. The longer replay is still diagnostic; ordinary paired runs decide throughput.

Next, choose one source-level candidate that reduces the identified hot-path work while preserving field and walk outputs. Record its exact diff and a paired A/A screen against the pinned production source before any wider claim. Advance only if the candidate passes the frozen DP32 corpus with zero drops and improves both paired ratios outside the A/A spread; then run five paired confirmations and the existing fresh/checkpoint/resume compatibility gate. A slower, incorrect or inconclusive candidate remains an observed screen result.

The first [64-step attempt](production-compute-profile.json) returned all requested Nsight sections, but application replay reused the append-only `/tmp/profile-dp.bin` between passes. Later processes reported `reloaded ... points`, so their workload inputs were not identical. Keep that receipt as an invalid profiler comparison. The corrected launcher creates a unique empty DP file for each replay process; its SHA-256 is recorded in a new `production-compute-profile-isolated.json` receipt. Require no `reloaded` message in any pass before interpreting the counters. The original four-step profile remains a separate short diagnostic.
