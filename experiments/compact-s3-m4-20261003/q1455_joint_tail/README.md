# Q1455: bounded joint pair-output join with unfixed intermediates

Q1455 tests an exact four-leaf feasibility rule for the compact chained-`S3`
point-decomposition solver. Each partial leaf has fixed normal-basis bits and
an unfixed suffix, under the exact sparse-x weight bound. If each pair's
completion product is at most the declared cap, the rule enumerates **all**
allowed nonzero x coordinates, computes both sets of `S3` pair-output roots,
and joins those sets through the selected target's final `S3` link. Neither
pair intermediate is fixed in advance. The result is one x-only chain,
`no_chain`, or `skipped` when a pair domain exceeds the cap.

`no_chain` is a sound rejection of that partial four-leaf assignment because
the bounded domains were enumerated in full. A returned x-only chain can
include non-lifting points or the wrong signs; it is a solver candidate until
the exact curve, subgroup, base membership, distinct signed-Frobenius columns,
and public-target sum are independently replayed. The rule imposes no
factor-base or lift filter in its feasibility test, making it a safe
superset of valid relations.

The [frozen control protocol](protocol.json) names the exact N53 W≤4 base
(`EC1N53Ckb1hf77aab617904`, `B=324,042`, `K=3,057`) and N83 W≤6 base
(`EC1N83Ckb1h876c2921cb64`, `B=408,131,750`, `K=2,458,625`), their
enumerated-set digests, and the archived group-verified witness inputs. N53
uses the known-satisfiable ordinary target preimage 201; N83 uses a planted
witness control. This is proposal `Q1455`, `candidate_id: null`,
`run_id: null`, and `isogeny: "none"`, with stage code `PDP4hybrid`.

The first correctness gate compares the join with independent full-field
`S3` evaluation on every complete four-leaf and nonzero-target N3 case,
plus deterministic partial N3 states. It then frees four normal-basis bits
per archived leaf at N53 and N83, with each pair's completion count bounded
by 256, and checks that the previously verified witness remains recoverable.
These are correctness controls, not ordinary-query performance, natural
relation yield, or a complete N131 work estimate.

The [native stage protocol](native_protocol.json) freezes a CaDiCaL external
propagator built on the archived compact-`S3` CNF. It decides the target
selector first, then interleaves leaf bits across both pairs. When all four
leaves remain partial and neither intermediate is fully fixed, it applies
the exact bounded join. A `no_chain` result emits a clause guarded by every
currently fixed leaf bit and the selected target. The stage records eligible
states, cap skips, rejections, output-set sizes, field calls, wall time,
memory, and sampled guards for independent replay. Its two partial-witness
controls were checked before freezing: both return group-verified relations,
and the Python join independently confirms sampled native rejections and
hits. The frozen run order adds an unpinned known-satisfiable N53 slice and
full ordinary N53/N83 public-target cells.

The N131 challenge remains closed until ordinary N53/N83 costs, natural
yield, useful rank, and the remaining IC phases support a complete work
estimate.

Use the accepted Sage launcher for all Sage work:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1455_joint_tail/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1455_joint_tail/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1455_joint_tail/build_native.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1455_joint_tail/freeze_native_protocol.py --check
```
