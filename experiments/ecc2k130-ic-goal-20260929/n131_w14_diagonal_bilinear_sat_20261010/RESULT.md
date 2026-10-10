# Bilinear W14 diagonal-pair coordinates on ECC2K-130

The five N131 W14 diagonal-pair leaves now use a **27-bit product
coordinate** rather than a full field multiplication in each reciprocal
S3 constraint. For `w_a,w_b` in the fourteen-dimensional source space,
`p=w_a w_b` lies in the span of `t^2,...,t^28`. With pair-output reciprocal
`z`, the exact join equation is

`(w_a+w_b)^2 + z^2 + pz + (pz)^2 = 0`.

Expanding `p` in its 27 product bits makes the last two terms bilinear in
those bits and the 131 bits of `z`. The [circuit](circuit.py) uses 3,537
bilinear ANDs per pair, plus 196 mask-product ANDs before sharing. Its
[constructed formula](constructed.xcnf.gz) passed a complete XCNF
assignment from ten group-verified diagonal atoms; 32 independently
audited pair outputs also satisfy the field equation. The construction
retains the exact curve `EC1N131Ckb1heb5f1998f20b`, the same W14 support,
82,200 actual projected factor-base points, 8,160 folded columns, and the
five repeated rotations `[0,0,26,26,52,52,78,78,104,104]`.

| Exact N131 stage diagnostic on the same published point | Source frame | Reciprocal sparse leaves | Bilinear pair coordinates |
| --- | ---: | ---: | ---: |
| Actual projected base points `B` | 82,200 | 82,200 | 82,200 |
| Folded columns `K` | 8,160 | 8,160 | 8,160 |
| Published formula AND gates | 59,049 | 72,785 | **64,698** |
| Published formula variables | 108,219 | 126,439 | **102,869** |
| Published formula native-XOR rows | 47,978 | 52,462 | **36,979** |
| Published formula CNF clauses | 635,469 | 676,669 | 652,408 |
| Published-point one-worker status at 120 s | `CENSORED_TIME` | `CENSORED_TIME` | `CENSORED_TIME` |

The bilinear change reduces AND gates by 8,087 relative to the reciprocal
sparse-leaf circuit, while remaining 5,649 above the source-frame circuit.
It reduces variables and XOR rows against both. Encoded public XCNF bytes
increase to **54,190,861**, so the smaller gate count is not a complete
size reduction. The [full-assignment receipt](profile.json) records 64,728
AND gates, 652,498 clauses, and 36,991 XOR rows on the constructed target;
its decompressed SHA-256 is
`dce19a4b7be0ded259cf5c8e15c4d725b815f7dfc00f86824cf7147e3adecb22`.

The [unpinned published-point query](public_query/result.json) gave the
solver all ten masks, eight intermediate reciprocals, and four raw target
preimages as alternatives. It used one CryptoMiniSat worker, a 4-GiB RSS
limit, and a frozen 120-second construction-plus-search gate. Formula
construction took **3.511 seconds** and active solver search **115.609
seconds**, totaling **119.120 seconds** at the search boundary. The solver
log shows active search with no terminal SAT or UNSAT line; sampled combined
RSS peaked at **1,099,857,920 bytes**. Archiving the formula and writing
the receipt added **2.024 seconds** after that boundary, so the receipt's
121.145-second process wall exceeds the search cap. The [terminal
audit](terminal_audit.json) preserves both intervals. The published formula
has decompressed SHA-256
`4202c4c721c0565dbb3aff17bd30fff47462d155189e7dc8f6957ab59dbbc4e9`.

This is a decomposition-stage proposal with `candidate_id: null`; the
published query yielded zero independently verified relations and zero
novel matrix rows. CPU timings on this host are exploratory without an
isolation receipt. The next circuit gate is the final target join: its
four preimages are fixed constants selected by one-hot flags, so the
last field product can be distributed over those four choices. That
should remove a full variable-by-variable multiplication while keeping
the exact public target and control fixed. A solver result still needs
independent group replay before relation yield and rank are measured.

The [construction protocol](protocol.json), [query protocol](query_protocol.json),
[checked Sage runtime receipt](sage_runtime_info.json), [raw solver
log](public_query/solver.stdout.txt), and compressed formulas bind the
source, input, resource cap, and observed outcome. The control point and
its independent Sage group audit are inherited by digest from the
[previous reciprocal experiment](../n131_w14_diagonal_sparse_sat_20261010/RESULT.md).
