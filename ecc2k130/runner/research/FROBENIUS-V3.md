# Frobenius v3: inline transform and canonical denominator cache

The v3 profile inlines the shared Frobenius transform and removes unused jump
bits from the fused kernel's denominator cache. It retains 120,320 workers,
batch 16, 640-thread blocks, four-warp inversion, the Certicom Frobenius walk,
DP weight 32, 32-byte records and checkpoint version 2.

`PACKED_INLINE_SIGMA=1` changes only the shared transform's call boundary. The
generated permutation operations and mask tables are unchanged. The flag
requires shared sigma, defaults to zero, and is enabled in `FROBENIUS_120K_FLAGS`.
Both the generator and its checked-in header carry the same conditional qualifier.

The fused kernel already has both transformed coordinates when it stores each
denominator. Its inverse loop never reads the cached jump index; v2 merely wrote
the tag and masked it away. v3 stores a canonical field value and removes that
mask. Every launch rebuilds this scratch cache before reading it, and the cache
is not part of a checkpoint. The ordinary two-pass kernel still retains its tags.

## Performance confirmation

The final combined build improved the median of five paired ratios by
**0.7824%** against v2. All five pairs improved, from
0.6311% to 0.9841%.
After compilation, the control ran 512 launches to warm the GPU. Each timed run
then used 128 launches of 1,024 steps, alternating control/candidate order between
pairs. The median absolute rates were **17.615940** and
**17.771584 billion updates/s**. The gain is the median of
paired ratios, which need not equal the ratio of the two absolute medians.

| Pair | v2 control | v3 candidate | Gain |
| --- | ---: | ---: | ---: |
| 1 | 17.680471 | 17.792045 | 0.6311% |
| 2 | 17.615940 | 17.771584 | 0.8835% |
| 3 | 17.603847 | 17.741582 | 0.7824% |
| 4 | 17.602373 | 17.739907 | 0.7813% |
| 5 | 17.649878 | 17.823572 | 0.9841% |

Every timed run emitted the same 705 records with zero drops, sorted SHA-256
`530de6e2e95f910cb8ce89e9db3ad681917296817650c4a5a5492d75e6d18e4e`.
The candidate retained 96 registers/thread, zero local bytes/thread and 14,592
shared bytes/block. Its binary SHA-256 is
`b3105b63c03075975c4bd7436f6a7983be560525c28a28595463fcea2b52ddfd`.
The [final receipt](production/2026-09-21-frobenius-v3-combination-confirm.json)
contains the exact source hashes, all 27 selected build settings and individual runs.

Inlining alone also improved all five warmed pairs, with a 0.6584% median gain;
its [separate receipt](production/2026-09-21-frobenius-v3-inline-confirm.json)
records that comparison. The 1.0905% gain in the short combination screen below
was a selection result; **0.7824% is the final warmed confirmation result**.
Absolute rates from different GPUs should not be used to infer a speedup.

## Screening

Each configuration used two alternating control/candidate pairs on an RTX PRO
6000 Blackwell Server Edition. Each run used 64 launches of 1,024 steps, run ID
11000, 120,320 workers and DP32. Rates below are billion updates/s; gain is the
median of paired ratios. These short screens select changes for longer
confirmation; absolute rates across GPUs are not directly comparable.

| Configuration | v2 control | Candidate | Paired gain |
| --- | ---: | ---: | ---: |
| `inline_sigma` | 17.825280 | 17.975620 | +0.843% |
| `forward_chain_first` | 17.827802 | 17.822713 | -0.029% |
| `pair_ilp` | 17.825086 | 17.610993 | -1.201% |
| `fused_unroll2` | 17.823941 | 17.655397 | -0.946% |
| `fused_prefetch` | 17.821376 | 17.752192 | -0.388% |
| `fused_pipeline` | 17.823797 | 17.684643 | -0.781% |
| `inline_inverse` | 17.826088 | 17.778900 | -0.265% |
| `balanced_l2_normal` | 17.826701 | 17.813110 | -0.076% |
| `clmad_square` | 17.827645 | 17.831600 | +0.022% |
| `flat_clmul` | 17.826124 | 17.719581 | -0.598% |
| `dead_mask` | 17.697705 | 17.701297 | +0.022% |
| `dead_mask_inline_sigma` | 17.724027 | 17.814076 | +0.509% |
| `pair_clmul` | 17.825166 | 17.829023 | +0.022% |
| `fixed_directions` | 17.828325 | 17.321082 | -2.845% |
| `untagged_denominator` | 17.826020 | 17.928082 | +0.573% |
| `blocks320` | 17.842056 | 13.624523 | -23.638% |
| `inline_sigma_untagged` | 17.834312 | 18.028734 | +1.091% |

All runs emitted the same 355 records with zero drops, sorted SHA-256
`c80bb8db34e419d53bc946a5fef01c99fd60214a16f9b42ff87b5d52f3668a90`.
The `clmad_square` name is historical: toggling `PACKED_ALU_SQUARE` does not
change the current polynomial squaring implementation, so this is a negative
control. `blocks320` changes both the block size and collective inverse width
(320 threads, two warps per inverse, two resident blocks requested).

Receipts: [initial ten cases](production/2026-09-21-frobenius-v3-screen.json),
[dead-flag cache](production/2026-09-21-frobenius-v3-dead-mask-screen.json),
[structural cases](production/2026-09-21-frobenius-v3-structure-screen.json), and
[combined candidate](production/2026-09-21-frobenius-v3-combination-screen.json).

## Compatibility and validation

The final combined binary passed all **17** fresh-state and bidirectional-resume
comparisons against v2. Checkpoints and sorted record corpora were byte-identical:

- Six standard cases: populations 640, 641 and 256, each at DP0 and DP50 with
  eight steps per launch. All **10,249 CPU-reference verification operations**
  passed with zero dropped records.
- Nine odd-launch cases: the same populations at 1, 3 and 17 steps, with DP0.
- Two forced-restart cases: populations 640 and 641, 4,097 steps per launch and
  `--max-iters 1`, crossing the 4,096-step guard and comparing resumed state.

The dedicated GPU shared-sigma probe passed **21 scenarios and 21,036 input
pairs** against independent routing, plus 114 full block-mask snapshots, output
guards and inactive blocks. Generated-header consistency checks passed.

`make check-cloud check-cli` passed (148 tests passed, seven optional tests
skipped). The CPU engine's `--test` passed with zero failures; the worker rehearsal
passed shutdown/upload, checkpoint resume, recovery into a fresh work directory
and the small-curve solution path. macOS builds used `CXX=clang++ OMPFLAGS=`.

The [packaging audit](production/2026-09-21-frobenius-v3-packaging.json) matches all
116 tracked build/source files and 27 production settings to the final measured
binary. The confirmation receipt's driver hash also matches the checked-in tuner.

Compute Sanitizer was not repeated: the [previous attempt on this GPU](production/2026-09-21-frobenius-fused-sanitizer.json)
reported `Device not supported`. There is no instrumented sanitizer coverage;
the evidence here is direct GPU comparison, CPU replay and checkpoint identity.

## Reproduction

From the repository root:

```sh
modal run ecc2k130/runner/tune_frobenius_v3.py --mode confirm --selected production \
  --output research/production/frobenius-v3-confirm-repeat.json
make -C ecc2k130/runner gpu-production
make -C ecc2k130/runner check-cloud check-cli
```

The driver defaults to frozen image `im-LEaik53IOCmWvHm1O2UUPQ` in the campaign's
Modal account; `ECC_BENCH_IMAGE` can select another compatible compiler image.
It builds its control from commit `7431819dd836d81707c0cd510a322ec9fdb14282`
(the merged v2 source), independently of local candidate edits. Prototype
screens also start from that pinned source. Only `--selected production` builds
the current working tree without prototype rewrites. Build commands, compiler,
GPU, source hashes, binary hashes and individual runs are saved in each receipt.
The driver uses temporary container files and no campaign secrets.

This PR prepares the v3 release configuration. It does not roll out a new fleet.
