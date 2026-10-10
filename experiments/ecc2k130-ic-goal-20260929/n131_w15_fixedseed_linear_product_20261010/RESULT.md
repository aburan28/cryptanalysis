# A fixed W15 seed makes two pair products linear in one source mask

For mask-XOR seed `s=13,686`, each constrained pair has source product
`p=w(w+s)=w²+sw`. This map is linear over `F₂` and has **dimension 14**
on the 15-dimensional W15 source. Encoding the two fixed-seed pairs with
15 source-bit coordinates instead of the generic 29 product coordinates
removes **4,118 AND gates, 12,354 CNF clauses, 54 native-XOR rows, and
4,172 variables** from the complete constructed N131 circuit, with the
same source masks, column exclusions, and group target. A complete
constructed assignment passes every row of the new XCNF. In a separately
frozen **120-second extraction gate**, one-worker CryptoMiniSat remained
active until `CENSORED_TIME` at **112.033 s** of formula construction plus
search. The [terminal audit](terminal_audit.json) binds the algebraic
identity, full assignment check, executed XCNF, raw solver log, and resource
record.

The exact field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The W15 source
has **B=197,292** subgroup-usable factor-base points and **K=16,381**
signed-Frobenius columns. The two specialized pairs are slots 2 and 3,
at rotations 26 and 39; slots 0, 1, 4, and 5 retain the original circuit.
The source-seed restriction has the exact uniform-target tuple mean
**1.0522519586** before cross-pair column exclusions. This gate uses the
previously group-replayed constructed point with `target_count: 0` to test
unassisted solver extraction. The published point is held in the
[protocol](protocol.json) for the later public gate and is not substituted
into this control measurement.

For source basis `w_i=t^(i+1)` and fixed seed element
`s=Σ_j s_j t^(j+1)`, the contribution of input bit `a_i` to `p` is
`w_i²+s w_i`. The [specialized circuit](linear_product.py) applies the
appropriate Frobenius rotation to these 15 basis images and leaves the
pair-output equation and upper S3 joins unchanged. The independent
[product audit](product_identity.json) checked
`w(w+s)=Σ_i a_i(w_i²+s w_i)` for **all 32,768** W15 masks and found image
rank 14. The 30 seed clauses force the second mask of each specialized
pair to the corresponding first mask plus `s`; the existing block-equality
constraint carries the seed to the second pair. The [full XCNF control](control.json)
uses the same twelve-point witness as the original W15 circuit and
verifies **424,401 CNF clauses and 43,218 native-XOR rows**. The
[checked Sage runtime](sage_runtime_info.json) was saved before the
measured Sage job.

| Constructed N131 W15 circuit | Generic with same 30 seed clauses | Linear product |
| --- | ---: | ---: |
| Variables | 121,787 | **117,615** |
| CNF clauses | 436,755 | **424,401** |
| Native-XOR rows | 43,272 | **43,218** |
| AND gates | 77,021 | **72,903** |
| Complete constructed witness | passes | **passes** |

| Bounded specialized extraction stage | Recorded result |
| --- | ---: |
| Formula construction | 1.145 s |
| Solver search | 110.888 s |
| Construction plus search | 112.033 s |
| Sampled peak combined RSS | 642,580,480 B |
| Last logged approximate conflicts / restarts | 958,000 / 1,483 |
| Terminal status / solver stop | `CENSORED_TIME` / `SOLVER_WALL_CAP` |
| SAT or UNSAT line / model lines | none / 0 |

The [result](result.json), [compressed formula](system.xcnf.gz), and
[raw solver log](solver.stdout.txt) preserve the timed diagnostic. Its
formula SHA-256 matches the complete constructed-control formula before
search. The gate establishes a correct, smaller encoding; extraction was
still censored at the declared cap, so it does not supply ordinary
relation yield, useful rank, or a one-target IC time. No controlled CPU
speedup is inferred from wall time on this unisolated host. The proposal
retains `candidate_id: null`.

The next method step is target-conditioned generation of compatible
four-atom residuals and seed families before source-mask expansion. The
exact one-sided Artin–Schreier join can serve as the terminal source
membership and witness decoder. First require an unpinned N41 public
relation with full column and group replay, then a source-bound N131
work/RSS projection before another published-point query. Relation rank,
factor-base logs, fresh-target recovery, and matched same-point rho
timing are later complete-pipeline gates.
