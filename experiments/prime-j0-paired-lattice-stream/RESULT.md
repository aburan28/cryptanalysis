# Paired lattice representatives: held-out operation panel

Source and checker were committed before generating the held-out scalar
pairs. The new little-endian fixtures and independent generic output
digests were committed before any τ arm ran. The release panel ran
`joint, paired2, paired5, paired, paired, paired5, paired2, joint` per
curve, preserving every raw trial. The UBSan replay used the same frozen
inputs. All 1,024 outputs per curve and arm matched the generic digest and
independent ordinary `aP+bQ` replay. Release and UBSan `joint_tau` tests
passed with `CA_WERROR=ON` on AppleClang 17; release `curve` and `rho`
tests also passed.

| Curve | Arm | τ steps | Mixed adds | Rotations | Recode attempts | Stream pairs scored |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | Joint control | 13,999 | 7,747 | 5,079 | 2,042 | 0 |
| | Paired 2 | 13,483 | 7,568 | 4,620 | 4,084 | 4,086 |
| | Paired 5 | 13,295 | 7,390 | 4,466 | 10,210 | 25,512 |
| | Paired 25 | 13,344 | 7,152 | 4,218 | 51,050 | 637,552 |
| `j0-56` | Joint control | 34,007 | 16,600 | 11,205 | 2,042 | 0 |
| | Paired 2 | 33,593 | 16,161 | 10,646 | 4,084 | 4,086 |
| | Paired 5 | 33,478 | 15,847 | 10,210 | 10,210 | 25,512 |
| | Paired 25 | 33,508 | 15,446 | 9,574 | 51,050 | 637,552 |

The two-neighbor arm saves 516 τ steps, 179 mixed additions and 459
rotations on `glv-j0-32`; it saves 414, 439 and 559 respectively on
`j0-56`. It inspects five L1 candidates per nonzero scalar and recodes
only the best two, compared with the control's 25 L1 checks and one
recoding per scalar. All four arms use the same 1,104-byte prepared object,
one preparation inversion, and the same output inversion count.

The fixed model `6 × τ + 11 × mixed add + rotation` decreases from
174,290 to 168,766 on `glv-j0-32` and from 397,847 to 389,975 on
`j0-56` for paired2. This model counts point work only. The larger
searches reduce more point work but score and recode many more streams;
their operation savings cannot be interpreted as CPU speedups.

The raw local wall times in `panel_local.json` and `panel_ubsan.json`
are exploratory. The paired2 times were lower than the joint control in
this local ABBA panel, but the host has no isolation receipt and both
records set `cpu_speedup_claim` to `null`. No one-target rho integration
or academic novelty claim follows from this experiment. Before routing
the algorithm into rho, compare full verified one-target solves with all
target-dependent preparation, walk, recovery and replay charged in the
same isolated resource envelope.

Reproduce from this commit with:

```sh
cmake -S . -B build-paired-lattice -DCMAKE_BUILD_TYPE=Release \
  -DCA_WERROR=ON -DCA_BUILD_JOINT_TAU_BENCH=ON
cmake --build build-paired-lattice --target test_joint_tau ca_joint_tau_bench
ctest --test-dir build-paired-lattice --output-on-failure -R '^joint_tau$'
python3 experiments/prime-j0-paired-lattice-stream/check_panel.py \
  build-paired-lattice/ca_joint_tau_bench paired-lattice-replay.json
```
