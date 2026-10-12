# Fused unit-orbit digit pairs: frozen panel result

The source and checker were committed before this prospective panel ran.
It reuses the two 1,024-pair little-endian fixtures and frozen generic
digests from the parent joint-stream experiment. Both arms use the same
scalar reductions and digit streams; the only change is how simultaneous
nonzero digits enter the projective accumulator. Each arm runs twice in
`joint, orbit, orbit, joint` order per curve. All outputs passed independent
ordinary `aP+bQ` replay in release and UBSan builds.

| Curve | Overlap positions | Joint mixed adds | Orbit mixed adds | Mixed adds saved | Online rotations saved | Extra preparation | Extra table bytes |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `glv-j0-32` | 1,373 | 7,771 | 6,398 | 1,373 | 873 | 486 mixed adds, 324 rotations, 1 inversion | 15,552 |
| `j0-56` | 2,222 | 16,650 | 14,428 | 2,222 | 1,508 | 486 mixed adds, 324 rotations, 1 inversion | 15,552 |

Both arms use 13,967 τ steps on the smaller curve and 34,091 on the larger.
The exact prepared object sizes are 1,104 bytes for the joint control and
16,656 bytes for the fused orbit table on the tested AppleClang 17 build.
The table has 486 entries, one for each `(P seed, Q seed, relative unit)`.

The extra 486 preparation additions divided by the observed per-evaluation
mixed-add savings give **lower bounds** of 363 evaluations on `glv-j0-32`
and 224 on `j0-56` before that one operation type breaks even. These
bounds omit the extra inversion, 324 preparation rotations, table lookup,
cache effects and memory. With `A` the cost of a mixed add, `R` a unit
rotation, and `I` an inversion, the per-target accounting is:

| Curve | Additional preparation | Online saving per observed evaluation |
| --- | --- | --- |
| `glv-j0-32` | `486A + 324R + I` | `(1373A + 873R) / 1024` |
| `j0-56` | `486A + 324R + I` | `(2222A + 1508R) / 1024` |

The local wall times are retained in `panel_local.json` and
`panel_ubsan.json` but have no host-level isolation receipt. They show no
dependable wall-time gain. Both machine records set `cpu_speedup_claim` to
`null`. This format is an opt-in internal candidate; it is not wired into
the one-target rho solver. Its larger preparation and memory costs must be
charged to the target in any rho comparison.

Reproduce from this commit with:

```sh
cmake -S . -B build-joint-orbit -DCMAKE_BUILD_TYPE=Release \
  -DCA_WERROR=ON -DCA_BUILD_JOINT_TAU_BENCH=ON
cmake --build build-joint-orbit --target test_joint_tau ca_joint_tau_bench
ctest --test-dir build-joint-orbit --output-on-failure -R '^joint_tau$'
python3 experiments/prime-j0-joint-orbit-pairs/check_panel.py \
  build-joint-orbit/ca_joint_tau_bench orbit-replay.json
```
