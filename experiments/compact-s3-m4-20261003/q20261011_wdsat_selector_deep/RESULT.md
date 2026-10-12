# Q1468: (2^{23})-branch selector-first four-summand search

The Q1467 selector-first order reached an eightfold deeper counted search on
the exact ordinary N53 and N83 queries. Both runs reached the frozen
(2^{23}=8,388,608) left-branch cap. The full-lock control at each degree
returned a SAT model independently replayed against both the width-four and
original XCNF.

| Field degree | Ordinary status | Left branches | User CPU seconds | Exploratory wall seconds | Child peak RSS |
| ---: | --- | ---: | ---: | ---: | ---: |
| 53 | `BRANCH_CAP_REACHED` | 8,388,608 | 76.917 | 179.608 | 220 MiB |
| 83 | `BRANCH_CAP_REACHED` | 8,388,608 | 102.254 | 227.307 | 858 MiB |

Q1468 is a `PDP4sat` solver-stage proposal. Its `candidate_id` and `run_id`
remain null; the exact curve IDs, actual factor-base sizes, folded column
counts, workload IDs, target points, source XCNF hashes, and transformed
XCNF hashes are in the [frozen input record](freeze.json) and run receipts.
The compiled solver retains the Q1467 selector-first permutation, with only
the left-branch cap increased from (2^{20}) to (2^{23}). It uses pinned
WDSat commit `61c6ff3f49445af2729274819edb27b85a89efc1`, 180/181-second
CPU soft/hard limits, a 1,800-second wall limit, and no address-space limit.
The branch metric counts four instrumented `conf[0]++` left-branch sites.

[The validator](validate.py) passed all four receipts, checking source
arrays, binaries, exact inputs, branch checkpoints, and SAT replay. These
fixed-query outcomes establish a search-depth boundary for this order and
these targets. They do not determine natural relation yield or the complete
point-decomposition work exponent. Accordingly, [the analysis](analysis.json)
retains the N131 full-solve exponent and gap to the (2^{61}) challenge as
`null`. The distinct conditional N131 full pair-index reference remains
(2^{86.1847}) counted pair-add attempts, 25.1847 bits above a (2^{61})
pair-add reference. Left branches, pair additions, and field operations are
different accounting units. The wall and CPU observations are exploratory
because the host lacks an isolation receipt.

The next search should vary the selector prefix itself, especially nearby
pair-midpoint and leaf-bit priorities, at a fixed branch cap on the same
ordinary points. Any ordinary SAT model needs group-law replay before its
relation can enter a yield measurement.
