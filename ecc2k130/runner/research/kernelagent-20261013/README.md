# ECC2K-130 GPU optimization probe, 2026-10-13

## Requested scope and method

The request is to use [PyTorch KernelAgent](https://github.com/meta-pytorch/KernelAgent/tree/e0647170da36ef9b059ac0bd3d60103aa4ed378b) to speed up the ECC2K-130 GPU code. The first gate is [the CUDA-to-KernelAgent bridge](../../../../problems/ecc2k130-kernelagent-cuda-bridge.md): KernelAgent currently accepts Triton/PyTorch inputs, and the production walk is native CUDA. No KernelAgent optimization result is claimed here.

The independent native screen checks whether the existing `ECC_PACKED_TOP_CLMAD=1` field-product variant helps the *production compatible* Frobenius walk. It is selected by the existing source-level cost analysis in [`packed131.h`](../../include/packed131.h): the candidate moves a three-bit product correction from integer/logic operations to carryless instructions. This is a candidate hypothesis, not a measured gain. It changes no walk equation, DP rule, record layout, or checkpoint format.

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

### Commands

```sh
python3 -m py_compile ecc2k130/runner/tune_frobenius_v3.py
modal run ecc2k130/runner/tune_frobenius_v3.py --mode screen \
  --selected production,production_top_clmad --production-baseline \
  --baseline-commit 1f8e6847de9e207880bd3be63835c3f56eb182d5 \
  --output research/kernelagent-20261013/top-clmad-screen.json
```

The receipt path is relative to `ecc2k130/runner/`. Save the exact CLI output separately. The screen is a fixed known-corpus comparison; it does not supply held-out confirmation evidence. Preserve regressions and failures rather than replacing the receipt.

## Results

Pending the isolated GPU screen. An unrun command is not a result.
