# Q1517: in-process first-pair pruning saves about one bit of N83 search work

Pruning each completed first-pair assignment inside one WDSat traversal
reproduced **all eight distinct Q1509 first pairs in the same order** on each
frozen ordinary N83 public point. Retaining the solver's search state avoided
restarting through the common prefix eight times. This reduced the counted
CNF+XOR calls to the eighth pair by **1.995×** on the selected point and
**2.058×** on the holdout.

| Exact curve `EC1N83Ckb1h876c2921cb64`, W≤5 base B=30,977,592, K=186,612 | Selected `2eb250a29072` | Holdout `394256b9f901` |
| --- | ---: | ---: |
| Distinct first pairs, exact sequence matched | 8 | 8 |
| Exact-base-usable pair indices | 0, 2, 6 | 0, 2, 6 |
| Q1509 restarted CNF+XOR calls | 434,996 | 453,588 |
| Q1517 in-process CNF+XOR calls | **218,096** | **220,420** |
| Saved calls / work bits | 216,900 / **0.996** | 233,168 / **1.041** |
| Calls per exact-base-usable pair | 72,699 | 73,473 |
| Process status | `EIGHT_PAIRS_TERMINATED` | `EIGHT_PAIRS_TERMINATED` |
| Peak child RSS | 922,910,720 B | 923,992,064 B |

The runner uses Q1509's exact N83 XCNF and frozen phase-two branch order.
At the earliest recursive node where all 166 first-pair coordinate bits are
assigned, it records the pair and returns a search failure for that branch.
Backtracking then advances to the next distinct pair. It stops with a
dedicated exit code after eight pairs. The [builder](build.py) applies this
small change to the source-pinned Q1509 WDSat tree; the [build receipt](build_receipt.json)
binds parent and patched source, config, binary, and compiler output. The
[run result](result.json) retains both process streams, exact call counters,
wall/CPU, peak RSS, status, and all eight 166-bit assignments.

The [validator](validate.py) checks every emitted assignment against the
archived Q1508/Q1509 eight-pair sequence, source and binary hashes, the
frozen XCNF bytes, and the earlier exact base and signed-complement scan
receipts. Indices 0, 2, and 6 are exact-base-usable on both points. Their
24 complete signed scans in Q1509 found zero second-pair hits. Thus this
change improves first-pair enumeration cost, while the measured second-pair
scan work and ordinary relation yield for these points remain as Q1509
recorded them. The host lacks an isolation receipt, so wall times are
exploratory; the claimed improvement is in the named CNF+XOR call count.

The separate Q1516 run reproduced Q1509's first four pairs. Q1509's
eight-pair archive is the baseline for this comparison. Q1517 is a
`PDP4sat` stage proposal with `isogeny: "none"` and null candidate/run IDs.
The N131 W≤6 four-sign full-scan transfer remains `2^35.933` batch field
multiplications per usable first pair, and Q1506's independent-first-pair
rank-supply model remains `2^123.289` in that unit. Those scan costs dominate
the saved first-pair SAT calls under the stated models. A fully charged N131
solve exponent remains unknown because this stage has no new verified
relation or rank increment, and the final matrix and target phases are not
measured for a corresponding complete candidate.

The next improvement should keep this in-process enumeration and replace its
complete second-pair scan with a target-conditioned or indexed lookup.
Measure verified ordinary relation yield and rank novelty on matched N53 and
N83 inputs; only then project a complete N131 solve in calibrated units.

Recheck the frozen result:

```sh
env PYTHONDONTWRITEBYTECODE=1 TMPDIR=/Volumes/SSD990/llm/tmp python3 experiments/compact-s3-m4-20261003/q20261012_q1517_inprocess_pair_enum/validate.py
```
