# Same-seed four-atom output rank saturates the quadratic feature space

The two constrained four-atom blocks in the frozen N41 W6 six-pair method
have **exactly the rank permitted by their finite output sets** in the
821-dimensional quadratic feature space on output `x` bits. Every one of
the 63 nonzero seed bins satisfies

`rank(s) = min(number of distinct x outputs in bin s, 821)`.

Thus the seed equality supplies no additional quadratic annihilator of an
*individual block output* in this feature family. Independent installed
Sage replay checked 100 four-atom witnesses and reranked every block-A
bin. A separate GF(2) Frobenius audit checked that all 51,840 block-B
witnesses are the tenth Frobenius rotations of the corresponding block-A
witnesses; direct block-B rank computation matched every bin. The
[terminal audit](terminal_audit.json) binds the executed sources, data,
rank agreements, and exact N131 transfer arithmetic.

## Frozen N41 output experiment

The field is `GF(2)[t]/(t^41+t^3+1)` and the curve is
`y²+xy=x³+1`, with subgroup order `549756390943`. The source is the
previously frozen six W6 windows at rotations `0,5,10,15,20,25`, with
**B=384** subgroup-usable source points and **K=26** folded columns.
For each pair, both source masks and signs vary, but its two columns must
be distinct. A constrained four-atom block joins two pairs with the same
nonzero six-bit mask-XOR seed and four distinct columns. The source input
contains the frozen public point `Q=(1458168294740,1672312028033)`;
the output census itself depends only on the source windows.

The [protocol](protocol.json) froze the input and executable hashes before
the block-A census. The [exact census](quad_outputs.tsv) enumerated the
rotations `10,15`; the [second protocol](protocol_b.json) did the same for
rotations `20,25`. Each block has 1,956 signed pair states per window,
51,840 finite four-atom witnesses, and **25,920 per-bin distinct output
`x` coordinates counted with seed multiplicity**. Each bin has between
144 and 832 distinct `x` values, with median 416. Sign reversal accounts
for the two witnesses per per-bin `x` in this census.

| Exact output feature | Block A | Block B |
| --- | ---: | ---: |
| Four-atom witnesses | 51,840 | 51,840 |
| Sum of per-bin distinct `x` counts | 25,920 | 25,920 |
| Nonzero seed bins | 63 | 63 |
| Quadratic features: constant, bits 1–40, pair products | 821 | 821 |
| Bins with rank below `min(distinct x,821)` | **0** | **0** |
| Bins at full feature rank 821 | 1 | 1 |

The [rank implementation](rank.py) performs exact GF(2) elimination on
the 821 Boolean monomials. [Sage's independent M4RI rank
audit](sage_audit.json), run after the checked
[Sage runtime receipt](sage_runtime_info.json), agrees in all 63 block-A
bins and replays sampled sums from the original subgroup points. The
[Frobenius audit](rotation_audit.json) independently implements squaring
modulo `t^41+t³+1` and checks all 51,840 corresponding block outputs,
their seeds, column masks, and rank profiles. The first Frobenius auditor
stopped before inspecting a row because the local Python interpreter did
not support `zip(strict=True)`; the [failure receipt](rotation_failure_v1.json)
and [corrected freeze](rotation_protocol_v2.json) preserve that attempt.

## Exact W15 transfer size for explicit quadratic filters

The audited W15 source has **32,767** nonzero seeds and
**540,579,832** signed pair states. The per-seed pair count ranges from
15,928 to 17,132, giving **253,701,184 to 293,505,424** same-seed
four-atom *tuples* per bin before cross-block folded-column exclusions.
These are tuple counts, not distinct group outputs. The
[transfer arithmetic](transfer.json) uses the previously frozen
[per-seed census](../n131_w15_cross_block_seed_offset_20261010/signed_seed_counts.tsv).

For an optimistic 130-coordinate Boolean chart of N131 output `x`, a
degree-`d` monomial vector has `Σ_(j=0)^d binom(130,j)` coefficients.
A literal table of 16 dense equations for every nonzero seed would need
the following *coefficient bits alone*:

| Degree | Features per equation | Fixed 16-equation table for all seeds |
| ---: | ---: | ---: |
| 2 | 8,516 | 558,349,680 B |
| 3 | 366,276 | 24,003,793,520 B |
| 4 | 11,725,156 | 768,396,635,440 B |
| 5 | 297,968,932 | 19,527,096,251,824 B |

The 130-coordinate chart is an optimistic size model, not an asserted
N131 field reduction. The table model excludes equation discovery,
indexes, target work, and four-point membership. At degree three it
already exceeds the 4-GiB cap by coefficient storage alone. The N41
rank result gives no observed extra quadratic structure to justify a
compact direct degree-two output filter. This gate concerns **separate
per-seed output-`x` interpolation**; it leaves open equations that retain
the pair products and bind both block outputs jointly to the target.

## Next target-conditioned gate

Keep the pair seed and product parameters as symbolic variables and use
the normalized pair equation together with the public-target S3 links.
On the same unpinned N41 point, measure whether this joint representation
rejects whole **pairs of block-output families** before either block's
leaves are selected and without the 3,167,136-state four-point index.
The first promotion check is a relation with independent subgroup and
column replay, then a source-bound N131 work and RSS projection within
one worker, 600 seconds, and 4 GiB. This rank diagnostic is a proposal
stage result with `candidate_id: null`.
