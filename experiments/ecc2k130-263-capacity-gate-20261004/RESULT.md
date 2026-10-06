# ECC2K-130 degree-263 capacity gate: arity and orbit policy

The exact counting gate rules out high one-shot **uniform-target** coverage
for the screened W24/m5, W28/m4 and W35/m3 policies, before choosing an
F4, F5, SAT, FES, Gray-code or crossbred solver. W28/m5 and W35/m4 pass
only this *necessary capacity* screen: their actual factor-base sizes,
natural PDP yield, useful rank and full costs remain unknown. The next
comparison should measure W24/m6 versus W28/m5 with actual-base/column
ledgers and held-out ordinary queries; a solver-only benchmark cannot
decide between them.

The [protocol](PROTOCOL.md) and [configuration](CONFIG.json) were committed
as `41348c06286beec8d7f35c4556883224ed438eaf` and opened as draft
[PR #272](https://github.com/aburan28/cryptanalysis/pull/272) before the
table was generated. The derivation used the exact 130-bit subgroup order
`680564733841876926932320129493409985129` from the verified degree-263
route and reproduced the three existing W-screen capacity rows. The
[machine-readable result](result.json) retains 12 threshold cells and five
W-policy cells; the [independent receipt](verification.json) checks every
minimality boundary using a separate binomial recurrence.

For any actual base of `B` subgroup points, at most `C(B+m-1,m)` unordered
`m`-multisets exist. The table gives the **minimum necessary** `B` for that
count even to reach 1% or 50% of the `r-1` nonidentity targets. It permits
repeated summands and optimistically assumes all multiset sums differ.
Actual support can be lower. A guided or nonuniform query law needs its
own analysis.

| Summands `m` | Minimum actual `B` for 1% | Minimum actual `B` for 50% | Sign-only columns at 1% `B` | Sign + order-131 orbit columns if closed | Raw 17-byte log vector, sign-only |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 3,443,553,994,135 | 12,686,161,381,663 | 1,721,776,997,068 | 13,143,335,856 | 29,270,208,950,156 B |
| 4 | 3,574,951,633 | 9,506,325,303 | 1,787,475,817 | 13,644,854 | 30,387,088,889 B |
| 5 | 60,591,280 | 132,496,417 | 30,295,640 | 231,265 | 515,025,880 B |
| 6 | 4,121,293 | 7,910,341 | 2,060,647 | 15,731 | 35,030,999 B |
| 7 | 617,668 | 1,080,105 | 308,834 | 2,358 | 5,250,178 B |
| 8 | 151,283 | 246,697 | 75,642 | 578 | 1,285,914 B |

These column counts are alternative **policy floors**, not measured matrix
dimensions, and assume no base logs are initially known. Sign folding has
orbits of at most two. On the Koblitz source, degree-2 Frobenius has order
131 on every nonidentity point of this prime subgroup: its 131st power
fixes every `F_(2^131)` point, while a point fixed by its first power would
lie in `E(F_2)`, a group of order four. Since 131 and `r` are odd, sign
doubles each nonzero Frobenius orbit to 262. The `B/262` floor requires
the **base itself** to contain complete signed Frobenius orbits. It is not
a free discount for a polynomial-W prefix. A closed base at a threshold
may need to round its actual size up to the next multiple of 262. The
byte column prices only a
raw vector of residues; it excludes relation storage, base construction,
solver memory, transport and matrix work.

The first three W-policy bounds independently match the [frozen W
screen](../ecc2k130-263-w-screen-20261004/README.md):

| Polynomial-W policy | Maximum possible usable `B` | Upper bound on uniform one-shot support | 1% possible? |
| --- | ---: | ---: | --- |
| W24/m5 | 33,554,430 | 0.0005208333333333311 | no |
| W28/m4 | 536,870,910 | 0.00000508626300188553 | no |
| W35/m3 | 68,719,476,734 | 0.0000000794728596970514 | no |
| W28/m5 | 536,870,910 | 1 (capped) | unresolved |
| W35/m4 | 68,719,476,734 | 1 (capped) | unresolved |

The last two `1` values are saturated **upper** bounds, not observed hit
rates. W24/m6 is also not eliminated by its `B_max` of 33,554,430 versus
the 4,121,293-point 1% necessary threshold, but its actual `B`, solver
cost and useful rank remain unmeasured. This makes W24/m6 and W28/m5
better next *tests* than repeating the excluded lower-arity cells. It
does not make either a viable IC candidate. The catalog's existing
`n131_poly_d24_m6` and `n131_poly_d28_m5` records stay proposals with
`candidate_id: null`.

## The ring change and the four policies

The [verified route](../koblitz-polynomial-w-pair-20260925/README.md)
changes the endomorphism-order conductor from 1 to 263. The source order
is `Z[π₂] = O_K`, whereas the descendant order is `Z + 263 O_K`; the
source's degree-2 Frobenius `π₂` is not an element of the descendant
order. This removes that cheap endomorphism on the native descendant.
There is still a conjugate order-131 **group action** on the prime
subgroup through the isogeny and its inverse. Building or recognizing its
orbits on a descendant-native base has a cost and may destroy a compact
polynomial-W membership rule; neither is priced here. Sign-only and fully
orbit-closed columns are stated policies, not absolute curve-level
performance limits.

The isogeny is a group isomorphism on this prime-order subgroup. An exact
group-sum PDP has identical mapped hit sets for `source` and
`transported`, and likewise for `descendant_native` and `pullback`.
Only two geometries can change natural group-level coverage; all four
implementations can change construction, membership, solver and map
costs. The merged N39 four-policy toy demonstrated these equalities on
held-out points. The N131 equal-actual-`B` four-policy PDP experiment and
its runtime accounting remain open.

The [density screen](../ecc2k130-263-w-screen-20261004/README.md) found
no two-point material gain at W24/W28 and left W35 inconclusive. The next
gate must certify **actual** usable `B` and effective columns for matched
source/native bases, then compare held-out ordinary m5/m6 PDP status mix,
cost per verified novel relation, and rank. Map costs and any induced
orbit closure belong in that ledger. A complete single-target DLP and
paired rho interval would come after those stage gates. No `IC1` result,
target logarithm, natural yield, online/cold time, or rho speedup is
issued here; those result fields are `null`.

## Reproduction and verification

The exact inputs are pinned in [SHA256SUMS](SHA256SUMS). Python 3.13.1
produced the table with integer arithmetic; no Sage job or timed
benchmark was run. From a clean checkout, use fresh output paths:

```sh
python3 experiments/ecc2k130-263-capacity-gate-20261004/derive.py \
  --out /tmp/ecc2k130-263-capacity-result-new.json
python3 experiments/ecc2k130-263-capacity-gate-20261004/verify.py \
  --result /tmp/ecc2k130-263-capacity-result-new.json \
  --out /tmp/ecc2k130-263-capacity-verification-new.json
cmp /tmp/ecc2k130-263-capacity-result-new.json \
  experiments/ecc2k130-263-capacity-gate-20261004/result.json
shasum -a 256 -c experiments/ecc2k130-263-capacity-gate-20261004/SHA256SUMS
```

The independent verifier accepted all 12 minimum-`B` boundaries and five
W cases, including direct equality with the three frozen screen rows. A
copied result with the m5/1% `B` increased by one was rejected at the
boundary assertion. Optimized Python is refused so assertions cannot
silently disappear. The producer and verifier digests are in the JSON
receipts; no failed or censored empirical rows were generated.
