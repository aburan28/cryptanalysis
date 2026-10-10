# Eight cross-block seed offsets: exact W15 support and an N41 public relation

The W15 six-pair method retains a group-wide mean of **8.339230** raw
signed twelve-point tuples per subgroup target when the seed sums of its
two four-atom blocks differ by one of eight predeclared offsets
`{0,…,7}`. This is an exact tuple-count upper bound before cross-block
folded-column exclusions. On the frozen N41 public point, the matching
W6 restriction produced a twelve-point relation with seed offset **3**;
independent checked Sage verified all twelve distinct columns, their
sum to the public point, and the normalized pair-output identity below.

The restriction sharpens the search boundary. For a uniform subgroup
target, a solver that fixes one free pair independently of the target
needs at least **32,411,856 distinct prefixes** before its union-bound
success ceiling reaches one half. A 600-second query would allow at most
**18.512 microseconds** of *all* target-dependent work per prefix at that
threshold. The earlier unrestricted W15 bound is 7,914 prefixes. The
offset restriction is therefore a candidate for a **fully joint**
target-conditioned solver, rather than an outer-prefix sweep.

## Exact count and algebraic constraint

The challenge field is `GF(2)[t]/(t^131+t^13+t²+t+1)` on
`y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`, subgroup order
`680564733841876926932320129493409985129`. The six W15 pairs use
rotations `0,13,26,39,52,65`, with **B=197,292** subgroup-usable
factor-base points and **K=16,381** signed-Frobenius columns from the
previously audited source. Each block of two constrained pairs has an
equal mask-XOR seed. Write their seeds as `s_A,s_B` and require
`s_A XOR s_B∈{0,…,7}`. The other two pairs remain unrestricted.

Let `c_s` be the number of signed, unordered, distinct-column source
pair states with seed `s`, with `c_0=0`; the exact W15 census gives
`N=Σc_s=540,579,832`. For offset `δ`, the two-block tuple count before
cross-block exclusions is

`E_δ = Σ_s c_s² c_(s XOR δ)²`.

The eight offsets contribute `E=Σ_(δ=0)^7 E_δ`. Multiplying by `N²` for
the two free pairs and dividing by the subgroup order gives the mean
above. [The frozen Walsh calculation](result.json) binds the exact
summary, the [32,767 per-seed counts](signed_seed_counts.tsv), the
[32,768 offset counts](offset_support.tsv), the support fraction, and
the one-prefix union bound. It reproduces the
previous independent W15 totals `N` and `Σc_s²`. A separately frozen
[direct native enumeration](direct_audit.json) visited every eligible
unordered W15 source-mask pair and matched **all 32,767 seed counts**
and the eight selected offset counts.

The offset also yields a low-degree joint equation before source masks
are expanded. For a raw source point let `w=1/x(P)`. In one pair, put
`s=w_a+w_b`, `p=w_aw_b`, and `c=1/x(P_a+P_b)` after undoing the pair's
known Frobenius rotation. The exact pair equation is

`(1+p²)c²+pc=s²`.

For a pair in block A and a pair in block B with seed offset `δ`, adding
their equations cancels the unknown common seed and leaves the known
constant `w_δ²` on the right. This is a necessary target-coupled
constraint when combined with the upper point-sum links. It is already
implied by exact leaf equations and the seed-offset rule; an implementation
must exploit it to prune output families to gain search time.

| Frozen W15 support quantity | Exact result |
| --- | ---: |
| Signed pair states `N` | 540,579,832 |
| Eight-offset share of unrestricted two-block tuples | 0.00024414939857694135 |
| Group-wide tuple mean before cross-block column filtering | 8.339230053385588 |
| One-free-pair prefixes needed at the 50% union-bound ceiling | 32,411,856 |
| Necessary average budget per prefix within 600 s | 18.512 µs |

The bound applies to target-independent prefixes under a uniform subgroup
target law. It does not estimate relation yield on the fixed published
point or constrain a generator that uses the target to choose outputs.

## Frozen N41 public-point control

The N41 control uses the same source-mask restriction on the previously
frozen W6 six-pair point
`Q=(1458168294740,1672312028033)` over
`GF(2)[t]/(t^41+t³+1)`, with subgroup order `549756390943`,
**B=384**, and **K=26**. Its six pair rotations are `0,5,10,15,20,25`.
The [query protocol](n41_query_protocol.json) fixes `Q`, the eight offsets,
source and binary hashes, one worker, 120 seconds online, 4 GiB RSS,
and RNG seed before the public query.

| N41 public-point stage | Recorded result |
| --- | ---: |
| Status after independent Sage replay | Verified twelve-point relation |
| Cross-block seed offset / distinct folded columns | 3 / 12 |
| Accepted target probes / group hits / column rejects | 827,015 / 8 / 7 |
| Total attempts / offset-filtered attempts | 15,003,145 / 13,098,809 |
| Target-independent index setup | 2.708535 s |
| Target-dependent native query | 2.338561 s |
| Parent wall / peak process RSS | 5.618352 s / 192,823,296 B |

The [native receipt](n41_query_receipt.json) preserves the exact hit,
attempts, filtered attempts, wall boundaries, resource cap, stdout, and
stderr. The [independent Sage replay](n41_sage_replay.json) rebuilt the
source atoms, matched their cofactor-four projections to the native
leaves, checked twelve distinct signed-Frobenius orbits, summed the
twelve subgroup points to `Q`, and verified the normalized pair equation
for all six pairs and the cross-block cancellation for four pair
combinations. The checked [Sage runtime receipt](sage_runtime_info.json)
was saved before replay.
The [terminal audit](terminal_audit.json) binds the source and result
hashes, all seed-count agreements, resource limits, verified public
point, and offset identity.

The N41 join still materializes a 3,167,136-state reusable four-point
index. Its target-dependent wall is an exploratory diagnostic on an
unisolated host and gives no challenge-width work bound. The offset
sampler rejected many incompatible block pairs; a seed-bucket sampler
could remove that local overhead, but an N131 solver must also replace
the index and jointly derive target-compatible partial outputs.

## Next algorithm gate

Use the normalized cross-block identity inside a joint solver for the
five-pair residual after a public target is supplied. Measure whether it
rejects *families* of both four-atom outputs before materializing their
members. The exact 32.4-million-prefix bound rules out an expensive
per-prefix residual oracle for this eight-offset policy. Promote to the
frozen N131 public-point query only after an unpinned N41 joint-output
method finds a relation without the explicit four-point index and a
source-bound N131 projection covers complete work and memory within
one worker, 600 seconds, and 4 GiB. This is a proposal-stage result
with `candidate_id: null`.
