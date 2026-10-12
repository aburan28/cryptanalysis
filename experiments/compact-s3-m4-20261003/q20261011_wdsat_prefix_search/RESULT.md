# Q1469: selector-prefix branch priority search

The matched (2^{20})-branch screen identified different lowest-cost prefixes
on the fixed ordinary N53 and N83 queries. On N53, putting interleaved leaf
bits after the target-preimage selectors used 7.531 user CPU seconds, versus
8.129 for selectors alone. On N83, putting the two pair-midpoint bit blocks
after the selectors used 10.026 seconds, versus 12.665 for selectors alone.
Each of the six full-lock controls returned a SAT model independently replayed
against the transformed and original XCNF.

| Field degree | Priority after selectors | Ordinary status | Left branches | User CPU seconds | Selectors-only / variant |
| ---: | --- | --- | ---: | ---: | ---: |
| 53 | Pair-midpoint blocks | `BRANCH_CAP_REACHED` | 1,048,576 | 15.963 | 0.51× |
| 53 | Interleaved midpoint bits | `BRANCH_CAP_REACHED` | 1,048,576 | 11.023 | 0.74× |
| **53** | **Interleaved leaf bits** | `BRANCH_CAP_REACHED` | 1,048,576 | **7.531** | **1.08×** |
| **83** | **Pair-midpoint blocks** | `BRANCH_CAP_REACHED` | 1,048,576 | **10.026** | **1.26×** |
| 83 | Interleaved midpoint bits | `BRANCH_CAP_REACHED` | 1,048,576 | 19.632 | 0.65× |
| 83 | Interleaved leaf bits | `BRANCH_CAP_REACHED` | 1,048,576 | 12.622 | 1.00× |

The three prefixes are exact transformations of the Q1467 source-bound
selector, pair-midpoint, and leaf IDs. Each is completed by all remaining
variable IDs in ascending order. The curve, actual factor base, folded
columns, public point, original XCNF, width-four transformed XCNF, branch
cap, and CPU/wall limits match Q1467 at each degree. [The priority source](priorities.py),
[frozen arrays](freeze.json), [build receipt](build_receipt.json), and 12
run receipts retain this identity. [The independent validator](validate.py)
checks source arrays, binaries, input hashes, selected-order markers, branch
checkpoints, and SAT replay.

These are three priority hypotheses per degree, each screened on one ordinary
query. The selected rows are single-query exploratory diagnostics, not an
estimated natural relation yield or a full decomposition exponent. All six
ordinary cells reached the same (2^{20}) branch cap. The host lacks an
isolation receipt, so the CPU and wall observations do not establish a
controlled wall-time speedup. The N131 full-solve exponent and gap to
(2^{61}) remain `null` in [the analysis](analysis.json). The separate
conditional N131 full pair-index reference remains (2^{86.1847}) counted
pair-add attempts, 25.1847 bits above a (2^{61}) pair-add reference.

The next measurement is a deeper capped run of the N53 leaf-prefix and N83
pair-midpoint-prefix variants on these exact ordinary points. It will test
whether their fixed-cap advantage persists as the search tree deepens.
