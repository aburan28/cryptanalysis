# Frobenius-frame low-product S3 links for ten-source decomposition

Moving each leaf-pair S3 equation into its own Frobenius frame cuts the exact
N41 public-point formula from 47,462 to **35,915 CNF clauses** and from
15,265 to **11,416 AND gates**. The complete framed XCNF accepts the
independently checked ordinary relation found by the native 4+6 join. On the
exact N131 W14 ten-rotation policy, all five leaf links use **7,585 AND
gates** each in this frame, compared with 11,404–11,633 for the generic
links. These are construction and correctness results; the bounded public
SAT-stage query is recorded below.

Let `A(v)=v²+v` and `phi(v)=v²`. A generic S3 link for transformed
coordinates `u_a,u_b,z` uses

`A(u_a) A(u_b) A(z) = (u_a+u_b+z)²`.

For a source mask `c`, `A(u_c)=sum_i c_i w_i` is linear in the W-basis. In
the leaf pair at rotations `r,r+delta`, apply `phi^(-r)` to the whole
identity. Both source W-bases are then `W,phi^delta(W)` and the output is
`phi^(-r)(z)`. This field automorphism preserves the equation and exact
group-sum relation. The inverse-Frobenius output transform is included in
the profile counts. The four upper S3 links retain the generic encoding.

| N41 formula on the same public point | Generic ten-source S3 | Direct low-product | Pair-local frame |
| --- | ---: | ---: | ---: |
| AND gates | 15,265 | 14,442 | **11,416** |
| CNF clauses | 47,462 | 44,993 | **35,915** |
| XOR rows | 11,249 | 10,533 | **8,957** |
| Variables | 26,896 | 25,357 | **20,755** |
| Full XCNF assignment from independently replayed public relation | PASS | PASS | **PASS** |

The N41 curve is `EC1N41Ckb1h7d5e80d3c4d0`; the source is W5 with ten
rotations `[0,4,8,12,16,20,24,28,32,36]`, actual usable factor-base
size `B=340`, and 14 folded columns. The masks, signs, group sum, Sage
replay, and target point come from the frozen
[native relation](../n41_w5_ten_native_join_20261010/RESULT.md). Both
[direct](audit.json) and [pair-frame](frame_audit.json) audits complete every
SAT auxiliary wire and check every CNF and native-XOR row, then decode the
same unpinned public relation. The formula files and SHA-256 digests are
archived with those audits.

| N131 W14 leaf link, actual rotation pair | Generic AND / clauses | Direct low-product AND / clauses | Pair-frame AND / clauses |
| --- | ---: | ---: | ---: |
| `0,13` | 11,404 / 34,343 | 7,585 / 22,886 | **7,585 / 22,886** |
| `26,39` | 11,633 / 35,030 | 11,633 / 35,030 | **7,585 / 22,886** |
| `52,65` | 11,633 / 35,030 | 11,633 / 35,030 | **7,585 / 22,886** |
| `78,91` | 11,633 / 35,030 | 11,633 / 35,030 | **7,585 / 22,886** |
| `104,117` | 11,633 / 35,030 | 11,633 / 35,030 | **7,585 / 22,886** |

The [N131 profile](n131_leaf_profile.json) uses the exact degree-131 field
`t^131+t^13+t^2+t+1`, the frozen W14 source and ten distinct rotations of
`EC1N131Ckb1heb5f1998f20b`. Its boundary is one S3 arithmetic leaf link:
it excludes rationality constraints, folded-column distinctness, upper
links, target fiber, and solver search. The optional `0,0` row in the raw
profile illustrates the coordinate sparsity when both leaves share one
rotation; it is a different factor-base policy and is not used in the
ten-rotation comparison.

The [frozen solver protocol](solver_protocol.json) binds the framed N41
formula, source, public point, one-thread CryptoMiniSat command, and
115-second/4-GiB SAT-stage cap. Search started and reached 949,000 logged
conflicts. The [run](solver_run/result.json) ended `CENSORED_TIME` at
115.051 seconds, with no model lines, empty stderr, and sampled combined
RSS 122,241,024 bytes. The prior generic-formula query was also
`CENSORED_TIME` at its 115.426-second cap. These two capped queries do not
establish a solver wall-time improvement. This proposal has
`candidate_id: null` because N131 ordinary relation yield, rank, and the
complete target pipeline have not been measured.

The next gate is a complete N131 W14 ten-source framed formula with a
checked constructed assignment and a frozen unpinned published-point
query. If SAT remains capped, use the pair-local identity with the existing
same-rotation inverse to generate and prune compatible pair outputs before
the upper four links; measure verified relation yield and novel rank per
ordinary query under the same 4-GiB envelope.
