# Q1457: admit 4,096 pair completions in the joint-tail solver

Q1455's exact four-leaf joint feasibility rule passes both partially freed
witness controls, but its original 256-pair N53 and 1,024-pair N83 caps admit
no observed unpinned partial state. Q1456 independently counted the exact
sparse completion products in short repeats on the same CNFs. A cap of 4,096
would admit six distinct states in each N53 prefix and one in the N83 prefix.

The [frozen Q1457 protocol](protocol.json) tests that cap change. It reuses
Q1455's native binary, CNFs, target lists, interleaved four-leaf decision
policy, one-million-conflict limit, and 60-second native wall limit. The
inputs include one unpinned known-satisfiable N53 selected-preimage slice,
one full ordinary N53 public target, and one full ordinary N83 public target.
The selected-preimage slice is a correctness stress case, not a sample of
natural relation yield. The full ordinary cells remain only two solver
attempts, and a successful relation would still need independent group
replay and broader yield/rank measurement.

This is proposal `Q1457`, `candidate_id: null`, `run_id: null`,
`isogeny: "none"`, with stage code `PDP4hybrid`. The exact N53 W≤4 base has
curve ID `EC1N53Ckb1hf77aab617904`, actual usable `B=324,042`, and folded
`K=3,057`; the N83 W≤6 base has `EC1N83Ckb1h876c2921cb64`,
`B=408,131,750`, and `K=2,458,625`. The protocol retains both enumerated
base-set digests and workload IDs. No `IC1` candidate is assigned because a
complete IC pipeline has not been specified or measured.

The [pre-run controls](control_result.json) both return independently
verified four-point relations at the 4,096 cap. All retained native
rejection/hit snapshots were recomputed with the separate Python join. The
[checked Sage runtime receipt](sage_runtime_info.json) was captured before
the measured cells. Solver wall time here starts at native process launch on
an already materialized CNF and ends at its first model or cap. It is an
exploratory PDP stage diagnostic, not a full one-target IC solve or an
isolated-host speedup. The eventual archive audit replays any model on the
curve and recomputes all retained joint-rule snapshots.

The complete N131 `2^x` and the challenge admission remain unknown until
ordinary-query relation yield, useful rank, final matrix costs, target
descent, and recovery checks can be charged in consistent units.

## Frozen outcome

The [three-cell archive audit](verification.json) regenerated each input,
checked all source and workload hashes, and independently replayed every
retained `no_chain` snapshot with the separate Python join. All three solver
attempts reached their 60-second native wall cap without a model or relation.

| Input | Partial states / cap skips | Joint checks / sound rejections | Native field mul / sqr / inv calls | Peak child RSS |
| --- | ---: | ---: | ---: | ---: |
| N53 known-satisfiable unpinned slice | 407 / 405 | 2 / 2 | 708,056 / 4,315,240 / 50,978 | 427,425,792 bytes |
| N53 full ordinary target | 300 / 298 | 2 / 2 | 708,027 / 4,315,076 / 50,976 | 314,900,480 bytes |
| N83 full ordinary target | 404 / 403 | 1 / 1 | 285,737 / 2,589,138 / 20,534 | 271,433,728 bytes |

The cap change makes the exact joint rule fire on both ordinary targets,
where Q1455 recorded zero such checks. It does not yield a relation in the
frozen interval. The branch path changes after a learned rejection, so the
Q1456 prefix's 6/6/1 prospective admissions are not a prediction of how
many checks the new runs must reach. Most new partial states remain over
cap. In the N53 ordinary run, the two joint checks alone account for
252,339 field multiplications, 1,729,118 squares, and 18,953 inversions;
the full native run uses the larger counts in the table. These are exact
primitive-call counts for a **censored search prefix**, not cost per
successful decomposition. The host has no isolation receipt, and no
controlled wall-time speedup follows from the matched run.

The next solver milestone is a verified relation from the unpinned
known-satisfiable N53 slice, then ordinary N53/N83 measurements on the same
curve/base/target records. The current evidence points to an eligibility
problem: the solver needs sound reasoning while pair domains are much larger
than 4,096, or a decision policy that reaches small domains with less root
enumeration. Raising the cap again without reducing work per check would
consume substantially more arithmetic while leaving most observed states
untouched.

Run all Sage checks and jobs through the accepted launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/run_stage.py --case n53_known_sat_unpinned
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/run_stage.py --case n53_ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/run_stage.py --case n83_ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1457_joint_cap4096/verify_archive.py --check
```
