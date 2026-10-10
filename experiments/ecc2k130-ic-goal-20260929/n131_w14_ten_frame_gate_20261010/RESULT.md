# Full N131 W14 ten-source framed S3 gate

The Frobenius-frame leaf construction produces a **complete 51.2 MB
ten-source XCNF** on the exact ECC2K-130 W14 factor-base geometry. A
constructed target with ten distinct folded columns satisfies every
708,816 CNF clause and 66,330 native-XOR row, and an independent checked
Sage replay verifies the ten source points, five framed leaf links, four
upper links, raw group sum, cofactor-four target, and subgroup order. The
full construction completed in 12.66 seconds with 281 MB sampled Python
RSS, within its frozen 120-second/4-GiB gate.

The [source protocol](protocol.json) fixes the exact degree-131 field
`t^131+t^13+t²+t+1`, curve `y²+xy=x³+1`, prime subgroup order
`680564733841876926932320129493409985129`, W14 masks, ten rotations
`[0,13,26,39,52,65,78,91,104,117]`, actual usable projected base size
`B=164,400`, and 8,160 sign/Frobenius-folded columns. The curve ID is
`EC1N131Ckb1heb5f1998f20b`; the [official bridge](../n131_w2_m15_official_single_target_4g_20261003/bridge_audit.json)
binds the polynomial coordinates used here to the official field record.
The constructed target in [control.json](control.json) is a correctness
fixture. The [full-formula receipt](profile.json) and [checked-Sage
replay](sage_audit.json) record separate algebraic and group checks;
[Sage runtime information](sage_runtime_info.json) came from the repository
launcher. The exact constructed XCNF is
[archived as gzip](constructed_full.xcnf.gz), whose decompressed SHA-256 is
`8073518a78ad394f82fc3959b770c6850526149f4f19c232c770ad8d3496c7fc`.

| Frozen gate | Constructed group control | Published `ecc2k-130` point |
| --- | ---: | ---: |
| CNF clauses | 708,816 | 709,284 |
| Native-XOR rows | 66,330 | 66,366 |
| AND gates | 83,498 | 83,654 |
| Formula variables | 151,020 | 151,212 |
| Distinct-column exclusion clauses | 375,480 | 375,480 |
| Full assignment and independent group replay | PASS | Search capped |
| Formula construction wall | 12.66 s including assignment/check | 8.33 s |
| SAT search wall | — | 110.64 s |
| Total target-query wall | — | 119.12 s |
| Sampled peak memory | 281 MB Python RSS | 1.12 GB combined RSS |

The [published-point protocol](query_protocol.json) binds the official
polynomial-coordinate Q,
`(2309658012506412099988466246134815930289,
1578526100003023531340803776621036465818)`, source hashes, one thread,
4-GiB RSS ceiling, and 120-second total target-query wall cap. Masks,
signs, intermediate points, and the target-fiber branch were unpinned. The
[run record](public_query/result.json) gives status `CENSORED_TIME` after
119.125 seconds: 0.081 seconds target transport, 8.334 seconds formula
construction, 110.637 seconds solver, plus 0.073 seconds measured overhead.
The solver log records active search, no model or UNSAT status, empty
stderr, and a sampled combined RSS peak of 1,120,534,528 bytes. The exact
published formula is [archived as gzip](public_query/system.xcnf.gz), with
decompressed SHA-256
`f48b3eb55e570d58e8af2a51f2067442e0c73763cf12b0e40db1eb3afd117f40`.
The [terminal audit](terminal_audit.json) checks the frozen source, both
compressed formulas, constructed assignment, Sage replay, official input,
query cap, and archived solver outputs.

This is a `Q` proposal with `candidate_id: null`: a capped SAT query gives
no verified ordinary relation or rank increment on the published target.
The formula fits comfortably in memory, so the next experiment should
reduce target-dependent search. One concrete route is to pair equal
Frobenius rotations, apply the exact joint pair-output inverse to generate
compatible pair domains, and use the upper S3 links to prune those domains.
That changes the factor-base policy, so first enumerate its actual `B` and
folded columns, then measure ordinary-query relation yield and novel rank
on frozen public inputs. Retain this ten-distinct-rotation formula as the
same-target SAT comparator. CPU wall figures here are algorithmic diagnostics
on an ordinary host, not controlled speedup measurements.
