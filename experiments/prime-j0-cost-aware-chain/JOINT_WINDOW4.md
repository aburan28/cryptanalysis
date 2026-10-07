# Joint Eisenstein radix-16 orbit table

This fixed-base public-scalar experiment treats the two short lattice
coordinates as **one joint digit at each binary window**. For the existing
exact reducer, `k = x + yω (mod r)`. Balanced radix 16 writes
`x = Σ x_i16^i` and `y = Σ y_i16^i`, with each digit in `[-8,7]`.
One joint action represents `[16^i(x_i+y_iω)]P`. The six units
`{1,ω,ω²,−1,−ω,−ω²}` partition the 255 nonzero digit pairs into 71
orbits. The table stores one affine point per orbit and position; a 654-byte
static map returns its slot and unit action. The online evaluator adds at
most one point per nonzero window, then converts its Jacobian accumulator
to affine. The format is variable-time and only for public scalars.

The 25-bit study subgroup uses four positions and 284 prepared points; the
56-bit subgroup uses seven positions and 497 points. The rounded lattice
coefficients plus the `±2` search radius bound the smaller curve's two
Eisenstein coordinates by 19,803 and 13,995, within four signed-window
positions' positive/negative capacities of 30,583/34,952. On `j0-56`, the
corresponding conservative bounds are 579,447,928 and 579,097,785, **above**
seven positions' positive/negative capacities of 125,269,879/143,165,576.
The held-out panel's largest observed absolute coordinates
were 115,832,497 and 115,817,187, so it had zero fallbacks; this does not
prove that every scalar fits. The native evaluator checks capacity and uses
the generic multiplier whenever it is exceeded.

[`joint-window4-design.json`](joint-window4-design.json), the generated-map
rule, and the disjoint-input generator were frozen in commit `9408da4f`
before [`joint-window4-inputs/inputs.json`](joint-window4-inputs/inputs.json)
was generated. The new fixture has 32,768 scalars across eight cases and
excludes every scalar in eight earlier fixtures. The independent Python
model checked all scalar identities and 184 elliptic-curve point outputs.
The C map verifier exhaustively checks all 256 raw digit pairs and every
canonical representative. Preparation verification independently recomputes
all prepared points.

The [release panel](joint-window4-native-panel.json) and
[warnings-as-errors UBSan panel](joint-window4-ubsan-panel.json) each ran 24
arms: joint window, signed radix-256, and fixed comb9 in rotating order.
Every arm independently verified all 4,096 outputs per case against the
generic multiplier; all paired output digests matched; there were no
fallbacks. Release and UBSan `test_curve` suites each passed 2,311,946
checks, including identity, scalar edges, and forced capacity fallback.
The first UBSan rebuild on the nearly full local system volume failed when
`ranlib` could not create a temporary file; a clean warnings-as-errors UBSan
build on the SSD passed the full suite and panel.

The table aggregates the four held-out cases per curve. The frozen
operation score is `16·mixed additions + 8·doublings + unit rotations`.
Preparation counts are per reused point, while online counts cover 16,384
scalars per curve.

| Curve | Mode | Point slots | Prep additions / doublings / rotations | Online additions / doublings / rotations | Score |
| --- | --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | joint window | 284 | 340 / 12 / 32 | 55,007 / 0 / 42,994 | 923,106 |
| `glv-j0-32` | signed radix | 384 | 381 / 16 / 0 | 63,008 / 0 / 31,319 | 1,039,447 |
| `glv-j0-32` | comb9 | 512 | 502 / 24 / 0 | 48,976 / 32,684 / 0 | 1,045,088 |
| `j0-56` | joint window | 497 | 595 / 24 / 56 | 114,200 / 0 / 85,552 | 1,912,752 |
| `j0-56` | signed radix | 512 | 508 / 24 / 0 | 128,318 / 0 / 64,118 | 2,117,206 |
| `j0-56` | comb9 | 512 | 502 / 56 / 0 | 114,211 / 98,219 / 0 | 2,613,128 |

The joint table uses 9,088 or 15,904 point bytes plus 654 static-map bytes.
The score is 11.67% below comb on the smaller subgroup and 26.80% below
comb on the larger one. This is an operation-model result, not a controlled
CPU speedup. Local macOS timing fields are retained as exploratory raw data
only. The score omits recoding, lookup, cache effects, and field costs beyond
its unit-rotation term; the full CPU ordering remains unknown.

[`make_joint_window4_isolated_manifest.py`](make_joint_window4_isolated_manifest.py)
freezes the new fixture, source and generated-map hashes, paired output
digests, and one binary into the serial service's alternating-order runs.
The default control is comb9; `--reference-mode endo-radix8-pos` selects the
immediate predecessor. Both manifests pass schema validation. Local macOS
preflight correctly rejects CPU/NUMA isolation certification. A qualifying
Linux host receipt is required for any wall-time ratio.

GLV decomposition, joint windows, and unit-orbit digit sets have prior art;
see the [GLV/GLS scalar-multiplication study](https://www.microsoft.com/en-us/research/publication/efficient-and-secure-algorithms-for-glv-based-scalar-multiplication-and-their-implementation-on-glv-gls-curves-extended-version/)
and [symmetric digit sets](https://eprint.iacr.org/2013/705.pdf). This is a
measured table-format experiment in this codebase, with no academic novelty
claim or one-target rho speedup claim.
