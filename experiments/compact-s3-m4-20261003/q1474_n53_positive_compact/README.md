# Q1474: matched positive N53 compact-S3 control

Q1474 asks whether Q1472's compact four-summand chained-S3 solver can recover
a relation for the **same ordinary public point** that Q1469's exact pair-table
oracle decomposed. The point was originally sampled by the seeded uniform
nonzero-scalar law, then selected for this control **after** the pair-table
result showed a four-point witness. Q1474 is therefore a known-representable
correctness and search-cost control. It is not an unbiased relation-yield
experiment or a complete IC candidate.

The exact curve is `EC1N53Ckb1hf77aab617904` (N53 is the field degree), with
actual subgroup-usable factor base `B=2,756`, `K=26` signed-Frobenius columns,
and enumerated-set digest
`cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70`.
There is no isogeny transport. The stage is
`PS1N53Ckb1fb2756PDP4hybridhb641481db49c`; `candidate_id` and `run_id`
stay null because no final relation matrix or target-DLP pipeline is wired.
Each case has its own frozen workload ID and `PS1...W...R1` stage run ID in the
[protocol](protocol.json).

The [input manifest](input_manifest.json) reconstructs all 428 raw cofactor
preimages of the Q1469 public target. It proves that the Q1469 four-point
witness sums to raw preimage 277 in the sorted full set. The Q1467 N53 W≤3
formula builder, Q1472 native solver binary, and exact factor-base selection
are reused. Three cases use the same public point:

| Case | Raw target preimages | Leaf constraints | Purpose |
| --- | ---: | --- | --- |
| `pinned_control` | witness preimage only | four witness raw x values fixed | formula and native-model correctness |
| `selected_preimage` | witness preimage only | free | search with the correct preimage supplied |
| `full_coset` | all 428 | free | search from the public point without knowing its raw preimage |

The [protocol](protocol.json) binds all source, input, binary, runtime, and
matched-pair receipt hashes. All three cases run once in order with the same
250,000 pair-admission cap, 1,000,000 SAT-conflict cap, 60-second native wall
cap, and 75-second external safeguard. Failed and capped work remains in the
record. A SAT model is accepted only after independent CNF, S3-root, base,
distinct-column, raw group-sum, and public cofactor-projection checks.

SAT propagations, conflicts, and field multiplication/squaring/inversion
calls are distinct units. Host wall time is exploratory without an isolation
receipt. No complete N131 `2^x`, natural relation yield, or verified
single-target DLP speedup follows from this stage control.

The target and input cases were constructed before the protocol was committed,
so this control is explicitly retrospective. The run protocol and source
snapshot are committed before the solver runs.

## Measured result

The [independent audit](archive_audit.json) recomputes the frozen input and
source hashes and replays the SAT model against the CNF, S3 roots, four
distinct projected columns, raw group sum, and public subgroup point.

| Case | Result | Verified relation | SAT propagations | Conflicts | Field mul / sqr / inv calls | Native process wall, exploratory |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Pinned control | SAT | 1 | 91,974 | 0 | 238 / 1,400 / 20 | 0.237 s |
| Selected preimage, free leaves | 60 s wall cap | 0 | 288,547,216 | 76,019 | 17,186,636 / 72,664,624 / 8,377 | 60.365 s |
| Full 428-preimage coset, free leaves | 60 s wall cap | 0 | 274,677,429 | 68,259 | 16,857,549 / 71,272,264 / 8,373 | 60.381 s |

The free-leaf rows record `2^28.104` and `2^28.033` exact SAT
propagations **through the caps**. Their successful-solve cost is unknown.
The pair-table oracle's matched successful target query used 1,188,334
field multiplications, 240,743 squarings, and 61 inversions; its table setup
is separate and expensive. SAT propagations and field calls have no declared
common calibration, and these wall intervals lack CPU isolation. No
controlled speedup ratio follows.

The next solver gate is an independently verified free-leaf result on this
same public N53 point, with all target-dependent attempts charged, followed
by a comparable N83 known-representable control and fresh ordinary-query
panel. A new method needs target-guided pruning or a compact pair index that
changes the measured search cost; extending the same capped run alone will
not establish a scaling law.

## Reproduce the audit

```sh
python3 experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/prepare_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1474_n53_positive_compact/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The frozen native solver runs and their full stdout, stderr, model when
available, and source-bound receipts are under `runs/`. Reproduction checks
do not rerun the 60-second cases.
