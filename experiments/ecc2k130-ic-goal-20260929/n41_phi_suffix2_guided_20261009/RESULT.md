# N41 target-conditioned suffix support: chain-index failure record

Exact curve arithmetic enumerated 3,600 signed two-leaf suffix cases for
the frozen N41 public target and produced **3,577 distinct finite residual
phi masks**. The [independent enumeration audit](preflight.json) reproduced
every mask and verified that one endpoint-sign set covers both signs of the
target. Reusable pair sums took 0.478 seconds; residual computation and XCNF
encoding took 1.250 target-dependent seconds.

The frozen [guided formula](guided.xcnf) placed those masks on the wrong
chain coordinate. In the 12-leaf left-deep chain, `partial8` is the sum
through leaf 9 and precedes the two-leaf suffix at positions 10 and 11.
`partial9` already includes leaf 10. The builder used variables 443–483
(`partial9`) where the exact two-leaf residual belongs on variables
402–442 (`partial8`). The byte-level preflight checked the written clauses
against that same incorrect index and therefore did not catch the semantic
misplacement.

CryptoMiniSat returned `UNSAT_FORMULA` after **108.687 solver-stage seconds**
on this invalid encoding. The [terminal audit](audit.json) confirms the
saved input/output hashes and process drain; it does not qualify the UNSAT
status as a result about the intended decomposition. The [run record](result.json)
retains the raw status, zero model lines, 1.250 seconds of target-dependent
construction, and 109.937 seconds of known target-dependent stage time.
This proposal is classified **`PRODUCER_ENCODING_ERROR`** for the IC
comparison, with no verified relation or rank contribution.

The corrected gate is to rebuild the same audited residual set on
`partial8`, add an independent planted-chain semantic check that subtracting
leaves 10 and 11 from a known endpoint yields `partial8`, and only then run
the frozen ordinary public-target query. The failed input, exact source,
preflight, solver log, and receipt remain available for regression.
