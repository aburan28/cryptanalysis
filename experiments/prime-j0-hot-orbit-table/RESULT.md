# Sparse hot64 orbit table: held-out result

The 64 indices were selected from the old PR #419 fixture using the
committed `count descending, slot ascending` rule. They were committed in
`hot64_selected.h` and `selection.json` **before** the new held-out pairs
were generated. The held-out bytes and independent generic output digests
were then committed before any joint, sparse or dense arm ran. The panel
ran `joint, hot64, dense, dense, hot64, joint` per curve and retained every
raw result. Release and UBSan builds both passed the checker and the
`joint_tau` unit test with `CA_WERROR=ON` on AppleClang 17.

| Curve | Hot hits / overlaps, training | Hot hits / overlaps, held-out | Joint mixed adds | Hot64 mixed adds | Dense mixed adds | Extra hot64 prep | Hot64 bytes |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| `glv-j0-32` | 460 / 1,373 (33.5%) | 285 / 1,321 (21.6%) | 7,767 | 7,482 | 6,446 | 64 mixed adds, 42 rotations, 1 inversion | 4,128 |
| `j0-56` | 591 / 2,222 (26.6%) | 383 / 2,328 (16.5%) | 16,587 | 16,204 | 14,259 | 64 mixed adds, 51 rotations, 1 inversion | 4,128 |

All 1,024 outputs per curve matched the frozen generic digest and
independent ordinary `aP+bQ` replay. The joint, hot64 and dense arms had
identical τ counts and output inversion counts on each curve. Hot64 needs
3,024 more bytes than the 1,104-byte joint precomp and 12,528 fewer bytes
than the 16,656-byte dense precomp on this build. Its extra preparation
mixed additions alone require at least **230** evaluations on `glv-j0-32`
or **172** on `j0-56` to repay at the observed held-out savings rate.
Those are lower bounds: they omit the extra inversion, rotations, lookup
and cache behavior.

The training coverage drop shows substantial slot-frequency noise. The
64-entry table does retain some advantage over using no pair table, but
the dense table saves far more online additions. The raw wall times are
exploratory because the host lacks an isolation receipt; both result files
set `cpu_speedup_claim` to `null`. This candidate is not routed into rho.
A one-target rho comparison must charge table construction to the target
and include the full walk, recovery and scalar replay before a performance
decision.

Reproduce the committed held-out panel with:

```sh
cmake -S . -B build-hot64 -DCMAKE_BUILD_TYPE=Release \
  -DCA_WERROR=ON -DCA_BUILD_JOINT_TAU_BENCH=ON
cmake --build build-hot64 --target test_joint_tau ca_joint_tau_bench
ctest --test-dir build-hot64 --output-on-failure -R '^joint_tau$'
python3 experiments/prime-j0-hot-orbit-table/check_panel.py \
  build-hot64/ca_joint_tau_bench hot64-replay.json
```
