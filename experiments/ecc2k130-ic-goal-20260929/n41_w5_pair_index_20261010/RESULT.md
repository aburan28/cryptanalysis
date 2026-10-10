# Exact fifth-pair output index on the N41 public target

An exact target-independent W5 pair-output index has **264 transformed
signatures** for one same-rotation leaf pair. Inserting this index into the
fifth leaf of the ten-summand public-point formula removes that leaf's
arithmetic S3 circuit while preserving a complete, independently replayed
relation. A fixed valid index entry and the unpinned formula both reached
their frozen SAT caps. The remaining upper-chain search is therefore a
measured method gate for this encoding.

The exact N41 field is `GF(2^41)` with polynomial `t^41+t^3+1`; the curve
is `y²+xy=x³+1` with prime subgroup order `549756390943` and curve ID
`EC1N41Ckb1h7d5e80d3c4d0`. The public point is
`Q=(1458168294740,1672312028033)`. Ten leaf slots use W5 rotations
`[0,0,8,8,16,16,24,24,32,32]`, with **B=170 actual usable factor-base
points** and **K=14 folded columns**. The exact public relation and its
checked-Sage group replay are bound to the earlier
[same-pair result](../n41_w5_samepair_hybrid_20261010/RESULT.md).

For each unordered pair of rational masks with different folded columns,
the [index builder](build_index.py) enumerates all four leaf-sign choices,
adds their raw curve points, and records
`(mask_a, mask_b, z)` with `mask_a<mask_b` and `z=1/(x(P_a+P_b)+1)`.
There are 528 accepted signed rows and 264 distinct signatures; both
simultaneous sign flips yield the same `z`. The
[independent checked-Sage audit](sage_index_audit.json) reconstructs all
17 rational masks and 34 source points, verifies subgroup projection,
checks every signed pair row, and confirms the index entry used by the
public relation after the inverse Frobenius frame change.

The [indexed circuit](circuit.py) constrains the fifth pair's two masks
and local output to exactly one of these signatures using a linear-size
sequential selector. The other four leaf pairs retain exact framed
low-product S3 links; four upper S3 links connect the five pair outputs
to the public target. A SAT model still needs raw-point replay because
the transformed coordinate omits signs. The [frozen protocol](protocol.json)
binds the code, index, checked Sage runtime, geometry, solver binary,
public point, and one-worker resource caps before formula construction.

The [preflight](preflight.json) completes all auxiliary variables for the
previously replayed public relation and checks every clause and native XOR
row in both the unpinned and known-selector formulas. The known relation
uses index entry 178. On the **same point and factor base**, the earlier
exact five-leaf arithmetic formula had 9,681 AND gates, 30,710 CNF
clauses, and 8,026 XOR rows. The indexed formula has 9,162 AND gates,
43,365 CNF clauses, and 7,511 XOR rows. These are construction counts;
the different clause structure prevents inferring solver performance from
the gate reduction.

| Frozen one-target SAT stage | Known valid selector fixed | All 264 selectors unpinned |
| --- | ---: | ---: |
| Parent wall cap | 45 s | 120 s |
| Recorded status | `CENSORED_TIME` | `CENSORED_TIME` |
| Solver wall | 45.106 s | 120.199 s |
| Logged search restarts | 493 | 672 |
| Sampled solver peak RSS | 28,901,376 B | 47,841,280 B |
| Model lines | 0 | 0 |

The [fixed query](fixed_query/result.json) and
[unpinned query](public_query/result.json) logs show active CryptoMiniSat
search with empty stderr. Parent caps terminated both one-worker attempts;
neither terminal row is an UNSAT result. The
[terminal audit](terminal_audit.json) rechecks frozen source hashes, the
264-entry index, independent Sage verification, full XCNF controls, and
both solver logs. CPU wall observations are exploratory on this
unisolated host. This is an IC design proposal with `candidate_id: null`;
relation yield and novel rank for this query are represented by the
recorded capped attempt.

The next N41 method gate is to constrain **all five** pair outputs by
their exact tables, separating upper five-sum selection from leaf
arithmetic. If that helps, the challenge-width analogue should replace
the enormous explicit W14 tables with the audited 41-column same-rotation
pair inverse and test target-conditioned output proposals on an unpinned
degree-131 point under a frozen memory and wall envelope. A complete
single-target IC comparison still requires verified relation rank,
factor logs, target recovery, and paired same-point rho timing.
