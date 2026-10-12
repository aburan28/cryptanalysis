# Q1516: independent replay of the first four Q1509 N83 blocked pairs

This run independently reproduces **the first four of Q1509's eight distinct
first pairs** on each frozen ordinary N83 point. Q1509 had already extended
the exact 166-bit blocked-pair chain to eight pairs before Q1516 began. The
third pair is exact-base-usable on both points; its four signed complements
per point were exhaustively scanned against the W≤5 base and again produced
zero second-pair hits. The fourth pair on each point failed the exact-base
leaf filter. Q1516 is a replication and capacity preflight record.

| Curve `EC1N83Ckb1h876c2921cb64`, W≤5 base B=30,977,592, K=186,612 | Selected | Holdout |
| --- | ---: | ---: |
| Third distinct pair, branch | 28 | 28 |
| Third pair, CNF+XOR calls | 54,482 | 56,806 |
| Third pair, exact-base usable | yes | yes |
| Third pair, four full signed scans | 4; zero hits | 4; zero hits |
| Fourth distinct pair, branch | 29 | 29 |
| Fourth pair, CNF+XOR calls | 54,141 | 56,465 |
| Fourth pair, exact-base usable | no | no |

These four replayed first-pair searches charged **221,894 CNF+XOR calls**, or
**110,947 per usable pair**. The eight full signed scans charged
**619,551,840 = 2^29.207 batch field multiplications**, excluding inversion
internals, setup, keying, leaf checks, and SAT calls. Combining Q1508 and
Q1516 within this replay gives four distinct pairs per point, four
exact-base-usable pairs in total, sixteen complete signed scans, and zero
second-pair hits. Q1509's earlier depth sweep already covers eight pairs per
point and 24 complete signed scans. Q1508's searches charged 218,630
CNF+XOR calls for two usable pairs, so this replay did not improve
usable-pair cost on these inputs.

The first fourth-pair replay attempt was rejected before search because this
run's initial WDSat binary allowed at most 65,710 variables while three exact
blocks need 65,870. The [failed preflight receipt](runs/preflight_max_id_selected_round3/receipt.json)
and stderr are preserved. A rebuilt binary raises `__MAX_ID__` to 66,040 and
`__MAX_EQ__` to 193,000; its [build receipt](build_receipt.json) binds the
parent source, config and binary hashes. Q1509 had independently raised its
own capacity for eight pairs. Both Q1516 fourth-pair searches reached their
first-pair markers. The exact block systems, solver streams, base-leaf
replays, signed complements, and scanner outputs are retained under [runs](runs).

For the exact N131 W≤6 base, the same complete four-sign scanner costs
**65,596,347,880 = 2^35.933 batch multiplications per usable first pair**.
That scanner stage alone is **5.333 bits above** the prior `2^30.6`
per-decomposition allowance for a `2^61` full-solve budget. This transfer
assumes a complete scan; it excludes first-pair search, failed pairs, rank
novelty, final matrix work, and target handling. The conditional Q1506
independent-first-pair model remains `2^123.289` batch multiplications for
expected rank supply. The fully charged N131 solve exponent remains unknown.

This is a `Q1516` stage proposal, `PDP4hybrid`, `isogeny: "none"`.
`candidate_id` and `run_id` are null because this replay does not
specify a complete pipeline. The host has no isolation receipt, so wall times
in run records are exploratory. The [protocol](protocol.json),
[result](result.json), [accounting](analysis.json), and [read-only validator](validate.py)
freeze the exact selected and holdout inputs, source identities, statuses,
resource caps, and counted work. Validate with:

```sh
env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_q1513_exact_complement_audit/validate.py
```

Q1517 subsequently pruned completed first pairs inside one WDSat traversal,
reproduced the full Q1509 eight-pair order, and halved that first-pair
search's CNF+XOR calls on both frozen ordinary N83 points. The next solver
gate is a target-conditioned or indexed complementary-pair lookup that
produces independently verified ordinary relations and rank increments on
matched N53 and N83 inputs. The existing N53 complete `PDP4mitm`
single-target run provides an end-to-end control; its operation-count
boundary is separate from this N83 hybrid stage.
