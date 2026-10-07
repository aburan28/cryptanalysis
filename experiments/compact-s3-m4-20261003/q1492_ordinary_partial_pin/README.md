# Q1492: ordinary N53 partial-pin search localization

Q1491 proved that Q1482's exact ordinary N53 CNF accepts a verified
four-point relation when its leaf, midpoint, and target-selector variables
are pinned. Q1492 keeps the same public target, CNF body, native solver,
and exact Q1481 factor base while leaving **all four leaves unpinned**.
Its [pre-registered design](design_protocol.json) tests four partial-pin
cells to localize search cost. This is an oracle-assisted diagnostic, not
a natural relation-yield sample.

The exact curve is `EC1N53Ckb1hf77aab617904`; the base has 430,360
usable subgroup points and 4,060 folded columns, with set SHA-256
`42e746657e39ea4d07aafc873110339e314cd685b3bd8493eb3c60aed1354ba5`.
Q1492 remains a proposal with `candidate_id: null`, `run_id: null`, and
`isogeny: "none"`. The [frozen protocol](protocol.json) binds the Q1491
SAT control, Q1490 witness, source, checked Sage runtime, exact pin
policies, 60-second native cap, and 1,000,000-conflict cap before the runs.

| Cell | Pins | Status | Domain builds | S3 roots | Direct right-S3 evaluations |
| --- | ---: | --- | ---: | ---: | ---: |
| Target and both mids | 115 | 60 s cap | 2,080 | 14,450,525 | 0 |
| Target and second mid | 62 | 60 s cap | 2,072 | 14,401,636 | 0 |
| Target and first mid | 62 | 60 s cap | 2,080 | 14,450,525 | 0 |
| Target only | 9 | 60 s cap | 1 | 8,193 | 143,401,600 |

All four [run receipts](runs) preserve zero verified relations, SAT
propagations and conflicts, field mul/sqr/inv counts, root calls, peak RSS,
raw stdout/stderr, source hashes, and exploratory process time. The
target-only cell selected the **known satisfiable** preimage 141 but still
made 143 million right-S3 evaluations without right support in its visited
search states. The three midpoint-pin cells spent their capped intervals
repeatedly constructing partial left-pair domains, with no exact joint
check admitted. These failures are censored search prefixes. Q1491's SAT
model proves the target and pinned mids are compatible with a relation.

The source-level next improvement is to let the partial-domain builder
filter possible first midpoints against the current first-midpoint
assignment before mapping them through the final S3 link. The current
Q1480 domain cache key and guard omit first-midpoint bits, so a sound
variant must include those bits in both the cache key and every learned
clause guard. An exact small-field control and the Q1491 witness must
pass before comparing ordinary search costs. Q1492 gives no successful
unpinned PDP cost, N83 ordinary relation, natural yield, novel rank, or
complete N131 `2^x`.

Reproduce the custody and replay checks with the repository launcher:

```sh
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1492_ordinary_partial_pin/freeze_protocol.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1492_ordinary_partial_pin/run_partial.py --cell target_plus_both_mids --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1492_ordinary_partial_pin/run_partial.py --cell target_plus_second_mid --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1492_ordinary_partial_pin/run_partial.py --cell target_plus_first_mid --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1492_ordinary_partial_pin/run_partial.py --cell target_only --check
```
