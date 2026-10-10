# Linear-source seven-summand reduction and exact W19 challenge query

On the prime subgroup, the seven same-sign diagonal blocks share the group
factor `1+φ`, where `φ` is Frobenius. Moving that factor to the target gives

`4 Σᵢ φ^rᵢ Pᵢ = (1+φ)⁻¹Q`.

For each raw source point `Pᵢ` made from `w = u²+u`, the transformed coordinate
`1/(x(Pᵢ)+1)` is exactly `u`, an F₂-linear function of its source mask.
This removes seven nonlinear diagonal-leaf constraints from the previous
fourteen-leaf encoding while retaining exact cofactor-four transport and the
same signed-Frobenius column policy. A checked-Sage audit verified the target
transport and all three earlier public N41 group relations.

| Degree-41 public-point stage, same frozen `Q` | Diagonal output leaves | Linear source leaves |
| --- | ---: | ---: |
| XCNF variables | 28,480 | 17,852 |
| CNF clauses / native XOR rows | 50,195 / 11,795 | 31,612 / 7,548 |
| AND gates | 16,147 | 10,053 |
| Exact known-row formula control | pass | pass |
| Unpinned CryptoMiniSat query | `CENSORED_TIME`, 115.114 s online | `CENSORED_TIME`, 115.111 s online |

The reduction is 37.3% in variables and 37.0% in clauses. Both solver runs
used one worker on the same public point and a 4-GiB RSS cap; their wall
times are exploratory on an unisolated host. The linear-source
[`preflight`](preflight/receipt.json) checks a complete satisfying assignment,
and [`checked Sage`](sage_audit.json) independently verifies the group
transport. The [public result](public/result.json), [raw search log](public/solver.stdout.txt),
and [terminal audit](terminal_audit.json) retain the active search and cap.

For the exact degree-131 W19 source, a frozen native enumeration and an
independent full checked-Sage mask and orbit audit give **262,390 rational
masks**, **262,151 signed-Frobenius columns**, and **3,673,460 distinct
subgroup-usable factor-base points** across rotations
`[0,18,36,54,72,90,108]`. Every pair of rotated W19 windows has binary
rank 38, establishing their disjoint source sets; the prior reciprocal
audit gives zero overlap under the cofactor-four x map. The
[`support audit`](sage_support_audit.json) checks every one of the 524,287
nonzero masks against the saved [mask/orbit map](support_w19.tsv), then
reconstructs every source Frobenius alias from subspace intersections.

The exact W19 control formula passed a full assignment check and independent
Sage group replay under a 120-second/4-GiB construction cap:

| Degree-131 stage | Observation |
| --- | ---: |
| Control XCNF variables / clauses / native XOR rows | 120,681 / 2,051,166 / 50,939 |
| Control construction and assignment wall / peak RSS | 12.224 s / 862,371,840 B |
| Published-point XCNF variables / clauses / native XOR rows | 120,708 / 2,051,223 / 50,947 |
| Published-point formula size, raw / archived | 138,781,248 / 7,989,578 B |
| Published-point online wall / solver phase | 580.999 / 575.158 s |
| Published-point combined peak RSS / verified relations | 3,523,805,184 B / 0 |
| Published-point terminal status | `CENSORED_TIME`, solver wall cap |

The online clock started before published-point validation, target transport,
fiber construction, and XCNF generation. It includes the full one-worker
solver attempt and producer model check. The archived
[`control XCNF`](n131_control.xcnf.gz), [control result](n131_control_result.json),
and [independent replay](n131_control_audit.json) establish the encoding.
The [published-point protocol](n131_public_protocol.json) binds the exact
challenge input, code, checked Sage runtime, 600-second online cap, 4-GiB
combined RSS cap, and solver flags. Its [result](n131_public/result.json),
[search log](n131_public/solver.stdout.txt), archived
[XCNF](n131_public/system.xcnf.gz), and
[terminal audit](n131_public/terminal_audit.json) preserve the censored
observation. The first control-builder attempt stopped at an import cycle
before formula construction; its [failure receipt](n131_control_bootstrap_failure_v1.json)
and the versioned corrected protocol are retained.

**Next method gate:** enumerate a smaller W14 source and test ten linear
source summands on an exact lower-degree public-point control, then a frozen
degree-131 formula and ordinary query if the source-bound work and memory
fit. A half-rational W14 source would give roughly `2^14` signed states per
block and `2^(140)/r` uniform-group support across ten blocks; those are
predictions until the masks, columns, public-query yield, and useful rank are
measured. The complete single-target IC objective still requires enough
independent rows for factor-base logs, final matrix solving, fresh-target
scalar verification, and a matched rho timing receipt. This method remains
a `Q` proposal with `candidate_id: null`.
