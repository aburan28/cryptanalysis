# Exact adjacent W14 pair-output inverse on ECC2K-130

An adjacent Frobenius-window pair has a **complete output inverse built
from a 61-column joint system and a seven-column conditional product
solve** on the degree-131 challenge field. The source seed sum has rank
21 and the product space has rank 40. A proposed output first faces a
binary-linear consistency check. If the joint system has a kernel, the
inverse enumerates its coefficient solutions; for each proposed seed sum
and product, a second linear solve determines the overlapping seed bits.
It recovered all 16 independently constructed pair outputs, rejected all
16 uniform field controls at the span gate, and completed structured
rank-deficient controls of nullity 12 and 6. Independent checked Sage
recomputed the full-rank decisions and replayed all 16 raw group sums.

The ten-window schedule `[0,1,26,27,52,53,78,79,104,105]` has
**B=163,800 distinct subgroup-usable points** before folding and
**K=8,160** signed-Frobenius columns. A separate checked-Sage census
enumerated the cofactor-four projected coordinates and confirmed `B`.
This nearly doubles the same-rotation W14 base size of 82,200 while
expanding the joint output span from 41 to 61 columns. Both schedules
have 8,220 rational masks available to each leaf, so this experiment
does not infer a higher ordinary relation yield from the larger union.

## Algebra and frozen policy

The curve is `y²+xy=x³+1` over
`GF(2)[t]/(t^131+t^13+t²+t+1)` with prime subgroup order
`680564733841876926932320129493409985129`, curve ID
`EC1N131Ckb1heb5f1998f20b`. The source is the audited W14 space
`W=span(t,...,t^14)` with 8,220 rational masks and 8,160 folded columns.
For one pair, `w_a∈W`, `w_b∈W²`, `s=w_a+w_b`, `p=w_a w_b`, and
`u_s=HT(s)`. If `z=1/(x(P_a+P_b)+1)` is the transformed raw pair-sum
coordinate, then

`z² = u_s² + (z²+z)p`.

The union `W+W²` has dimension 21. Its 28 seed-coordinate columns have
a seven-dimensional kernel, so a fixed `s` has 128 raw seed-mask
representations before rationality and column filtering. The products
`t^i(t^j)²`, `1≤i,j≤14`, span exactly `t³,...,t^42`, dimension 40.
For nonexceptional `z`, the inverse solves the 131-row binary system
formed by 21 columns `u_basis²` and 40 columns `(z²+z)p_basis`, with
right side `z²`. A full-rank solution determines `s,p`. When the rank
drops, [the complete inverse](complete_inverse.py) enumerates every
coefficient solution. For fixed `s`, all seed representations have the
form `(w1+h,w2+h)` with `h∈W∩W²`. Their products are
`p0+h²+sh`, an affine map of seven binary overlap bits. A seven-column
solve recovers every mask pair with the required product, after which
source support, folded-column distinctness, and exact raw group sum are
checked. The `s=0` branch contains 60 supported coordinate overlaps,
all in the same folded column and therefore excluded. `z=0` is not a
finite transformed x coordinate; `z=1` would require
`HT(s)=1` and hence both `s=0` and `HT(s)=0`, a contradiction.

The [frozen protocol](protocol.json) fixes the source hashes, local PRNG
seed, 16 constructed pairs, 16 independent uniform field controls,
120-second stage cap, and 4-GiB RSS cap. This is a proposal-stage pair
primitive with `candidate_id: null`; the panel does not specify a complete
relation collector, factor-log solve, or target descent.

## Results and independent checks

| Exact stage measure | Result |
| --- | ---: |
| Seed sum / product / joint span | 21 / 40 / 61 |
| Joint rank on all 32 nonexceptional outputs | 61 |
| Constructed pair outputs recovered by complete inverse | 16 / 16 |
| Uniform field controls rejected at span gate | 16 / 16 |
| Rank-deficient `z=2`: rank / nullity / exact coefficient solutions | 49 / 12 / 4,096 |
| Rank-deficient `z=18`: rank / nullity / exact coefficient solutions | 55 / 6 / 64 |
| Rank-deficient inconsistent `z=3` | rank 49, span rejected |
| Seven-column solver versus 128-representation scan | 48 / 48 matching controls |
| Sage raw group and subgroup replays | 16 / 16 |
| Source masks / projected factor-base points / folded columns | 8,220 / 163,800 / 8,160 |
| Complete stage wall / peak RSS | 51.206 s / 31,571,968 B |
| Median positive / control inverse query | 1.686 / 0.888 ms |
| Complete inverse panel wall / peak RSS | 0.710 s / 20,676,608 B |

The first stage wall includes all pair queries, raw group checks, and a
target-independent source-union enumeration. The [complete inverse panel](complete_result.json)
reuses those 32 coordinates and adds rank-deficient and exceptional
controls. Its 48 fixed-sum comparisons include all 16 positives and 32
rank-deficient coefficient solutions; each seven-column result agreed
with a direct scan of all 128 overlap representations. Both consistent
rank-deficient controls exhausted their coefficient spaces and had zero
supported raw pair candidates. The query medians are
exploratory CPU diagnostics on an unisolated host; they are not an
online single-target IC/rho comparison. The [run receipt](result.json)
retains every output, recovered pair, status, and query interval.

The [independent Sage inverse audit](sage_audit.json) rebuilt the 61-column
matrices and subgroup-point witnesses. The [subspace audit](sage_union_audit.json)
found rank 21 for the five adjacent window pairs and rank 28 for the
other 40 window pairs. Each adjacent intersection contributes exactly
60 rational x coordinates, giving `10×8,220−5×60=81,900` raw x
coordinates. The [projected-point audit](sage_projected_audit.json)
applied the binary-curve doubling law to every source mask and enumerated
81,900 distinct projected x coordinates, each with two signs. The
[checked Sage runtime receipt](sage_runtime_info.json) predates these
audits. Their frozen protocols bind source, run, support, and runtime
hashes.

The first Sage inverse verifier squared the already rotated second leaf
again and stopped on its group assertion. Its [failure receipt](audit_failure_v1.json),
[source](sage_audit.py), and [frozen input](audit_protocol.json) are retained;
the corrected [v2 source](sage_audit_v2.py) reuses the unchanged stage
result and passes all independent checks. The first [joint inverse source](run.py)
did not enumerate the rank-deficient branch; the separately frozen
[complete inverse protocol](complete_protocol.json) and panel close that
branch while preserving the first result unchanged.

## Next target-conditioned gate

This inverse is useful only after the upper S3 chain proposes a pair
output. The next solver experiment should keep several sparse pair-output
domains coupled to the fixed public point and call this inverse before
expanding their 128 seed representations. First compare the 41-column
same-rotation and 61-column adjacent gates on a frozen unpinned N41 public
point with complete failed-probe, relation, and rank accounting. Promote
the adjacent schedule to N131 only if that joint method has a source-bound
work and memory projection below one worker, 600 seconds, and 4 GiB;
then query the frozen public point and independently replay a relation.
