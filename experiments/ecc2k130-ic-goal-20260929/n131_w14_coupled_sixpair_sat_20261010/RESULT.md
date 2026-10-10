# Coupled six-pair W14 relation gate on ECC2K-130

A complete twelve-diagonal-atom N131 formula now enforces **two shared
W14 seed sums** and passes both a full XCNF assignment and independent
checked-Sage group replay. The two constrained four-atom blocks satisfy
`mask_4 XOR mask_5 = mask_6 XOR mask_7` and
`mask_8 XOR mask_9 = mask_10 XOR mask_11`. Six bilinear pair joins, four
upper reciprocal S3 joins, and a one-hot target-linear join connect those
atoms to one subgroup target. The control uses twelve distinct folded
columns and seed sums 13,686 and 896. A separate [group-lift control](lift_control.json)
recovers exactly one signed twelve-point relation from its masks,
intermediate reciprocals, and target-fiber choice.

The [frozen construction](protocol.json) uses the exact curve
`EC1N131Ckb1heb5f1998f20b`, field polynomial
`t^131+t^13+t^2+t+1`, subgroup order
`680564733841876926932320129493409985129`, W14 source support, and
paired rotations `[0,13,26,39,52,65]`. The actual projected factor
base has **B = 98,640** points and **K = 8,160** folded columns. Its
[constructed formula](constructed.xcnf.gz) has 119,035 variables,
875,983 CNF clauses, 42,278 native-XOR rows, and 75,275 AND gates.
Every clause and XOR row passes the [complete assignment check](profile.json);
the [independent Sage replay](sage_audit.json) verifies the twelve raw
points, all eleven S3 links, both seed equalities, cofactor-four
projection, and subgroup membership. The decompressed constructed XCNF
SHA-256 is
`9635437d5d34ecd95ac63eb077a2453b5493ea43ccd552cc52ce8cc2910c24de`.

The [published ECC2K-130 point](query_protocol.json) was queried with
all twelve masks, all ten intermediate reciprocals, and the four raw
target-preimage alternatives unpinned. One CryptoMiniSat worker used a
frozen 600-second construction-plus-search cap and 4-GiB combined RSS
limit. Its [public formula](public_query/system.xcnf.gz) has 119,042
variables, 875,983 CNF clauses, 42,285 XOR rows, 75,275 AND gates,
and decompressed SHA-256
`0314f3682d17cd5ea5a6e8c68637f809331cd7bd708e668c70eaa2ee3f2fe37e`.

| Public-point stage | Recorded result |
| --- | ---: |
| Target formula construction | 8.585 s |
| Active solver search | 590.453 s |
| Construction plus search | **599.038 s** |
| Post-search archive and receipt | 5.334 s |
| Sampled combined peak RSS | 664,043,520 B |
| Solver status | `CENSORED_TIME`, no SAT or UNSAT line |
| Independently verified public relations / novel rows | 0 / 0 |

The raw [solver log](public_query/solver.stdout.txt) records active
search, and the [terminal audit](terminal_audit.json) checks the frozen
source hashes, exact public point, compressed formula hashes, group
control, resource envelope, and timing boundary. The receipt's total
604.372-second process wall includes archiving after the search clock
stopped. CPU timing comparisons on this host remain exploratory without
an isolation record.

The [smaller-field six-pair control](../n41_upper_xor_projection_20261010/RESULT.md)
has an independently verified unpinned N41 public-point relation using
the same two-seed-equality policy. Its exact W14 support count gives a
group-wide mean of at most 33.324886 twelve-atom tuples per N131 subgroup
target before cross-pair column exclusions; that is a support bound, not
the relation yield of this fixed public point. The explicit same-seed
four-atom index used at N41 exceeds the N131 4-GiB budget by a factor
of at least 4,399, so this run tested a symbolic formula instead.

This measured stage has `candidate_id: null`. The next algorithmic step
is a target-conditioned pair-image membership and inversion kernel that
can use the exact W14 diagonal pair inverse while processing shared
seed-sum buckets without storing one key per four-atom state. Its first
gate is recovery of the archived N41 public relation from unpinned pair
outputs with bounded memory; the N131 gate must then measure accepted
ordinary-query relations and novel rank before factor-base logs and
single-target online timing are assessed.

Source and replay: [control generator](prepare.py), [six-pair circuit](circuit.py),
[formula builder](run.py), [query runner](query.py), [group lift](lift.py),
[Sage audit](sage_audit.py), and [terminal audit](terminal_audit.py).
The [checked runtime receipt](sage_runtime_info.json) records the local
Sage build used for the control and measured run.
