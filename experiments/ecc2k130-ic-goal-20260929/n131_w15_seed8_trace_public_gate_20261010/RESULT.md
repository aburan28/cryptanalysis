# Eight W15 seeds and an exact trace fiber constrain the public query

The seed family **13,680–13,687** has an exact group-wide mean of
**8.3540070920** signed twelve-point tuples per uniformly selected N131
subgroup target before cross-pair column exclusions. For the published
point, independent Sage arithmetic restricts the four raw target preimages
to trace-zero indices **0 and 2**. These constraints preserve the complete
constructed twelve-atom witness and add only **26 CNF clauses** to the
unrestricted public XCNF. A frozen one-worker CryptoMiniSat query reached
`CENSORED_TIME` after **592.119 s** of construction plus search under the
600 s / 4 GiB gate. The [terminal audit](terminal_audit.json) verifies the
exact added clauses, unchanged base formula, source hashes, and raw log.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. Its subgroup
order is `680564733841876926932320129493409985129`. The audited W15
factor base has **B=197,292** usable points and **K=16,381** folded
columns. The [protocol](protocol.json) freezes the exact public target,
seed family, counts, source and solver hashes, one worker, 600 s, and
4 GiB before execution. The [checked Sage runtime](sage_runtime_info.json)
was saved before the measured job. The [complete constructed control](control.json)
checks **436,751 CNF clauses and 43,272 native-XOR rows** using the
previously group-replayed witness at seed 13,686.

For signed pair counts `c_s`, write `N=Σ_s c_s=540,579,832` and
`S=Σ_s c_s²=8,918,874,017,088`. The family contributes
`Σ_{s=13680}^{13687} c_s²=2,181,396,304` four-atom states.
The tuple mean is `N² S (Σ_family c_s²)/r` for subgroup order `r`.
It bounds source support before columns shared across different pairs
are excluded. The [prior trace proof](../n131_w15_one_seed_public_gate_20261010/trace_result.json)
checks all four raw published-target preimages by installed Sage and gives
reciprocal traces `[0,1,0,1]`; the source W15 basis has trace zero.

| Published-point stage | Frozen result |
| --- | ---: |
| Target-dependent formula construction | 2.792 s |
| Solver search | 589.327 s |
| Construction plus search | 592.119 s |
| Sampled peak combined RSS | 750,518,272 B |
| Last logged approximate conflicts / restarts | 2.896 million / 2,860 |
| Terminal status / solver stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| SAT or UNSAT line / model lines | none / 0 |

The [result](result.json), [solver log](solver.stdout.txt), compressed
[formula](system.xcnf.gz), and [byte-level auditor](audit.py) retain the
complete stage record. The comparison formula has **121,794 variables,
436,751 CNF clauses, and 43,279 native-XOR rows**; the prior 436,725
CNF clauses and all native-XOR rows match byte for byte. This is a
proposal-stage `candidate_id: null` result with no relation row or useful
rank within the cap. These unisolated-host solver times are exploratory
stage measurements.

The next encoding gate makes the trace-zero condition explicit for all ten
intermediate reciprocal coordinates. In this exact polynomial basis,
`Tr(x)=x₀⊕x₁₂₉`; twenty binary clauses expose those ten necessary
equalities to unit propagation while keeping the same seed family and
public target.
