# Full quadratic coordinate rank for the exact N131 d13 pair domain

**The d13 same-rotation pair-output support has no universal Boolean equation
of degree at most two in its 131 phi-coordinate bits.** An exact subset of
8,647 signed pair outputs already gives rank 8,647 in the complete quadratic
feature space. M4RI and a separate packed-bit incremental elimination agree;
an independent checked-Sage audit replays 96 sampled curve additions and
recomputes the feature-map digest. This closes coordinate-only quadratic
screening as a compact way to constrain a free pair in the selected d13
six-pair search. The next propagator must use the seed sum, interactions among
pair outputs, or higher-degree information together with the public point.

## Exact input and rank statement

The [frozen protocol](protocol.json) binds the canonical d13 candidate
manifest and its curve ID `EC1N131Ckb1heb5f1998f20b`:
`GF(2^131)` with official polynomial modulus
`t^131+t^13+t^2+t+1`, binary curve `y^2+xy=x^3+1`, and odd-order subgroup
`r=680564733841876926932320129493409985129`. The factor-base source is
the audited 13-dimensional phi subspace with 4,134 usable leaf codes and
same-rotation pair blocks at Frobenius rotations `0,22,44,66,88,110`.
For a nonexceptional point, `phi(P)=1/(x(P)+1)`; the tested coordinate bits
are its 131 ONB mask bits. The proposal has `candidate_id: null` and
`run_id: null` because this is a pair-domain stage.

The sample law selects 2,200 distinct right codes without replacement for
each of the first four valid left codes, using frozen seed
`20261009173000`, and takes both signed point sums. This gives 8,800
unordered descriptors and **17,600 distinct phi outputs**. Every record in
the [saved binary sample](sample.bin) contains both exact leaf codes, the
sign branch, and the phi mask. The sample and all source hashes are saved in
the [sample receipt](sample_result.json); the checked Sage runtime was saved
before generation. The 17,600 records are a subset of the complete pair
domain, so their full feature rank certifies full feature rank for the
complete domain.

Let `z_0,...,z_130` be the phi mask bits. The feature map consists of
`1`, all 131 individual bits, and all `C(131,2)=8,515` distinct products
`z_i z_j` for `i<j`, totaling **8,647** columns. Boolean squares equal the
original bits, so this is the complete degree-at-most-two polynomial space.
If a nonzero polynomial in this space vanished on every exact pair output,
its coefficient vector would lie in the right kernel of the saved sample's
feature matrix. Both exact rank computations find a zero-dimensional right
kernel. Because `phi(P^{(2^k)})=phi(P)^{2^k}` and Frobenius is an invertible
binary linear map, the same result applies to each of the six rotated pair
domains.

| Frozen stage | Exact result | Exploratory wall | Process peak RSS |
| --- | ---: | ---: | ---: |
| Checked-Sage point setup and subgroup checks | 4,134 usable codes | 53.082 s | 264,781,824 B total sample peak |
| Exact signed-output generation | 17,600 distinct phi masks | 11.639 s | Same sample process |
| [M4RI rank](rank_result.json) | 8,647 / 8,647; 17,600 rows | 0.929 s rank kernel; 1.449 s guarded command | 22,183,936 B internal peak |
| [Independent incremental rank](audit_rank_result.json) | 8,647 / 8,647 by row 8,647 | 2.162 s internal; 2.471 s guarded command | 10,977,280 B internal peak |
| [Independent checked-Sage audit](audit.json) | 96 signed additions; descriptor order, sample hash, feature digest, both ranks pass | Separate audit | Separate audit |

The [rank protocol](rank_protocol.json) freezes both compiled binaries,
sources, sample digest, 300-second per-method wall caps, and 4-GiB RSS cap.
Both [primary control](rank_control.json) and [independent control](audit_rank_control.json)
ended `EXIT_SUCCESS`. The generation protocol also capped its one worker at
300 seconds and 4 GiB. All observed CPU wall times here are exploratory
because this host has no isolation receipt; the algebraic rank is the result.
The earlier pair-output pilot printed an older curve label in its own protocol;
this experiment binds to the canonical curve ID in the frozen candidate
manifest and independently checks the exact field, curve, and subgroup
arithmetic through Sage.

## Algorithm decision

A target-conditioned solver cannot get a free pair-output rejection from a
single universal quadratic test in these phi bits: every such nonzero test
rejects at least one genuine output. Conditioning on a seed sum remains
possible, because it restricts the output support. The exact
[joint linear inverse](../n131_d13_joint_linear_pair_inverse_20261009/RESULT.md)
already uses this seed structure efficiently **after** an output is proposed.
The next experiment should carry at least four free pair blocks through a
public-target S3 tree while retaining each block's seed-conditioned product
constraint; it should measure early family rejection on the frozen N41
control and provide a whole-search N131 work bound before a public-point
query. This rank result is proposal `Q20261009173000`, not a complete IC
candidate comparison.
