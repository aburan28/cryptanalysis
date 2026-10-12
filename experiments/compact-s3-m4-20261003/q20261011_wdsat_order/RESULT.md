# Q1467: selector-first branch order on exact four-summand queries

Placing the target-preimage selectors before all other WDSat variables reduced
exploratory user CPU cost at the same (2^{20}) counted left branches by 5.47×
on N53 and 5.33× on N83. The alternative interleaved-leaf order was near the
ascending baseline. All four full-lock controls returned SAT models that were
independently replayed against both their transformed and original XCNFs.

| Field degree | Order | Ordinary status | Counted left branches | User CPU seconds | Ascending baseline seconds | Baseline / order |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 53 | selector first | `BRANCH_CAP_REACHED` | 1,048,576 | 8.129 | 44.428 | 5.47× |
| 53 | interleaved leaves | `BRANCH_CAP_REACHED` | 1,048,576 | 45.427 | 44.428 | 0.98× |
| 83 | selector first | `BRANCH_CAP_REACHED` | 1,048,576 | 12.665 | 67.501 | 5.33× |
| 83 | interleaved leaves | `BRANCH_CAP_REACHED` | 1,048,576 | 64.525 | 67.501 | 1.05× |

These are ordinary queries on the exact Q1466 curve, public point, factor
base, source XCNF, and width-four transformed XCNF at each degree. Q1467
changes only the complete static branch permutation. The pinned WDSat source
is commit `61c6ff3f49445af2729274819edb27b85a89efc1`. Each run has a
120/121-second CPU soft/hard limit, a 900-second wall limit, and no address
space limit. The branch metric counts the four instrumented `conf[0]++`
left-branch sites. It is neither a field-operation count nor a full solve.

The source-bound selector IDs are 944–952 for N53 and 2140–2141 for N83.
The interleaved order visits corresponding bit positions of the four leaves
before all remaining IDs. [The order manifest](order_manifest.json) fixes the
exact arrays, and [the build receipt](build_receipt.json) binds the compiled
source and binaries. Each solver emits its selected mode and priority count;
[the validator](validate.py) checks these markers, the source arrays, the
input hashes, branch checkpoints, and SAT models. `candidate_id` and `run_id`
remain null because Q1467 is a `PDP4sat` solver-stage proposal, not a complete
IC pipeline. The curve IDs, actual factor-base size, folded columns, and
workload IDs are retained in every run receipt.

The ordinary searches are censored at (2^{20}) left branches. Consequently,
the complete decomposition work exponent, natural relation yield, N131
projection, and gap to the (2^{61}) challenge remain `null` in
[the analysis](analysis.json). A distinct conditional N131 full pair-index
reference remains (2^{86.1847}) counted pair-add attempts, 25.1847 bits
above a (2^{61}) **pair-add** reference; the WDSat CPU ratios cannot be
subtracted from that count. Wall times are exploratory because this host has
no isolation receipt, and they varied substantially across runs.

The next controlled measurement is a deeper selector-first ordinary search
on N53 and N83 with the same exact inputs, model replay, and explicit work
cap. If an ordinary SAT model appears, verify its four curve points and group
sum, then measure natural relation yield before extrapolating to N131.
