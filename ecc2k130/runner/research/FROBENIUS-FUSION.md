# Frobenius pass fusion at 120,320 workers

The v2 profile prepares the next step while the updated point is still in registers.
It also issues the inverse-chain product before the slope product. Both changes
preserve the Certicom Frobenius walk, DP weight 32, 32-byte records, batch 16,
640-thread blocks, four-warp inversion and checkpoint version 2.

## Performance confirmation

The exact proposed build is **2.7734% faster** by the median
of five paired ratios. After compilation, the control ran 512 launches to warm
the GPU. Each timed run then used 128 launches of 1,024 steps; control/candidate
order alternated between pairs. All five pairs improved, with gains from
2.7216% to 2.8523%. Median absolute rates were **17.156838**
and **17.625650 billion updates/s**. The measured gain is
relative to the paired control, not to a historical rate on another GPU.

| Pair | Deployed v1 | Proposed v2 | Gain |
| --- | ---: | ---: | ---: |
| 1 | 17.193422 | 17.661360 | 2.7216% |
| 2 | 17.158062 | 17.647467 | 2.8523% |
| 3 | 17.156838 | 17.625650 | 2.7325% |
| 4 | 17.136178 | 17.617125 | 2.8066% |
| 5 | 17.138633 | 17.613956 | 2.7734% |

Every timed run emitted the same 705 records, sorted SHA-256
`530de6e2e95f910cb8ce89e9db3ad681917296817650c4a5a5492d75e6d18e4e`,
with zero drops. The candidate retained 96 registers/thread, zero local
bytes/thread and 14,592 shared bytes/block. Its binary SHA-256 is
`b8ac0ec70358f4874262db6528a06f431945226ff62ceef6252612df0f344436`.
The [final confirmation receipt](production/2026-09-21-frobenius-fused-confirm.json)
records all 26 build settings, candidate source hashes and the individual runs.

## Why the fused loop preserves the walk

For each batch slot, the forward pass stores a weighted prefix
`W_i = E_i * product(D_k for slots preceding i)`. The inverse pass traverses
those slots in reverse order to recover `lambda_i = E_i / D_i`. The multiplication
order can change provided that the inverse traversal reverses it.

The fused kernel alternates slot direction at each step. After updating `(x, y)`,
it computes that point's next denominator and weighted prefix immediately. This
removes the second coordinate load for every step after the launch prologue.
The first selection still occurs at `iterBase`; the last update does not select
or report its output until the next launch. DP reporting, trail expiry and
reseeding therefore retain their original iteration boundaries.

The shared sigma table is initialized by every block thread before inactive
threads return. Partial blocks use the existing scalar inverse fallback.
`FROBENIUS_FUSED=0` retains the ordinary kernel; `FROBENIUS_FUSED=1` requires the
Frobenius polynomial-state path, weighted prefix 2, shared sigma and the plain
slot loop. `PACKED_CHAIN_FIRST=1` selects the product order used by v2.

## Initial screening

Each case used two control/candidate pairs, with their order reversed in the
second pair, on an RTX PRO 6000. Every timed run used 120,320 workers, 1,024 steps
per launch, 64 launches, run ID 11000 and DP32. All produced the same 355-record
corpus, sorted SHA-256
`c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90`,
with zero drops. Rates are billion point updates per second, and gains are
medians of paired ratios. These short runs select candidates for confirmation.

| Candidate | Control | Candidate | Paired gain |
| --- | ---: | ---: | ---: |
| `chain_first` | 17.549454 | 17.722311 | +0.985% |
| `pair_ilp` | 17.543268 | 17.586268 | +0.245% |
| `prefetch` | 17.546506 | 17.046852 | -2.848% |
| `unroll2` | 17.540439 | 17.426215 | -0.651% |
| `no_persist` | 17.544781 | 16.453910 | -6.218% |
| `balanced_l2_normal` | 17.544421 | 17.423029 | -0.692% |
| `balanced_l2_streaming` | 17.547022 | 17.429451 | -0.670% |
| `balanced_l2_chain_first` | 17.545583 | 17.481475 | -0.365% |
| `fused` | 17.504822 | 17.864434 | +2.058% |
| `fused_chain_first` | 17.477373 | 17.917233 | +2.520% |

The control is the actual deployed v1 binary,
`108f48480710c14d4368ec924d0101293993afac66b5b7c3b27f935d781c7846`.
The [eight-way screen](production/2026-09-21-frobenius-tuning-screen.json) and
[fusion prototype screen](production/2026-09-21-frobenius-fused-screen.json)
record commands, compiler flags, source hashes, binary hashes and every sample.
The original L2 policy remains selected because all replacements regressed.

The [instruction-order-only confirmation](production/2026-09-21-frobenius-tuning-confirm.json)
measured a smaller 0.619% median paired gain. Its GPU cooled during compilation
and then slowed while warming. The final fusion confirmation adds a 512-launch
control warm-up after compilation, before the five timed pairs.

## Compatibility and validation

All **17** fresh-state and bidirectional-resume comparisons passed against the
deployed v1 binary. Checkpoints and sorted record corpora were byte-identical:

- Six standard cases: populations 640, 641 and 256, each at DP0 and DP50 with
  eight steps per launch. All **10,249 CPU-reference verification operations**
  passed with zero dropped records.
- Nine odd-launch cases: the same populations with 1, 3 and 17 steps per launch
  at DP0, including both complete blocks and the scalar-inverse fallback.
- Two forced-restart cases: populations 640 and 641, 4,097 steps per launch and
  `--max-iters 1`, crossing the 4,096-step guard and comparing resumed state.

`make check-cloud check-cli` passed (148 tests passed, seven optional tests
skipped), and the new Modal entrypoint passed `codegen/checkcli.py`. The CPU
engine's `--test` passed with zero failures. The worker rehearsal also passed
shutdown/upload, checkpoint resume, recovery into a fresh work directory and
the small-curve solution path. On macOS these used `CXX=clang++ OMPFLAGS=`.

The [source and build audit](production/2026-09-21-frobenius-fused-packaging.json)
matches all 116 relevant source files and the 26 selected compiler settings to
the GPU confirmation.

Compute Sanitizer's memcheck and synccheck attempts both reported
`Device not supported` on this GPU. They provided **no instrumented coverage**;
the [sanitizer receipt](production/2026-09-21-frobenius-fused-sanitizer.json)
preserves that limitation and all four attempts. Direct GPU compatibility tests
and CPU-reference checks are the validation evidence for this change.

The build manifest selects `rtx-pro6000-frobenius32-120k-v2`. This change prepares
the validated release configuration; the live fleet still runs the earlier v1
deployment recorded in [DP reconciliation](DP-RECONCILIATION.md).

## Reproduction

From the repository root:

```sh
modal run ecc2k130/runner/tune_frobenius.py --mode confirm \
  --selected fused_chain_first \
  --output research/production/frobenius-fused-confirm-repeat.json
make -C ecc2k130/runner gpu-production
make -C ecc2k130/runner check-cloud check-cli
```

The Modal driver defaults to the frozen v1 image in the campaign's Modal account.
`ECC_BENCH_IMAGE` can select another image containing the v1 executable and source
at `/opt/ecc2k130`; its binary hash is recorded in the receipt. The proposed
Makefile, kernel sources and compatibility checker are overlaid for the candidate
build. The driver uses one temporary GPU container and no campaign secrets.
The final confirmation receipt, rather than the prototype screen, binds the
proposed source and build settings to the measured binary.
