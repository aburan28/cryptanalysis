# Q1521: four N83 complements reuse one exact-base setup

The `PDP4hybrid` native scanner now decodes the exact N83 factor base and
builds its raw-x Bloom index **once for four signed complements**, instead of
starting a new process and repeating setup four times. The scanner returned
the same exact result vector as Q1520 on eight frozen ordinary complements:
per-query raw-x checksums, Bloom probes and positives, canonical-key calls,
exceptional counts, and zero exact-base hits all match. Four positive
controls each replayed the same exact signed-base hit as Q1512.

| Frozen ordinary workload, phase-three pair 6 | Separate Q1520 processes | Fused Q1521 process | Accounting boundary |
| --- | ---: | ---: | --- |
| Selected `2eb250a29072`, base decodes and Bloom builds | 4 | **1** | Exact invocation count |
| Selected, child CPU seconds | 13.44 | **11.11** | Exploratory, unisolated |
| Selected, host wall seconds | 80.70 | **53.70** | Exploratory, unisolated |
| Holdout `394256b9f901`, base decodes and Bloom builds | 4 | **1** | Exact invocation count |
| Holdout, child CPU seconds | 12.32 | **10.39** | Exploratory, unisolated |
| Holdout, host wall seconds | 122.68 | **53.43** | Exploratory, unisolated |

The child CPU ratios are 1.21 and 1.19 for these fixed groups. The panels
ran at different times on a heavily contended host, so these ratios are
implementation diagnostics, not controlled wall-time speedups. Peak fused
child RSS was 1,282,981,888 bytes on selected and 1,283,375,104 bytes on
holdout. The fused process retains one base and Bloom index while scanning
all four complements; it does not keep four copies in memory.

The exact curve is `EC1N83Ckb1h876c2921cb64`; its cofactor-four
weight-at-most-five base has **B=30,977,592** usable subgroup points and
**K=186,612** signed-Frobenius columns. The base binary digest is
`56c951ad78cc4036d3e8ff70bcb9d7feccacc6c763220b285def056cba30afb8`.
This is stage proposal `Q1521`, with null candidate and run IDs and
`isogeny: "none"`. The [protocol](protocol.json) pins the parent source,
compiled binary, exact Q1520 query inputs, control, resource caps, and
compiler command. The [native implementation](native_fused.cpp),
[per-process receipts](runs), [result](result.json), [analysis](analysis.json),
and [validator](validate.py) retain both the exact output comparison and
exploratory resource timings.

The eight complete scans still require **619,551,840 = \(2^{29.207}\)**
batch multiplication calls, excluding inversion internals. Reusing setup
does not change the N131 complete-scan arithmetic or Q1506's specified
independent-first-pair relation-supply model of \(2^{123.289}\) such calls,
62.289 bits above an abstract \(2^{61}\) call reference. The fully charged
N131 solve exponent remains null because ordinary relation yield, rank
novelty, final matrix work, and target handling are unresolved for this
compact solver. The next improvement must reduce the number of second-base
points tested per usable first pair or increase target-conditioned relation
yield, then measure novel rows on ordinary N83 inputs.

Recheck every frozen positive control and matched ordinary scan vector:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 experiments/compact-s3-m4-20261003/q20261012_q1521_fused_complements/validate.py
```
