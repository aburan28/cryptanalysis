# Q1470: deeper selected branch priorities

The selected Q1469 prefixes retained lower exploratory user CPU cost at the
matched (2^{23}=8,388,608)-branch cap. Interleaved leaves after selectors
used 55.454 seconds on the fixed N53 ordinary query, compared with 76.917
for selectors alone. Pair-midpoint blocks after selectors used 76.771 seconds
on N83, compared with 102.254. Both full-lock controls returned independently
replayed SAT models.

| Field degree | Selected prefix | Ordinary status | Left branches | User CPU seconds | Selectors-only seconds | Baseline / selected |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 53 | Selectors, then interleaved leaves | `BRANCH_CAP_REACHED` | 8,388,608 | 55.454 | 76.917 | 1.39× |
| 83 | Selectors, then pair-midpoint blocks | `BRANCH_CAP_REACHED` | 8,388,608 | 76.771 | 102.254 | 1.33× |

The choices were frozen from Q1469 before Q1470 timing. The exact curve,
factor base, folded columns, public point, original and width-four XCNFs,
branch cap, and CPU/wall resource limits match Q1468 at each degree. Q1470
uses pinned WDSat commit `61c6ff3f49445af2729274819edb27b85a89efc1`
with 180/181-second CPU soft/hard and 1,800-second wall limits, without an
address-space limit. The branch metric counts four instrumented `conf[0]++`
left-branch sites. [The frozen record](freeze.json) includes the priority
arrays and source/input receipts; [the validator](validate.py) passed all
four control and ordinary run receipts, including binary hashes, branch
checkpoints, and XCNF replay.

This repeats a fixed-query solver-kernel improvement at a deeper cap. The
ordinary results remain censored, so the natural relation yield, complete
decomposition work exponent, N131 full-solve exponent, and gap to the
(2^{61}) challenge remain `null` in [the analysis](analysis.json). The
separate conditional N131 full pair-index reference remains (2^{86.1847})
counted pair-add attempts, 25.1847 bits above a (2^{61}) pair-add reference.
The WDSat CPU ratios do not alter that pair-add count. Wall and CPU ratios
are exploratory because the host lacks an isolation receipt.

The next goal is to turn a branch-cost improvement into a **useful-relation
cost estimate**: sample a frozen set of previously unseen ordinary targets,
record all censored attempts and verified decompositions, and measure exact
GF(2) and field-operation work alongside branch counts. A model must replay
against both XCNFs and the four-point curve sum before it enters the yield
estimate. That evidence can then bound the per-decomposition cost against
the N131 (2^{30.6})-field-operation allowance for a sub-(2^{61}) IC path.
