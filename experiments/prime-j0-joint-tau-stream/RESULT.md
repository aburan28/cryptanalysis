# Joint prime-field τ stream: frozen operation panel

The frozen prospective panel evaluates 1,024 public `aP+bQ` pairs on each
of two prime-field j=0 study subgroups. `P` is the repository's named base
point and `Q=37P`. Eight boundary pairs precede 1,016 deterministic fresh
pairs per curve. The fixture and independent generic output digests were
committed before either τ arm ran. Both arms use the same 18 prepared seeds,
digit alphabet and scalar recoder. The script executes split, joint, joint,
split for each curve and retains every raw subprocess result.

| Curve | Split τ steps | Joint τ steps | τ steps saved | Split full adds | Joint full adds | Mixed adds, both | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `glv-j0-32` | 26,321 | 13,967 | 12,354 | 1,020 | 0 | 7,771 | 1,024/1,024 generic replays passed |
| `j0-56` | 66,274 | 34,091 | 32,183 | 1,020 | 0 | 16,650 | 1,024/1,024 generic replays passed |

Each arm also performs the same number of digit rotations and output
inversions. The shared preparation uses two τ maps, ten doublings, eight
mixed additions and one inversion on each curve. `sizeof` the prepared
object is 1,104 bytes on the tested build. The release and UBSan panels
both passed with identical operation counts. The C unit test independently
checks 525 pairs per curve, including identity, maximal 64-bit inputs,
equal points, opposite points and cancellation. The release and UBSan
unit tests passed with `CA_WERROR=ON` on AppleClang 17.

These are algorithmic counts for a prepared 1,024-pair diagnostic. The raw
local wall times in `panel_local.json` and `panel_ubsan.json` are exploratory;
both records deliberately set `cpu_speedup_claim` and `isolation_receipt`
to `null`. They are not a one-target rho speedup. A one-target integration
must include target-dependent preparation, walk, recovery, and scalar replay
under the same resource envelope and pass the repository's host-level CPU
isolation gate before any wall-time promotion.

Reproduce the committed source and fixture with:

```sh
cmake -S . -B build-joint-tau -DCMAKE_BUILD_TYPE=Release \
  -DCA_WERROR=ON -DCA_BUILD_JOINT_TAU_BENCH=ON
cmake --build build-joint-tau --target test_joint_tau ca_joint_tau_bench
ctest --test-dir build-joint-tau --output-on-failure -R '^joint_tau$'
python3 experiments/prime-j0-joint-tau-stream/check_panel.py \
  build-joint-tau/ca_joint_tau_bench panel-replay.json
```

The checker fails if a fixture hash, frozen generic digest, output replay,
common preparation counter, or expected operation saving differs. The
implementation requires the caller to establish subgroup membership for
both input points; it checks their curve validity during preparation.
