# Corrected target-conditioned suffix support on the N41 public chain

The two-leaf suffix now constrains **`partial8`**, the state before leaves
10 and 11. An exact planted-chain [semantic control](semantic_control.json)
subtracts those two signed leaves from its endpoint and recovers the saved
`partial8` point and 41-bit phi coordinate. It also checks the circuit's
primary-variable ranges: `partial8` occupies variables 402–442, while
`partial9` occupies 443–483. This closes the chain-index gap that invalidated
the preserved [first run](../n41_phi_suffix2_guided_20261009/RESULT.md).

For the frozen ordinary public point, 3,600 signed suffix pairs give 3,577
distinct finite `partial8` masks. The [independent preflight](preflight.json)
re-enumerates every pair, proves the same x-coordinate set covers both
endpoint signs, and byte-compares all 54,513 inherited XCNF records plus
146,658 appended membership clauses. Reusable pair sums took 0.085 seconds;
target-conditioned residual enumeration and formula encoding took **0.198
seconds**. The corrected XCNF has 37,942 variables and 201,171 records.

The one-worker public-target query ended **`CENSORED_TIME`** at its frozen
240-second wall cap with zero model lines. Sampled solver CPU was 120.129
seconds and sampled combined peak RSS was 132,972,544 bytes. The
[terminal audit](audit.json) checks the exact input/output hashes and drained
process. Known target-dependent stages sum to **240.254 seconds**: the
0.198-second suffix construction plus 240.056 solver-stage seconds. The
earlier source formula's target-dependent construction was outside this
interval, so complete one-target online time remains unknown. The host has
no isolation receipt; these wall and CPU values are exploratory. The
[frozen protocol](protocol.json), checked-Sage runtime, XCNF, raw solver
log, and [result](result.json) retain the cap and censored row.

The exact lookup and backward membership constraints are now qualified for
correctness, but their SAT search has not passed the smaller-field ordinary
relation gate. The next method gate is an exact **target-coupled group join**
using a reusable adjacent two-leaf sum index, with the same public N41
target and independent point replay. A verified row and measured
target-dependent index-query cost would guide a 4-GiB N131 d13 pair-index
preflight. The N131 ordinary-relation, useful-rank, factor-log, and
one-target online-vs-rho gates remain active.
