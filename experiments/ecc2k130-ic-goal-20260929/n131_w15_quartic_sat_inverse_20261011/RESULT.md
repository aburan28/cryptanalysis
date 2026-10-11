# Direct quartic SAT inverse on an N131 W15 product-space control

An exact native-XOR circuit encodes one 13-term quartic factor of the
rotated four-atom resultant over **28 unpinned product-space bits**. The
archived N131 W15 positive product pair satisfies all **87,974 CNF
clauses** and **21,651 native-XOR rows**, checked against the full
serialized formula. One-worker CryptoMiniSat entered search and reached
the frozen **75-second parent cap** with `PARENT_TIMEOUT`, 119 logged
restarts, and no model or proof. The archived native degree-eight GCD
inverse had completed this same fixed-seed, fixed-output positive case
in 6.522 seconds. This direct Boolean encoding does not clear the
fixed-output gate; the useful next change is to reduce the native
field-arithmetic cost or generate target-compatible outputs jointly.

The field is `GF(2)[t]/(t^131+t^13+t²+t+1)` and the curve is
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is the
W15 common mask-XOR seed `13686` at Frobenius rotations `26,39`. The
fixed proposed raw four-atom output is the reciprocal x-coordinate
`1072442453979696659264084726754206488845` from the previously
checked constructed block. Its rotated source-product spaces each have
dimension 14, and the known product pair is independently archived in
the [four-atom control](../n131_w15_rotated_fouratom_inverse_20261010/control_result.json).
The [quartic specialization](../rotated_fouratom_factorization_20261010/n131_positive.json)
has exactly one factor vanishing at that product pair; this experiment
uses factor zero. The full resultant is the product of the two factors,
so any root of factor zero passes the algebraic resultant, while final
source-mask, column, and group replay would still be required before a
relation row could be used.

The [builder](build.py) represents each product as a linear combination
of 14 basis vectors. It forms their first product with 196 primary ANDs,
then shares powers and mixed monomials across the quartic's 13 terms.
The resulting [XCNF](factor0.xcnf.gz) has **50,960 variables, 29,281
AND gates, 87,974 CNF clauses, and 21,651 native-XOR rows**. The
[protocol](protocol.json) froze source and solver hashes, the positive
factor, one worker, 60-second solver limit, 75-second parent cap, and
4-GiB child RSS cap before construction and search. The
[builder receipt](factor0_build.json) binds the compressed formula.
The [independent assignment replay](audit_result.json) reconstructs the
known product codes `(5576,3)` and checks every serialized equation; it
also records the uncompressed formula SHA-256.

| Fixed-output product-space stage | Recorded result |
| --- | ---: |
| Unpinned Boolean variables | 28 primary product bits |
| Constructed positive assignment | 87,974 clauses and 21,651 XOR rows pass |
| CryptoMiniSat solver / parent limits | 60 / 75 s |
| Parent wall / sampled peak child RSS | 75.086 s / 82,608,128 B |
| Last logged restart / approximate conflicts | 119 / 31,000 |
| Terminal solver status | `PARENT_TIMEOUT` |
| Archived native inverse, same seed and output | 6.522 s query stage |

The [solver protocol](solver_protocol.json), [receipt](solver_result.json),
and [raw transcript](solver.stdout.txt) show active search; stderr is
empty. The [terminal audit](terminal_result.json) checks hashes, the
positive assignment, the frozen limits, restart activity, and the
bounded terminal status. The timings are exploratory on an unisolated
host, and the native and SAT methods have different implementation
boundaries. The positive short gate already failed to improve the
fixed-output inverse, so no additional negative-output SAT run or
ordinary public-point query was launched for this encoding.

This is a partial-sum stage with `candidate_id: null`. The complete IC
goal still requires target-conditioned output generation with free seeds
and pairs, verified ordinary N131 relations, novel rank, factor logs,
fresh target recovery, and a paired same-point rho interval.
