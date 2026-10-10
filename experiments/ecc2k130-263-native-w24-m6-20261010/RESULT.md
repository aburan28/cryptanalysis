# Exact native W24 six-summand circuits on the degree-263 descendant

The Q1420 equal-size comparison now has a native descendant six-summand
Boolean circuit on the exact degree-263 codomain, paired with a source-curve
circuit on the same public point. Both use 16,772,828 actual usable base
points and the frozen one-target workload `eee7f6ee5f6b`. Checked Sage and
an independent field/curve replay certify four raw target lifts on each
curve, their transport through the oriented map, six leaf witnesses per
base, and every link of the balanced S3 tree. Two positive and six mutated
Boolean-program controls pass; CryptoMiniSat separately passes all eight
positive and eight negative native-XOR target-mux controls.

The descendant codomain has `y²+xy=x³+A*x+b_raw`. Its exact coordinate
shift `y_normalized=y_codomain+A` gives `b=b_raw+A²` and
`alpha=b^(1/4)`. The committed builder encodes `w*z=1`,
`u*(x+alpha)=alpha`, and `Tr(alpha*z)=0` for each descendant W24 leaf,
with S3 constant `b`; source leaves specialize to `alpha=b=1`. The
independent verifier evaluates these identities using separate polynomial
field arithmetic and checks their cofactor-four point projections on the
proper curve. The source and descendant lift sets agree under the verified
degree-263 map, so their four-choice target muxes refer to the same public
subgroup query.

| Exact cell on Q1420 query 0 | Source W24 prefix | Descendant-native W24 |
| --- | ---: | ---: |
| Usable base points `B` | 16,772,828 | 16,772,828 |
| Signed base columns | 8,386,414 | 8,386,414 |
| XCNF variables | 336,141 | 340,630 |
| CNF clauses | 340,070 | 339,710 |
| Native XOR clauses | 221,374 | 225,935 |
| Formula build wall, seconds | 3.219 | 3.143 |
| Formula build peak RSS, bytes | 247,218,176 | 249,479,168 |
| CryptoMiniSat 5.14.7 status | `BOUNDED_UNKNOWN` | `BOUNDED_UNKNOWN` |
| Solver exit code | 15 | 15 |
| Solver wall, seconds | 123.032 | 124.275 |
| Terminal conflicts | 753,756 | 757,597 |
| Sampled solver peak RSS, bytes | 360,693,760 | 335,478,784 |

Both solver commands used the same pinned binary SHA-256
`a3f85c3709b5e2a040bf82a4a604d1c7b9f10219bbf180a9e0f72319a2e892ac`,
one thread, `--maxtime=120`, a 150-second external wall cap, and a 4-GiB
RSS guard. Both stdout streams contain actual conflicts and terminate with
`s INDETERMINATE`; the independent [audit](runs/R1/audit.json) checks each
status against exit code, transcript hash, resource receipt, exact XCNF
header and clause counts, and the public-input/geometry chain. The source
formula SHA-256 is
`1c6fd5241c097134f11fe4e82052289d6b064e4d6e9fddbf3530dddad4150f2e`;
the descendant formula SHA-256 is
`f9eef81faa47320985cfa67daed29ec561eb3431703c44a4fe93ce3aa867c417`.
Lossless deterministic gzip archives retain both exact native-XOR inputs.
The preregistered 300-second and 4-GiB *external* guard for formula
construction was not invoked: the two direct build commands completed in
3.219 and 3.143 seconds and reported 247,218,176 and 249,479,168 bytes
peak RSS, respectively. Those observed bounds are recorded, while external
construction-cap enforcement remains a protocol deviation. The solver
attempts did use their separate external wall and RSS guard.

The descendant formula adds 4,489 variables and 4,561 native XORs while
using 360 fewer CNF clauses. Its terminal conflict count is 0.51% above the
source cell under the fixed cap. These are single-query construction and
solver diagnostics on an unisolated host. The row status is censored;
verified relation yield, novel rank, target-dependent descent, and the
paired rho ratio remain `null` in the [audit](runs/R1/audit.json). This
comparison therefore selects neither W24 geometry for a downstream IC
pipeline.

The next exact experiment should complete the finite S3 chart and decode
point signs on positive controls with cancellations or an intermediate at
infinity. It should then compare that chart-complete circuit with a
projective group-law encoding on the same frozen Q1420 point and resource
envelope, measuring formula size, verified natural relations per query, and
new rank. Extending the current 120-second cap to additional public points
before either circuit returns a verified relation would spend the budget on
censored cells without resolving the geometry question. The source and
transported policies, like the native and pullback policies, have paired
group-sum membership under the verified isogeny; any subsequent difference
between members of a pair must be attributed to encoding or charged map
work, not base cardinality.

The first Sage producer attempt ended with a configuration-key lookup error
after 23.786 seconds, before writing geometry outputs. Its
[`PRODUCER_FAILURE` receipt](runs/R1/failed_preflight.json) and the one-key
correction are committed. The successful producer used the checked
repository Sage runtime and took 20.345 seconds with 339,509,248 bytes peak
RSS; the independent replay took 18.706 seconds. The [producer](runs/R1/runtime-info.json)
and [verifier](runs/R1/runtime-info-verifier.json) runtime receipts bind the
accepted Sage build. These setup and correctness times are outside any
single-target online IC interval.

To replay from the repository root, use the checked Sage launcher and the
committed inputs. Use fresh output paths because the scripts refuse to
overwrite evidence:

```sh
./sage --runtime-info > /tmp/q1420-native-runtime.json
./sage -python experiments/ecc2k130-263-native-w24-m6-20261010/produce_geometry.py \
  --runtime-info /tmp/q1420-native-runtime.json --out-dir /tmp/q1420-native-geometry
cmp /tmp/q1420-native-geometry/lifts.json \
  experiments/ecc2k130-263-native-w24-m6-20261010/runs/R1/lifts.json
cmp /tmp/q1420-native-geometry/geometry_controls.json \
  experiments/ecc2k130-263-native-w24-m6-20261010/runs/R1/geometry_controls.json
./sage -python experiments/ecc2k130-263-native-w24-m6-20261010/verify_geometry.py \
  --runtime-info /tmp/q1420-native-runtime.json --out /tmp/q1420-native-verification.json
python3 experiments/ecc2k130-263-native-w24-m6-20261010/audit.py \
  --out /tmp/q1420-native-audit.json
```

The frozen [protocol](PROTOCOL.md), [configuration](CONFIG.json),
[lifts](runs/R1/lifts.json), [positive controls](runs/R1/geometry_controls.json),
[Boolean controls](runs/R1/boolean_controls.json),
[mux controls](runs/R1/mux_controls/receipt.json), and full
[solver receipts](runs/R1/source_m6_pilot.json) plus
[descendant receipt](runs/R1/descendant_native_m6_pilot.json) supply the
methods and raw evidence. `candidate_id` remains `null` until a complete
relation collection, final matrix, and target-descent policy is specified.
