# Certified five-neighbor Eisenstein scalar reduction

The bounded pair evaluator previously reduced a public scalar through a
25-candidate search around a rounded GLV lattice point. The
[certificate producer](make_joint_pair_five_design.py) proves that
five candidates give the **global minimum** in the same L1 coordinate
metric on each exact study curve: the rounded center and its four
axial lattice neighbors.

Let `b1,b2` be the lattice basis and `R` the residual after rounding
both lattice coordinates. Then `R = s b1 + t b2` for
`|s|,|t| ≤ 1/2`. Convexity of the L1 norm gives

`||R||₁ ≤ M = max(||b1+b2||₁, ||b1−b2||₁)/2`.

For any lattice translation `V` with `||V||₁ ≥ 2M`, the triangle
inequality gives `||R−V||₁ ≥ ||V||₁−||R||₁ ≥ ||R||₁`, so the center
is at least as good. The inverse basis bounds the coefficients of
every `V` shorter than `2M`. Exhaustive integer enumeration within
those proved bounds leaves only `±b1` and `±b2` on both curves.

| Curve | `2M` | Short nonzero translations | Candidate costs evaluated |
| --- | ---: | --- | ---: |
| `glv-j0-32` | 8,873 | `±b1`, `±b2` | 5 instead of 25 |
| `j0-56` | 463,138,171 | `±b1`, `±b2` | 5 instead of 25 |

The [frozen design](joint-pair-five-design.json) retains the exact
basis, determinant, coefficient bounds, enumerated short vectors,
input hashes, and old tie order. The earlier 16,384 training scalars
per curve chose the same representative under both searches. That
agreement is a diagnostic; the bound above is the correctness
argument for every scalar on these exact curves.

The four new benchmark modes keep the same prepared point tables as
their 25-candidate controls:

| Five-candidate mode | Paired 25-candidate mode |
| --- | --- |
| `joint-pair-top-triple-five-pos` | `joint-pair-top-triple-pos` |
| `joint-pair-top-double-five-pos` | `joint-pair-top-double-pos` |
| `joint-pair-top-triple-five-wave128` | `joint-pair-top-triple-wave128` |
| `joint-pair-top-double-five-wave128` | `joint-pair-top-double-wave128` |

The [fresh fixture](joint-pair-five-inputs/inputs.json) excludes all
scalars in sixteen earlier fixtures. The
[release panel](joint-pair-five-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-five-ubsan-panel.json)
each run 80 native arms across eight 4,096-scalar cases, rotating arm
order per case. Each arm replays every group result against independent
scalar multiplication. The Python model checks 32,768 scalar
identities, 184 group decompositions, eight subgroup-base relations,
and the complete short-vector certificate. All 32,768 fresh scalars
select the same representative as the 25-candidate search. The C suite
passes 2,313,199 checks in both builds, including zero, identity,
forced fallback, and block sizes 1, 2, 7, and 128.

| Curve | Scalars | Pair additions, all formats | Serial output inversions | Wave output inversions | Five-candidate fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 16,384 | 32,724 | 16,384 | 128 | 0 |
| `j0-56` | 16,384 | 65,442 | 16,384 | 384 | 0 |

The [isolated manifest producer](make_joint_pair_five_isolated_manifest.py)
binds a same-width, same-evaluator 25-candidate control to each new
mode. Generate the manifest on a Linux benchmark host after building
and running the release panel there. Its required cgroup, CPU, and
NUMA arguments must describe a genuinely exclusive host partition;
the [runner](../../scripts/isolated_bench.py) checks this before timing.
Local CPU timings remain exploratory until a host-level isolation
receipt exists, and no controlled wall-time speedup is claimed.

Nearest-plane GLV reduction is established prior art; this exact
curve-specific cutoff certificate is an implementation result, not an
academic priority claim. The experiment measures public-scalar batch
latency, not one-target DLP recovery.
