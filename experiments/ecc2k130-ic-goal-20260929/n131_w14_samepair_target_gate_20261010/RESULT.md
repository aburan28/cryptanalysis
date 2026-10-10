# Five same-rotation W14 pairs in the full ECC2K-130 relation system

Five equal-rotation W14 leaf pairs reduce the **complete N131 ten-source
constructed formula** to 59,146 AND gates, 635,760 CNF clauses, and
47,997 native-XOR rows. A full assignment from ten distinct audited
source masks satisfies every row, and the checked Sage build independently
replays the raw group sum, five framed pair links, four upper links,
cofactor-four projection, and subgroup membership. The factor-base policy
uses rotations `[0,0,26,26,52,52,78,78,104,104]`, giving **82,200 actual
usable projected points** and 8,160 folded columns on the exact
`EC1N131Ckb1heb5f1998f20b` curve.

The five pair controls are the first five independently verified positive
outputs from the [W14 polynomial pair inverse](../n131_w14_polynomial_pair_inverse_20261010/RESULT.md).
Their ten folded columns are distinct. The [v2 protocol](protocol_v2.json)
binds those masks, the repeated-rotation policy, source hashes, and the
120-second/4-GiB construction gate. The [complete assignment receipt](profile.json)
records 15.814 seconds and 154,583,040 bytes sampled Python RSS, and the
[independent Sage replay](sage_audit.json) records the group and field
checks. The exact formula is [archived as gzip](constructed_full.xcnf.gz),
with decompressed SHA-256
`7bada067a8b8cc28fb6ea69458c744c32e45f6b620d5abb1747770990e0d68d0`.

The first preflight was a [preserved producer failure](failure_v1.json):
its formula builder selected the ten distinct rotations from the source
support record while its control used the five repeated rotations. The
invalid formula and traceback condition were isolated before any solver
query; the [failed formula](failure_v1.xcnf.gz) is archived under its exact
digest. The corrected source uses the rotations in the frozen v2 protocol.

| Exact formula on the same curve and published point | Ten distinct rotations | Five repeated pairs |
| --- | ---: | ---: |
| Actual factor-base points `B` | 164,400 | **82,200** |
| Folded columns `K` | 8,160 | 8,160 |
| Published formula AND gates | 83,654 | **59,049** |
| Published formula CNF clauses | 709,284 | **635,469** |
| Published formula native-XOR rows | 66,366 | **47,978** |
| Published formula variables | 151,212 | **108,219** |
| One-point query status at 120-second cap | `CENSORED_TIME` | `CENSORED_TIME` |

The [published-point protocol](query_protocol.json) binds the official
polynomial-coordinate `ecc2k-130` target, one thread, 4-GiB RSS limit,
and 120-second total query cap. All ten masks, signs, middle points, and
four target-fiber choices were unpinned. The [run](public_query/result.json)
records 0.027 seconds target transport, 4.434 seconds formula construction,
114.528 seconds of active CryptoMiniSat search, and 119.052 seconds total
query wall. It ended `CENSORED_TIME` with no model or UNSAT status, empty
stderr, and sampled combined peak RSS 708,526,080 bytes. Its exact
[published formula](public_query/system.xcnf.gz) has decompressed SHA-256
`ea855759b255d5623a165b59e8defd2e96356210471e3191435f7eb4aa7acda4`.
The [terminal audit](terminal_audit.json) checks both frozen protocols,
the preserved v1 failure, compressed formulas, constructed assignment,
Sage replay, published target, cap, and solver logs.

The smaller formula and lower sampled memory are construction results;
both public searches reached their caps, and the CPU host lacks an
isolation receipt. This remains a proposal with `candidate_id: null`.
The next experiment should make pair outputs **forward-generated** from
source masks and a root bit, then apply the exact W14 pair inverse as a
checker when the upper S3 links propose a pair output. The target-dependent
gate is verified ordinary relation yield and novel matrix rank, followed
by factor-base logs and single-target scalar recovery.
