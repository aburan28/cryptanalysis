# Six free W15 pair blocks: exact source census and public-query gate

The six-pair W15 construction leaves all twelve source masks free and enforces twelve distinct signed-Frobenius columns. Its exact source census is **24,863,471,058,848,457,991,060,203,338,856,652,134,570,456,632,524,800** signed tuples. Dividing by the subgroup order gives **36,533,587,214,387.252** tuples per uniform target before filtering zero intermediates or checking group output. Two independent combinatorial programs agree on the count. This is a source-density calculation; ordinary relation yield is measured by the public-point search below.

The instance uses `GF(2)[t]/(t^131+t^13+t²+t+1)`, `y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`, **B=197,292** usable factor-base points, and **K=16,381** folded columns. The [frozen protocol](protocol.json) binds the published challenge point, source and solver hashes, one worker, a 600-second construction-plus-search cap, and 4 GiB combined-RSS cap. The [constructed control](control.json) has a complete checked XCNF assignment and an exact group lift. Its formula contains 121,757 variables, 436,717 CNF clauses, 43,242 native-XOR rows, and 77,021 AND gates.

| Published-point gate | Recorded result |
| --- | ---: |
| Target-formula construction | 2.861 s |
| CryptoMiniSat search | 589.197 s |
| Construction plus search | 592.058 s |
| Sampled peak combined RSS | 702,971,904 B |
| Public formula | 121,764 variables; 436,717 CNF clauses; 43,249 native-XOR rows |
| Terminal status / stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| Solver status lines / model lines | 0 / 0 |

The [result](result.json), [compressed public formula](system.xcnf.gz), and [raw solver log](solver.stdout.txt) preserve the capped attempt. The [terminal audit](terminal_audit.json) rechecked source hashes, both compressed formulas, trace clauses, solver activity, and resource accounting. The host was unisolated, so these wall times are stage diagnostics. This gate retains `candidate_id: null` until a complete IC pipeline is specified and measured.

The next experiment specializes one pair to the constructed control's fixed XOR seed while leaving the other five pair blocks free. The identity `w(w+s)=w²+sw` makes that pair product linear in one source mask and removes 2,059 AND gates from the control circuit. Its exact source census remains above one billion tuples per uniform target before intermediate filtering; the frozen public-point gate will test whether the smaller circuit yields a verified relation under the same resource envelope.
