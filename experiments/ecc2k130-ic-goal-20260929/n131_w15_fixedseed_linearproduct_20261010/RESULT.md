# One fixed W15 pair seed yields a smaller six-pair circuit

Fixing the first W15 pair's mask-XOR seed to `s=12004` makes its source product `p=w(w+s)=w²+sw` linear in one 15-bit mask. The exact fixed-seed source still has **752,094,681,192,591,998,035,606,369,052,497,482,898,066,636,800** signed tuples with twelve distinct folded columns, or **1,105,103,811.282** per uniform subgroup target before zero-intermediate and group-output filtering. Independent combinatorial counts agree, and the checked Sage identity audit verified all **8,176** ordered usable mask pairs for this seed. The map has rank 14 because its kernel on the W15 subspace is `{0,s}`.

The exact curve is `y²+xy=x³+1` over `GF(2)[t]/(t^131+t^13+t²+t+1)`, curve ID `EC1N131Ckb1heb5f1998f20b`; the source has **B=197,292** usable factor-base points and **K=16,381** folded columns. The seed came from an archived constructed witness, while the public input is the previously published challenge point. The [frozen protocol](protocol.json) binds both inputs, executed source hashes, one worker, a 600-second construction-plus-search cap, and a 4-GiB combined-RSS cap. The [constructed control](control.json) has a complete checked XCNF assignment and exact group lift.

| Constructed-control circuit | Six free pairs | First pair fixed to `s=12004` |
| --- | ---: | ---: |
| Variables | 121,757 | **119,664** |
| CNF clauses | 436,717 | **430,570** |
| Native-XOR rows | 43,242 | **43,208** |
| AND gates | 77,021 | **74,962** |
| Complete group-backed witness | passes | **passes** |

The specialization removes **2,059 AND gates**, **2,093 variables**, and **6,147 CNF clauses** from this controlled circuit comparison. It retains five free pair blocks and the same upper S3 chain. The [independent control-formula replay](audit.py) checked the compressed XCNF bytes, all clause and XOR rows, and all 22 appended trace clauses.

| Published-point gate | Recorded result |
| --- | ---: |
| Target-formula construction | 1.980 s |
| CryptoMiniSat search | 590.056 s |
| Construction plus search | 592.036 s |
| Sampled peak combined RSS | 778,354,688 B |
| Public formula | 119,671 variables; 430,570 CNF clauses; 43,215 native-XOR rows |
| Terminal status / stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| Solver status lines / model lines | 0 / 0 |

The [result](result.json), [compressed public formula](system.xcnf.gz), and [raw solver log](solver.stdout.txt) preserve the capped query. The [terminal audit](terminal_audit.json) checked both formulas, source and input hashes, solver activity, and resource accounting. Host isolation was not established; the two capped searches are stage observations rather than a wall-time speedup comparison. This method remains a proposal with `candidate_id: null`.

The next search gate is **target-coupled elimination across multiple pair blocks before mask expansion**. On the archived unpinned N41 public point, combine the exact seed-bucket S3 norm with the rotated four-atom product-space inverse to generate and reject partial-sum families while at least four pair blocks remain free. Require a complete ordinary relation with independent group and column replay, then a source-bound one-worker N131 work and RSS projection that fits 600 seconds and 4 GiB before another challenge-width query. Count verified ordinary relations and novel rows per query after that gate; factor logs and same-point rho timing follow a complete candidate.
