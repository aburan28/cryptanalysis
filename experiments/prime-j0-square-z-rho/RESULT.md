# Fresh one-target square-Z rho result

The square-Z rho implementation, tests, independent affine target
generator, checker, strict isolation manifest generator, and protocol
were frozen in `1fa76255`. A new public point was generated and frozen
in `a73063eb` before any solver invocation. Each invocation started
with an empty distinguished-point table and used the same public point
`(1214753992, 1398575280)` and seed `4102642139449210755`.

Both serial Release and UBSan panels passed their frozen six-arm order:
generic reference, regular steered batch, square-Z steered batch,
square-Z steered batch, regular steered batch, generic reference. Every
arm recovered scalar `513690` and independently replayed it to the
public target. The panels retain every raw trial, return code, source
and binary hashes, timing, counters, and replay result.

| Checked item | Generic reference | Regular steered | Square-Z steered |
| --- | ---: | ---: | ---: |
| Equivalent rho group operations | 5,066 | 5,066 | 5,066 |
| Distinguished-point table entries | 192 | 192 | 192 |
| Table evaluations / restarts | 8 / 4 | 8 / 4 | 8 / 4 |
| Prepared bytes | 0 | 1,104 | 1,104 |
| Evaluation τ steps | 0 | 156 | 156 |
| Square-Z τ steps | 0 | 0 | 156 |
| Evaluation rotations | 0 | 30 | 30 |
| Free gauge transitions | 0 | 30 | 30 |

The two steered arms also match preparation counts, mixed additions,
batch and restart inversions, recoding attempts, pair scores, and
scalar output. The new arm substitutes one field square for one field
multiplication on each of its 156 nonidentity τ steps, with modular
additions and halving. This is a source-level operation model. In the
current backend, `ca_mont_sqr` and `ca_mont_mul` both use the same
Montgomery reduction of a 128-bit product. There is no specialized
square kernel, and the extra additions and modular half make this
substitution an uncertain performance tradeoff.

Release `online_ms` in frozen order was `0.552, 0.567, 0.502, 0.517,
0.505, 0.557`. UBSan gave `4.705, 4.655, 4.547, 4.292, 4.645, 4.805`.
These short runs were on a host without verified CPU and NUMA isolation;
their timing is exploratory. Both raw panels set `cpu_speedup_claim:
null` and `isolation_receipt: null`. The one-target result establishes
correctness and an unchanged rho trajectory, not a controlled CPU
speedup. The separate post-solve replay timing is recorded in each row.

The Release `CA_WERROR=ON` build passed all 16 CTest tests; UBSan
`curve` and `joint_tau` tests passed. The candidate remains opt-in.
The strict serial isolated-run manifest generator in this directory
can bind the same frozen target to a qualifying host. Automatic
routing and academic novelty remain open.
