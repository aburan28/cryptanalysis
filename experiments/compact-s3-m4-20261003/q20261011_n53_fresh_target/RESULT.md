# Q1461: one fresh N53 target recovered from the rank-227 base

The Q1457 factor-base logarithms recovered the discrete logarithm of one
previously unseen N53 target. The complete signed-Frobenius pair table found
its first quotient match at query 174,935; independent four-point expansion,
log substitution, and group scalar replay recovered
`10348862694683` modulo `21044858204113`.

| Identity or measurement | Value |
| --- | --- |
| Curve | `EC1N53Ckb1hf77aab617904` |
| Candidate | `IC1N53Ckb1fb24062PDP4mitmRCenumLAgaussTDdirectISO0h8ec5895c4d78` |
| Workload | `71e0ca65effe`, exactly one target |
| Run | `IC1N53Ckb1fb24062PDP4mitmRCenumLAgaussTDdirectISO0h8ec5895c4d78W71e0ca65effeR1` |
| Actual factor base and folded columns | 24,062; 227 |
| Setup rank and replayed logs | 227/227; 227 |
| Fresh-target first match | query 174,935; one verified relation |
| Native target query and lookup | 5.145022 s |
| Relation expansion and scalar recovery | 0.004395 s |
| Independent target scalar replay | 0.001091 s |
| Target-dependent phase sum | **5.150508 s**, exploratory |
| Target-process table build | 44.669584 s, reusable preparation |
| Counted pair-add attempts, setup plus target process | 65,834,737 = `2^25.972` |

The target-dependent phase sum charges every target query through the first
match, relation expansion, recovery, and group replay. The native target
lookup and Python recovery were separate processes, so a contiguous
one-target online stopwatch interval is still unmeasured. The pair-add count
includes both native table builds and both query streams; it excludes
factor-base construction, modular linear algebra, scalar replay, and input
generation. The complete solve exponent in a single normalized operation
unit is therefore recorded as null. No isolated-host paired rho row exists
for this workload; the wall times are exploratory.

The [candidate manifest](candidate_manifest.json) follows the `IC1` naming
contract and hashes its exact field, curve, base, algorithms, and executed
source components. The [pipeline receipt](pipeline_receipt.json) separates
setup phases, target-dependent phases, missing subphase splits, resource
conditions, and correctness. The target scalar fixture is checked after
group recovery and outside its charged phase.

For the N131 challenge, Q1462 reprices the separate conditional W≤7
full-index model at `2^86.18` counted pair-add attempts, 25.18 bits above
an abstract `2^61` pair-add reference. The actual N131 W≤7 base and its
full solve projection remain unresolved; the N53 measurement is not used as
an N131 success-rate estimate.

Validate the source, inputs, candidate ID, workload ID, scalar, and exclusive
phase sum with:

```sh
python3 experiments/compact-s3-m4-20261003/q20261011_n53_fresh_target/validate.py
```
