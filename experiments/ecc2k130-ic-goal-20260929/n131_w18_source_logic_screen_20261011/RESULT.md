# Exact source-logic screen for the N131 W18 rational mask set

The W18 source-membership predicate has a **dense 131,019-term Boolean ANF of degree 18** on its 18 mask bits. The current reduced ordered BDD has **31,118 nodes**; among 30 fixed-seed alternative variable orders, the smallest has **31,002 nodes**, a reduction of 116 nodes (0.373%). This exact screen makes a direct ANF expansion and a small random BDD-order search weak candidates for resolving the present N131 cubic SAT bottleneck. It does not claim a global minimum BDD order or a formula/solver timing gain.

The source is the audited rational-mask table for `GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, curve `EC1N131Ckb1heb5f1998f20b`. It has **131,307 valid masks** among `2^18=262,144` possible masks and **131,068** folded columns. The [frozen protocol](protocol.json) binds that table, the current cubic BDD builder, the deterministic permutation seed `20261011`, 30 alternative orders, one worker, a 120-second wall cap, and 4 GiB RSS. The invalid-mask truth table is transformed to its algebraic normal form by the Boolean Möbius transform; reduced BDDs are hash-consed bottom-up for every declared order.

| Exact source-logic item | Result |
| --- | ---: |
| Invalid-mask ANF terms / maximum degree | **131,019 / 18** |
| ANF terms by degree 0–18 | `1,8,100,369,1460,4295,9107,15839,22076,24220,22098,15976,9220,4264,1483,425,69,8,1` |
| Current root-to-leaf BDD order | bits 17 through 0; **31,118** nodes |
| Best / median / worst of 30 fixed-seed alternatives | **31,002 / 31,092 / 31,151** nodes |
| Current-builder cross-check | **31,118** nodes |
| Producer wall / peak process RSS | 19.723 s / 65,519,616 B |

The [result](result.json) retains every sampled order and node count, exact ANF degree counts, source hashes, and process measurements. The [independent audit](audit.json) recomputes the ANF in reverse variable order, transforms it back to all 262,144 truth-table entries, checks the permutation stream, and obtains the current, best, and worst BDD node counts through a separate recursive Shannon expansion. These are source-encoding diagnostics on an unisolated host, with `candidate_id: null`.

The current eight-slot cubic formula spends substantial work on source membership, but the measured order change is small and a naive dense ANF would add many monomial terms. The next method should retain a compact exact source encoding while coupling the public point to multiple pair-product or block-output families before source-mask expansion. Any such N131 variant still needs an unpinned ordinary relation under a frozen resource budget before yield, rank, factor logs, and single-target online comparison can be measured.
