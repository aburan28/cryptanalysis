# Two independent W15 pair seeds reduce the N131 six-pair circuit

Fixing the first two mask-XOR pair seeds to `12004` and `9022` makes both pair products linear in their respective 15-bit source masks. The resulting six-pair source has exactly **23,206,419,158,377,803,130,458,201,825,805,898,783,784,960** signed tuples with twelve distinct folded columns, or **34,098.768** per uniform subgroup target before zero-intermediate and group-output filtering. The direct 17,042,784-choice census and an independent incidence-based count agree. The checked Sage identity audit verified the linear product on **8,176** and **8,340** usable ordered mask pairs at Frobenius rotations 0 and 13.

The exact curve is `y²+xy=x³+1` over `GF(2)[t]/(t^131+t^13+t²+t+1)`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source has **B=197,292** usable factor-base points and **K=16,381** folded columns. Both seeds came from an archived constructed witness; the [frozen protocol](protocol.json) binds the previously published challenge point, executed sources, one worker, a 600-second construction-plus-search cap, and a 4-GiB combined-RSS cap. The [constructed control](control.json) has a complete checked XCNF assignment and exact group lift.

| Constructed-control circuit | One fixed pair | Two fixed pairs |
| --- | ---: | ---: |
| Variables | 119,664 | **117,245** |
| CNF clauses | 430,570 | **424,423** |
| Native-XOR rows | 43,208 | **42,848** |
| AND gates | 74,962 | **72,903** |
| Complete group-backed witness | passes | **passes** |

| Published-point gate | Recorded result |
| --- | ---: |
| Target-formula construction | 3.932 s |
| CryptoMiniSat search | 588.180 s |
| Construction plus search | 592.112 s |
| Sampled peak combined RSS | 685,441,024 B |
| Public formula | 117,252 variables; 424,423 CNF clauses; 42,855 native-XOR rows |
| Terminal status / stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| Solver status lines / model lines | 0 / 0 |

The [result](result.json), [compressed public formula](system.xcnf.gz), and [raw solver log](solver.stdout.txt) preserve the capped attempt. The [terminal audit](terminal_audit.json) checked both exact formulas, source hashes, trace clauses, solver activity, and resource accounting. Host isolation was not established, so these times are stage diagnostics; the proposal retains `candidate_id: null`.

The solver log records several discarded native-XOR matrices with 2,095–3,929 columns, above CryptoMiniSat's default 1,000-column limit. A separately frozen [matrix-policy gate](../n131_w15_two_fixed_gauss_public_20261010/) tests the byte-identical formula with a 4,096-column limit and up to eight matrices under the same target and resource envelope. The next algorithmic gate after solver-policy testing is target-coupled elimination across multiple still-free pair blocks, checked first on an unpinned N41 relation and then against a source-bound N131 work/RSS projection.
