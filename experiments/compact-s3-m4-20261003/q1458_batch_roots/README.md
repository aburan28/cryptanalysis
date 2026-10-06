# Q1458: batch the exact S3 root inversions in the joint rule

Q1457 activates the exact four-leaf joint feasibility rule on N53/N83
ordinary inputs but spends many separate field inversions while enumerating
each bounded pair-output set. Q1458 retains its same 4,096 pair-candidate
cap, interleaved leaf decision policy, CNFs, public targets, one-million
conflict limit, and 60-second native wall limit. Only the joint-rule `S3`
root evaluation changes: all nonzero denominators in one root set are
inverted with Montgomery's batch trick. Pair roots and final target-link
roots still use the exact Q1420 polynomial, half-trace, and independent
`S3` substitution checks. A zero pair-output midpoint keeps the original
special-case inverse of the nonzero target.

The [frozen protocol](protocol.json) identifies the exact N53 W≤4 curve
`EC1N53Ckb1hf77aab617904` and factor base (`B=324,042`, folded
`K=3,057`), and N83 W≤6 curve `EC1N83Ckb1h876c2921cb64` and base
(`B=408,131,750`, `K=2,458,625`). It pins the enumerated-set digests,
public points, workload IDs, Q1457 baseline receipts, source and binary
hashes, and the [checked Sage runtime](sage_runtime_info.json). This is
proposal `Q1458`, `candidate_id: null`, `run_id: null`,
`isogeny: "none"`, stage code `PDP4hybrid`.

The [N53](smoke_n53.jsonl) and [N83](smoke_n83.jsonl) deterministic native
panels compare every batched root to the separate serial field oracle for
1, 32, 512, and 4,096 input pairs, including equal inputs and zero-, one-,
and two-root outcomes. On the 4,096-input panels, the serial oracle uses
6,032 N53 and 6,046 N83 inversions; the batched kernel uses two in each
case. These are exact primitive-call counts for the root kernel, not a
controlled CPU speedup or a decomposition solve. The
[partial-witness controls](control_result.json) return independently
verified four-point group relations at both degrees; their retained native
rejection and hit snapshots agree with the separate Python join.

The matched measured cells are the unpinned known-satisfiable N53 selected
preimage, the full ordinary N53 public target, and the full ordinary N83
public target. Native solver timing starts at launch on a prebuilt CNF and
ends at the first model or cap. It is a PDP stage diagnostic. The archive
audit independently replays any model on the curve and all retained joint
snapshots. A censored run gives operation counts for its search prefix, not
cost per successful decomposition. Natural relation yield, useful rank,
the complete N131 `2^x`, and challenge admission remain unknown until
ordinary successful relations and all later IC phases are measured.

## Frozen outcome

The [archive audit](verification.json) regenerated the three exact inputs,
checked every raw receipt and binary hash, and recomputed all retained
`no_chain` snapshots with the separate Python join. The
[paired operation audit](paired_comparison.json) confirms that Q1457 and
Q1458 encountered **the same retained joint-rejection states**, made the
same number of pair and final `S3` root calls on those states, and reached
the same censored outcome. It compares only the exact joint-rule calls on
those matched states; the rest of each 60-second SAT path is not fixed by
the snapshot match.

| Input | Joint checks | Serial → batched joint inversions | Joint squares saved | Outcome |
| --- | ---: | ---: | ---: | --- |
| N53 known-satisfiable unpinned slice | 2 | 18,953 → 12 | 984,932 | 60 s cap; no relation |
| N53 full ordinary target | 2 | 18,953 → 12 | 984,932 | 60 s cap; no relation |
| N83 full ordinary target | 1 | 12,168 → 6 | 997,284 | 60 s cap; no relation |

The arithmetic change is exact and large on the matched joint states. It
does **not** increase the number of admitted joint checks within the fixed
wall limits or recover the unpinned witness. Most partial states still
exceed the 4,096 pair cap: 273/275 on the N53 stress slice, 240/242 on
the full ordinary N53 target, and 404/405 on N83. The host lacks a CPU
isolation receipt, so the elapsed times do not establish a controlled
speedup. The successful-decomposition cost and complete N131 `2^x` remain
unknown. The next solver change must act on large partial pair domains or
guide branching into small domains; further arithmetic tuning alone does
not solve the observed eligibility bottleneck.

Run all Sage jobs through the accepted launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/run_controls.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/run_stage.py --case n53_known_sat_unpinned
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/run_stage.py --case n53_ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/run_stage.py --case n83_ordinary
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1458_batch_roots/verify_archive.py --check
```
