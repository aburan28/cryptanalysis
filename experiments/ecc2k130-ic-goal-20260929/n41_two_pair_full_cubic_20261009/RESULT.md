# Exact mixed-cubic nullspace certificate for two N41 pair domains

The complete 48,818-feature seed-plus-`x,y` mixed-cubic evaluation matrix has
rank **47,206** on 80,000 frozen, exact, four-column-distinct sums of two N41
pair domains. Its 1,612-dimensional nullspace is **exactly** the
124-dimensional coordinate-only quadratic nullspace together with one copy
multiplied by each of the 12 seed bits. The rank equality below is an exact
finite-matrix certificate: this feature family contributes no additional
seed-conditioned equation on the training rows.

The same coordinate row span contains 6,000 independently sampled prime
subgroup points and **8,192 residuals of the frozen public target**. Thus every
equation in this tested mixed-cubic nullspace evaluates to zero for every
12-bit seed assignment on those public residuals. The eight shortest
extracted equations, each with 24 monomials, also held on 50,000 fresh exact
two-pair sums and rejected zero of the 8,192 public residuals.

## Instance and frozen feature family

The curve is `EC1N41Ckb1h7d5e80d3c4d0` over
`GF(2)[t]/(t^41+t^3+1)`, with `y²+xy=x³+1` and prime subgroup order
`549756390943`. The public point is
`Q=(1458168294740,1672312028033)`. The four-window factor base has
`B=256` actual subgroup-usable points and `K=26` folded columns. The two
suffix pair domains use rotations 20 and 30 and have 1,956 exact states each.
Every accepted four-point suffix tuple uses four distinct signed/Frobenius
column IDs. The public residual control uses prefixes from rotations 0 and
10 with the same distinct-column rule.

The 93 Boolean variables are two six-bit seed-mask XORs, residual `x` bits
1–40, and residual `y` bits 0–40. The feature order is the constant; all
degree-one and degree-two squarefree monomials; and every degree-three
squarefree monomial containing at least one seed bit. The coordinate-only
subfamily is the constant and degree-at-most-two terms in the 81 `x,y` bits.
`x` bit 0 is omitted because the declared prime-subgroup points have
trace-zero `x` in this encoding. The [protocol](protocol.json) freezes the
inputs, source and binary hashes, row order, seed, and limits. This is
proposal `Q20261009231000`; `candidate_id` and `run_id` are null because a
complete IC pipeline is not specified by this rank experiment.

## Rank identity and target-conditioned result

Let `C₂` be the coordinate-only feature space and let `K` be its kernel on the
80,000 exact training rows. The measured ranks give

| Evaluation space | Features | Rank | Nullity |
| --- | ---: | ---: | ---: |
| Coordinate-only `C₂` | 3,322 | **3,198** | 124 |
| Full seed-plus-coordinate mixed-cubic space | 48,818 | **47,206** | 1,612 |

For each of the 12 seed variables `sᵢ`, multiplication maps every relation
in `K` into the full kernel: `(sᵢ f)(row)=sᵢ(row) f(row)=0`. The coefficient
supports of `K,s₀K,…,s₁₁K` are disjoint because their monomials contain
respectively zero or exactly one particular seed variable. They therefore
give `13 × 124 = 1,612` independent null vectors. This equals the full
nullity, so **there are no other null vectors on these rows**. The
[M4RI echelon result](rank.json) and the independently rebuilt full RREF
both report rank 47,206; the [RREF extraction](equations.json) reports 1,488
mixed candidates, exactly `12 × 124`, and directly re-evaluates its eight
selected equations on all training rows.

The eight selected equations are `sᵢ C(x,y)` for seed bits `i=0,…,7` and one
common 24-term coordinate polynomial `C`. The [fresh evaluation](holdout_validation.json)
found zero violations for each equation on 50,000 newly generated exact sums
whose pair-index combinations do not occur in training. On the frozen public
point, the [prefix probe](public_residual_probe.json) found `C(Q-P)=0` for
8,192 distinct-column prefixes `P`, giving zero rejection for every seed
assignment under those eight equations.

The stronger [public coordinate-span check](public_coordinate_span.json)
rebuilds the training coordinate span with an independent low-pivot GF(2)
implementation and appends the same 8,192 exact residuals. Its rank remains
3,198, with **zero novel directions**. Every `f∈K` therefore vanishes on
these residuals, and the rank identity shows that **every** mixed-cubic
training null equation vanishes there for every seed assignment. This is an
exact statement for the sampled prefix set and the frozen feature family;
the experiment leaves the rest of the prefix domain for a later proof or
exhaustive certificate.

| Exact control | Result |
| --- | ---: |
| Distinct training pair-pair sums | 80,000 |
| Fresh pair-index-disjoint sums | 50,000 |
| Sage subgroup source points checked | 128 |
| Sage exact group sums replayed | 272 |
| Random subgroup points for coordinate rank | 6,000; rank 3,198 |
| Novel coordinate rank after adding those subgroup points | **0** |
| Public-target prefix residuals | 8,192; novel coordinate rank **0** |

The [checked-Sage audit](sage_audit.json) rebuilds both pair domains, checks
all 128 source points and `Q` in the declared subgroup, and independently
replays 272 selected sums. Its [runtime receipt](sage_runtime_info.json) was
saved before the Sage job. The [independent combined-rank control](combined_coordinate_rank.json)
checks all 80,000 pair coordinates plus the 6,000 random subgroup points; its
rank stays 3,198. These checks establish the point encoding and row-span
claims used above.

## Resource record and next method gate

All local runs used one worker. The frozen rank and RREF caps were 300 seconds
and 4 GiB each. Exact row production took 14.971 seconds and peaked at
56,328,192 bytes. M4RI population and rank took 44.714 seconds and peaked at
529,907,712 bytes; the bounded wrapper completed in 45.121 seconds. Full
RREF extraction and direct training-row equation validation took 110.399
seconds and peaked at 497,025,024 bytes; its wrapper completed in 111.075
seconds. The low-pivot combined subgroup and public span controls took
57.335 and 44.711 seconds, respectively. These are unisolated algorithmic
diagnostics, with no CPU wall-time speedup ratio attached.

The next constructive gate is a **nonlinear, target-conditioned pair
realizability test**. It should carry the public residual constraint through
at least three still-free pair domains before fixing all their leaves, use
the exact seed-conditioned pair polynomial or quotient-ring eliminant, and
avoid materializing a full pair-vector index. The first acceptance test is an
unpinned ordinary eight-point row on this N41 public point with independent
group and folded-column replay under the standing 120-second/4-GiB gate.
Only then should a source-bound N131 W18 projection be charged. The finite
rank certificate here removes this low-degree seed-coordinate family from
that search and keeps the next experiment focused on genuinely nonlinear
target propagation.

Run `PYTHONDONTWRITEBYTECODE=1 python3 verify.py` in this directory to check
the frozen hashes, exact row disjointness, Sage and M4RI receipts, rank
identity, held-out equations, public residual span, and resource statuses.
