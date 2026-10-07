# Q1477: one previously unseen N53 target, timed query through replay

Q1477 measures target recovery for the **explicit N53
pair-table comparator**. It reuses Q1473's independently verified 26
factor-base logarithms and constructs one complete Q1468-style cross-column
pair table before the target-dependent clock. A new public target was selected
from the precommitted uniform scalar law after the [design protocol](design_protocol.json)
was pushed in PR #418. The native solver received the public point, never its
fixture scalar. The [full protocol](protocol.json), source and binary hashes,
target and log files, checked Sage runtime, and [pre-run validation](input_validation.json)
were committed before the [run](runs/primary/receipt.json).

| Identity | Frozen value |
| --- | --- |
| Curve | `EC1N53Ckb1hf77aab617904` |
| Factor base | 2,756 actual subgroup points; 26 folded columns; digest `cf9bb366bb3cd429693e6891d6b0619e8f942a86f3a8308f737795cbaf8b2d70` |
| PDP stage | `PS1N53Ckb1fb2756PDP4mitmhb828dff20631` |
| One-target workload | `a4f7b6242393` |
| Stage run | `PS1N53Ckb1fb2756PDP4mitmhb828dff20631Wa4f7b6242393R1` |

This remains proposal `Q1477`, with `candidate_id: null`, `run_id: null`,
and `isogeny: "none"`. Q1469 and Q1473 produced the reusable logs across
archived panels, not one fully specified, contiguous IC precomputation run.
This is not an `IC1` candidate or a compact chained-`S3` result.

## Measured one-target result

The [independent audit](audit_result.json) replayed the frozen target,
deterministic shift stream, four distinct factor-base columns, the witness
group sum, every base-point log, and the recovered scalar. The target's
discrete log is **7,916,229,610,986** modulo the frozen prime subgroup
order. Ten complete pair-table queries were absent; the eleventh yielded
one verified relation. There were no timeouts or censored queries. All
eleven attempts belong to this one target; `1/11` is not an estimate of
natural relation yield.

| Exclusive target-dependent phase | Native wall | Field mul | Field sqr | Field inv |
| --- | ---: | ---: | ---: | ---: |
| Query generation and controller overhead | 0.001983 s | 6,340 | 34,022 | 634 |
| Four-point decomposition, including ten failures | 45.685586 s | 184,930,528 | 37,441,268 | 9,031 |
| Relation check | 0.000009 s | 30 | 159 | 3 |
| Target descent and scalar recovery | 0.000000 s | 0 | 0 | 0 |
| Scalar replay | 0.000198 s | 630 | 3,381 | 63 |
| **One-target online total** | **45.687777 s** | **184,937,528** | **37,478,830** | **9,731** |

The [raw native transcript](runs/primary/stdout.ndjson) retains every
attempt, shift, queried point, status, witness when found, phase cost, and
primitive count. The phase wall intervals sum **exactly** to the native
online interval; loop and controller overhead are charged to query
generation. The 3.580-second table build and its 18,279,700 field
multiplications are target independent and excluded from online time.
Peak child RSS was 91,209,728 bytes. The external 49.280-second process
interval includes launch, loading, and table setup and is supplementary.

The wall times are exploratory because the host has no isolation receipt.
There is no paired same-point rho run, so controlled online speedup is
`null`. The archived Q1469/Q1473 relation collection and matrix costs are
available separately, but their intervals do not form a complete cold-start
run. The native loader also checked the target's subgroup membership before
the online clock. That target-dependent validation is inside the reported
aggregate pre-clock setup interval but was not timed separately. Thus
45.688 seconds is the exact query-through-replay interval, **not** a fully
charged target-from-input online time under the strict single-target
contract. A future primary timing run must move that check inside the
online interval or time it separately. The explicit N131 pair table alone
needs about `2^64.222` entries;
Q1477 does not supply an N83 compact-solver cost, natural N83 yield, or a
complete N131 `2^x`. The challenge gate remains closed.

## Reproduce the custody and mathematical checks

```sh
python3 experiments/compact-s3-m4-20261003/q1477_n53_online_target/make_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1477_n53_online_target/build.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1477_n53_online_target/validate_inputs.py --check
python3 experiments/compact-s3-m4-20261003/q1477_n53_online_target/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1477_n53_online_target/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

The checks replay archived evidence; they do not launch a second target run.
