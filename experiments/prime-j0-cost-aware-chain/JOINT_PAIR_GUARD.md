# Certified center guard for Eisenstein pair recoding

The five-neighbor recoder is globally optimal in L1 on the two exact
study lattices. This candidate accepts the rounded center without
search when two strict coordinate inequalities prove that the center
beats all four axial neighbors. All other scalars use the unchanged
five-neighbor search.

Let the rounded residual be `R=(x,y)`, with basis vectors
`b1=(a,b)` and `b2=(c,d)`. Here `|b|>|a|` and `|c|>|d|`. For either
sign of `b1`, the triangle inequality gives

`||R ± b1||₁ ≥ |x|−|a|+|b|−|y| > ||R||₁`

when `2|y| < |b|−|a|`. Similarly, both signs of `b2` lose when
`2|x| < |c|−|d|`. The [five-neighbor certificate](JOINT_PAIR_FIVE.md)
excludes all other lattice translations. Strict inequalities preserve
the earlier recoder's tie order.

| Curve | Horizontal threshold | Vertical threshold | Guard accepted in 16,384 training scalars |
| --- | ---: | ---: | ---: |
| `glv-j0-32` | 3,275 | 952 | 2,147 |
| `j0-56` | 231,499,057 | 231,359,000 | 16,362 |

The [frozen design](joint-pair-guard-design.json) records the exact
bases, thresholds, parent certificate, and training fixture hashes.
The acceptance counts are algorithmic diagnostics, not runtime
measurements. The [fresh fixture](joint-pair-guard-inputs/inputs.json)
excludes every scalar in seventeen earlier fixtures. The
[release panel](joint-pair-guard-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-guard-ubsan-panel.json)
each check 112 native arms: four guard modes, their four five-neighbor
controls, four original 25-neighbor controls, a packed plane, and
fixed comb9. Each arm independently replays all 4,096 outputs per
case. The Python model checks 32,768 scalar identities, 184 group
decompositions, eight subgroup-base relations, the exact guard
inequalities, and the complete short-vector certificate. The C suite
passes 2,313,655 checks in both builds, including zero, identity,
forced fallback, and wave blocks of 1, 2, 7, and 128 lanes.

| Curve | Fresh scalars | Guard accepts | Pair additions, all formats | Serial output inversions | Wave output inversions | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 16,384 | 2,199 | 32,724 | 16,384 | 128 | 0 |
| `j0-56` | 16,384 | 16,363 | 65,465 | 16,384 | 384 | 0 |

All paired output digests, group additions, rotations, and unit
actions match. The five-neighbor control and guarded candidate share
the same center-based fallback core, so the comparison isolates the
guard decision. The guard modes use the same prepared points and
online scratch as their corresponding controls. The
[isolated manifest producer](make_joint_pair_guard_isolated_manifest.py)
validates locally for all four same-width serial or wave pairs, each
with eight cases and 229 custody artifacts. Generate a fresh native
panel and manifest on the Linux benchmark host. A controlled CPU
wall-time claim requires a host-level isolation receipt; the local
timing fields are exploratory. This is a public-scalar batch-latency
study, not a one-target DLP speedup claim.
