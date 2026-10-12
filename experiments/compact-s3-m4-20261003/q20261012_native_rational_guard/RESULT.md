# Q1496: exact pair guard raises usable-pair coverage but costs 9.34 bits more search

The native N83 guard applies the exact nonzero, weight-at-most-five rationality
test to both leaves when the first S3 pair is fully assigned. Across eight
frozen 249-flip restarts on each of two ordinary N83 points, it found five
usable first pairs on each point. Three restarts per point reached the
32,768-branch cap without an accepted pair. All first-pair outputs passed the
independent Q1495 predicate; the native helper matched the 40 Q1494 archived
pair classifications before solver execution.

| Ordinary N83 input | Restarts | Accepted first pairs | Branch-capped | Charged CNF/XOR calls, all attempts | Calls per accepted pair |
| --- | ---: | ---: | ---: | ---: | ---: |
| selected, workload `2eb250a29072` | 8 | 5 | 3 | 839,242,944 | 167,848,589 = 2^27.323 |
| holdout, workload `394256b9f901` | 8 | 5 | 3 | 839,261,536 | 167,852,307 = 2^27.323 |
| selected Q1491 external-filter baseline | 8 | 3 | 0 | 778,598 | 259,533 = 2^17.986 |

The selected-point comparison uses the same eight restarts and original
Q1494 exact base audit. Q1496 costs 646.7 times as many CNF/XOR calls per
accepted first pair, a 9.337-bit regression in this stage. Q1491 has no
historical holdout receipt for these eight phases; the Q1496 holdout row is
therefore an independent reproducibility check, not a paired holdout speedup.

The guard added 103,821 native pair checks on selected and 102,193 on
holdout. Each nonzero tested leaf inversion uses eight native field
multiplications and 82 squarings. Short-circuiting and zero/weight rejection
make 180 field mul/sqr operations per guard check an upper bound, rather than
an exact charge. These field operations are separate from WDSat CNF/XOR
calls; the table does not combine unlike units. Wall and CPU values in the
per-run receipts are exploratory because this host has no isolation receipt.
Peak RSS is the Darwin cumulative child statistic and is not presented as a
per-run memory peak.

The [protocol](protocol.json), [freeze](freeze.json), [build receipt](build_receipt.json),
[drive receipt](drive_receipt.json), and [charged analysis](analysis_v2.json)
bind the exact curve `EC1N83Ckb1h876c2921cb64`, B=30,977,592 actual usable
points, K=186,612 folded columns, both ordinary inputs, source/binary hashes,
limits, statuses, and work counters. This is a `PDP4sat` stage proposal with
null `candidate_id` and `run_id`, and `isogeny: "none"`. First-pair acceptance
does not yet measure complete four-summand relations, rank gain, matrix work,
or target descent, so the complete N131 solve exponent stays unset.

The original frozen validator attempted to load Q1491 historical holdout
receipts for phases 41–48, which do not exist. Its failure is retained in
`validation_v1_failure.json`. The [versioned validator](validate_v2.py)
checks selected historical baselines and both new workloads; it passed.
`analyze_v2.py` then charges the final `Q1473_WORK` counters in every capped
row. The next solver experiment should test earlier pruning or pair-level
learning on these same inputs before integrating the native check further.
