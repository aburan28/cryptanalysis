# Q1480: midpoint-conditioned pair feasibility on exact dense bases

Q1480 replaces Q1479's broad exact pair-root join with a target-conditioned
support check. After the selected target preimage and second midpoint are
fixed, the solver derives at most two first-midpoint roots from the final
`S3` link. It tests the right partial leaf pair against its fixed midpoint
and the left pair against those roots by direct `S3` evaluation. Each side
admits at most 16,384 weight-valid pair completions. Unsupported states
receive clauses guarded by every assigned selector, leaf and midpoint bit.
Q1479's earlier partial first-pair domain rule remains active. The method
uses three compact `S3` links and does not construct `S5` or a pair table.

The [design](design_protocol.json) was published in commit `23c4c16f` before
implementation. The [source-bound protocol](protocol.json), native binary,
exact archived inputs, checked Sage runtime and direct small-field control
were published in commit `08d49a51` before the six runs. The
[archive audit](archive_audit.json) independently replays every SAT model to
its public subgroup point and checks all six raw receipts.

Q1480 is a `PDP4hybrid` **proposal**, with `candidate_id: null`, `run_id:
null`, and `isogeny: "none"`. The Q1476 pinned controls use their own smaller
bases and stage IDs. The four Q1438 cells below reuse the exact production
bases and public points, with no newly selected target.

| Degree | Exact curve ID | Production base | Actual usable `B` | Folded `K` | Enumerated-set SHA-256 |
| ---: | --- | --- | ---: | ---: | --- |
| 53 | `EC1N53Ckb1hf77aab617904` | W≤4 | 324,042 | 3,057 | `9e12afb51aaf2bbf47640554ce88b3653903375c33489ce8b1e07abe6a649cae` |
| 83 | `EC1N83Ckb1h876c2921cb64` | W≤6 | 408,131,750 | 2,458,625 | `c1ee6d1064935976fc0d3e479f895fe4832722b5991ba148a6d6cb003b76330d` |

The production stage IDs are
`PS1N53Ckb1fb324042PDP4hybridhb24c21e0f0a4` and
`PS1N83Ckb1fb408131750PDP4hybridhfa81d8ce086d`. Each measured case
appends its unchanged Q1438 workload ID and `R1`; the pinned correctness
controls have separate Q1476-derived `PS1` IDs. The protocol records every
field, curve, base, input, source, binary, runtime and workload digest.

## Validation and frozen result

The independent `F_8` check evaluates each `S3` polynomial directly. It
checked all 5,832 partial pair/midpoint states, 1,102,248 partial left-pair
guards, 72,576 complete four-leaf/target/midpoint cases, and 4,096 paired
partial guards. Its 3,708 sampled rejections excluded no valid x-only chain.
All four archived control models also replay as verified public four-point
relations through the separate Q1476 and Q1438 verifiers. Q1438's
free-partner controls retain their known first leaves and both pair
midpoints; they do not measure an unpinned ordinary solve.

| Frozen case | Status | Verified relations | SAT propagations | Field mul / sqr / inv | Direct right / left `S3` evaluations | Conditioned checks / right supports |
| --- | --- | ---: | ---: | --- | --- | --- |
| N53 Q1476 sorted pinned | SAT | 1 | 83,088 | 209 / 1,236 / 18 | 0 / 0 | 0 / 0 |
| N83 Q1476 sorted pinned | SAT | 1 | 443,653 | 227 / 1,926 / 18 | 0 / 0 | 0 / 0 |
| N53 Q1438 free partner | SAT | 1 | 51,775 | 179,302 / 494,460 / 30 | 9,324 / 46 | 46 / 46 |
| N83 Q1438 free partner | SAT | 1 | 126,554 | 168,332 / 738,970 / 30 | 6,364 / 46 | 46 / 46 |
| N53 Q1438 ordinary | 60 s cap | 0 | 22,633,945 | 531,403,553 / 133,737,059 / 9,257 | 132,805,860 / 0 | 35,567 / 0 |
| N83 Q1438 ordinary | 60 s cap | 0 | 103,562,890 | 279,634,885 / 71,872,645 / 19,181 | 69,847,082 / 0 | 35,598 / 0 |

Every ordinary conditioned check found no right-pair support at its tested
partial state, so no ordinary check reached a left-pair evaluation. The
Q1438 baseline on the same N83 W≤6 input used 856,544,631 affine XORs
and 2,343,613 field multiplications under its 60-second cap; Q1480 uses a
different solver and spends many more field multiplications while also
remaining censored. The host lacks an isolation receipt, and these are
fixed-cap operation vectors, not successful-solve costs or CPU speedups.
The N53 ordinary point has a known representation on an old subset; the N83
ordinary point's representability was not proved beforehand. Neither
ordinary query produced a verified relation.

These two ordinary rows do not estimate natural relation yield, novel rank,
cost per useful row, or successful N53-to-N83 scaling. A complete degree-131
`2^x` remains `null`; challenge dispatch remains closed. The result suggests
that fixing a midpoint and testing small local pair windows is the wrong
place to spend a per-query budget. A successor needs to constrain broad
right-pair and target support together without visiting local windows one
at a time. This observation is specific to the frozen Q1480 policy and cap,
not a lower bound on every compact solver.

Q1425 already tested exact reverse roots after one leaf and a midpoint were
fixed, and Q1436 tested affine feasibility while a pair was still partial;
their ordinary cells also censored. A successor must address the global
target-linked support question those checks leave open, rather than only
move the same fixed-midpoint test to a different decision depth.

## Reproduce custody checks

```sh
python3 experiments/compact-s3-m4-20261003/q1480_conditioned_join/build.py --check
python3 experiments/compact-s3-m4-20261003/q1480_conditioned_join/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1480_conditioned_join/validate_conditioned.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1480_conditioned_join/audit.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/build_work_ledger.py
```

These checks replay the archived evidence; they do not overwrite the six
native runs. Each run preserves its raw stdout/stderr, source-bound receipt,
any SAT model, exact operation counts, wall interval and peak child RSS.
