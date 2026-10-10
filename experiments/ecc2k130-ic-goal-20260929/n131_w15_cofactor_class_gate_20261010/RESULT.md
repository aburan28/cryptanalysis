# Exact W15 cofactor-class gate for five-pair search

The W15 source admits a **32-KiB exact mask table** for the raw point's
cofactor class. Its bit is `Tr(H(w²)/w)`, where `w=1/x(P)` and `H` is the
odd-degree half-trace. The complete 15-bit census classified **8,295**
usable masks in the subgroup and **8,146** in its order-two coset. An
independent checked-Sage audit multiplied both signed lifts of 256
deterministically chosen masks by the subgroup order and matched all
**512** class predictions. No folded column mixed classes. This table is
an exact and inexpensive native validation filter for known masks.

The class bit does not give the missing whole-family search filter. Every
one of the **32,767** nonzero W15 XOR seeds has usable distinct-column
pair states in *both* classes. A complete Walsh census found 7,660–8,856
signed pair states per seed in class zero and 7,664–8,856 in class one;
an independent direct enumeration replayed 84 frozen seeds, including the
extrema. Over the usable masks, four explicit parity certificates rule out
every Boolean polynomial of degree at most four for this bit. Its full
15-bit algebraic normal form has degree 14 and 16,445 terms. The next
search gate therefore remains target-conditioned S3 elimination across
multiple free pair blocks, with the class table available for cheap
witness screening.

## Exact character

Work on `y²+xy=x³+1` over `GF(2)[t]/(t^131+t^13+t²+t+1)`, with subgroup
order `r=680564733841876926932320129493409985129` and curve ID
`EC1N131Ckb1heb5f1998f20b`. The W15 source coordinate is
`w∈span(t,...,t^15)`; its absolute trace is zero. For a rational point
`P=(x,y)` with `x=1/w`, set `u=y/x`. The curve equation gives
`u²+u=x+w²`, hence `Tr(x)=Tr(w)=0`. Such a point has a half because the
doubling x-coordinate is `λ²+λ`. For a root `λ²+λ=x`, the half has
`x(R)²=y+(λ+1)x`. It is divisible by four precisely when
`Tr(y+(λ+1)x)=0`.

Now `v=u+λ` satisfies `v²+v=w²`. Since `Tr(x)=0`, the class test becomes
`Tr(v/w)`. The half-trace `H(w²)` supplies one root, and changing roots
adds `Tr(1/w)=Tr(x)=0`; thus

`class(P) = Tr(H(w²)/w)`, with class zero iff `[r]P=O`.

Both signs of a raw source point have the same class: negation changes
`y` by `x`, whose trace is zero. Frobenius rotations preserve the class.
The prior [trace certificate](../n131_w15_middle_trace_public_gate_20261010/trace_proof.json)
fixes the polynomial-basis trace support; the new
[source-frozen census](census.json) evaluates the formula on every
15-bit mask. Its [Sage audit](audit.json) checks group multiplication
independently on selected rational masks. The complete bytes are retained
in [class_bits.bin](class_bits.bin), indexed by mask.

## Relation geometry and obstruction

| Exact W15 source statistic | Value |
| --- | ---: |
| Rational nonzero masks / folded columns | 16,441 / 16,381 |
| Raw subgroup class / order-two class masks | 8,295 / 8,146 |
| Signed unordered pair states, class zero / one | 270,295,552 / 270,284,280 |
| Nonzero seeds with either class absent | 0 |
| Class-zero pair states per seed | 7,660–8,856 |
| Class-one pair states per seed | 7,664–8,856 |
| Full-mask ANF degree / terms | 14 / 16,445 |
| Lowest ruled-out polynomial degrees on usable masks | 1, 2, 3, 4 |

For the previously frozen target-independent prefix masks `4,17`, both
raw source points have class one, so their sum lies in the subgroup. If
each of the five free pairs also has class-zero sum, all twelve raw
points sum in the subgroup and the search can select the unique subgroup
four-preimage of the projected public target. The exact
[colored distinct-column count](count.json) is
**1,434,898,473,217,176,753,500,613,063,519,241,374,105,600**
signed five-pair tuples. That is **2,108.394 per uniform subgroup target**
before excluding zero intermediates, or 3.1254% of the unrestricted
five-pair source count. The [independent coefficient replay](count_audit.json)
agrees using the after-prefix column polynomials
`(1+x)^8236(1+2x)^28(1+3x)` and `(1+x)^8087(1+2x)^27` for classes zero
and one. This is source density, not measured public relation yield.

The [degree protocol](degree_protocol.json) fixed degrees 1–4 before
testing. Each [producer row](degree_result.json) contains a subset of
usable masks whose monomial evaluations XOR to zero while the class
labels XOR to one; the separate [certificate audit](degree_audit.json)
replays those parities without the producer's elimination. The
[seed protocol](seed_protocol.json) likewise fixed all nonzero seeds before
the Walsh [count](seed_result.json), and its [direct audit](seed_audit.json)
re-enumerates selected seed pairs. The read-only [verifier](verify.py)
checks all source hashes, count identities, and degree certificates.

The independently checked [curve order](../../ic-candidate-catalog/measurements/2026-09-30/n131_cofactor_character_sage_verification.json)
is `4r`, so this raw-source class supplies one bit
on the W15 points already in `2E`; after cofactor projection, the
prime-order target group has no nontrivial small 2-group quotient. The
class filter can reject known-mask witnesses and select a target
preimage, but cannot replace target-coupled point-addition constraints.
The complete IC candidate ID remains `null` pending ordinary N131
relations, useful rank, factor logs, and single-target recovery. The next
experiment should generate candidate partial-sum outputs from the public
target while at least four pair blocks remain free, check them with the
existing exact pair inverse, and record ordinary relation yield and novel
rank on the frozen N41 control before an N131 resource projection.
