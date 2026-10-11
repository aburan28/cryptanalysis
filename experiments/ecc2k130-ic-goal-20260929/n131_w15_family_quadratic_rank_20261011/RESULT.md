# Full quadratic rank for a fixed N131 W15 four-atom family

An exact fixed-first-pair W15 family has **8,516 independent degree-two Boolean feature rows**, filling the complete function space of degree at most two on its trace-zero output hyperplane. The producer reached this rank after 4,259 admissible second pairs and 8,518 reciprocal S3 outputs. Checked Sage independently verified every pivotal field equation and recomputed rank 8,516 with a different monomial order and pivot rule. Thus no additional degree-at-most-two polynomial in the four-atom output bits vanishes on this entire fixed-first-pair family. An exact early filter must use higher-degree information, source masks, or a constraint coupling multiple blocks to the public target.

## Frozen family and feature space

The curve is `EC1N131Ckb1heb5f1998f20b`, `y²+xy=x³+1` over `GF(2)[t]/(t^131+t^13+t²+t+1)`. The audited W15 source has **B=197,292** subgroup-usable points before signed-Frobenius folding and **K=16,381** folded columns. The first pair fixes masks `[5576,8382]` at rotation 26, XOR seed `13686`, and reciprocal output `676093460871150716153371303092316913430`. The second pair uses the same seed at rotation 39. Its archived rotation-26 table has 8,288 exact output/mask records; 8,286 remain admissible with four distinct folded columns after the first pair is fixed. The [protocol](protocol.json) binds that table, positive output, source hashes, trace basis, 600-second wall cap, and 4-GiB RSS cap.

In this polynomial basis, `Tr(z)` is the XOR of coordinate bits 0 and 129. The reciprocal S3 equation implies `Tr(z)=Tr(c)+Tr(d)=0` for every four-atom output in the family. Eliminate bit 129 and let the remaining 130 Boolean coordinates be `x_0,…,x_129`. The complete degree-at-most-two feature basis contains the constant, 130 linear terms, and `C(130,2)=8,385` square-free pair products, for **8,516 features**. Boolean squares reduce to linear terms. Full column rank on valid outputs therefore excludes every further degree-at-most-two vanishing equation.

## Exact scan and replay

The [producer](run.py) places the archived positive second pair first, then streams the other admissible table rows. For each row it rotates the pair coordinate, solves both nonzero roots of `(1+c²d²)z²+cdz+(c+d)²=0`, checks trace zero, and inserts both degree-two feature vectors into binary Gaussian elimination. It stopped at full rank and saved every pivotal output, its masks, and S3 branch in the [result](result.json).

| Exact stage | Result |
| --- | ---: |
| Admissible second-pair records | 8,286 |
| Records / outputs processed to full rank | 4,259 / 8,518 |
| Independent degree-two rows | **8,516 / 8,516** |
| Positive archived block output | Present among the first row's roots |
| Exploratory arithmetic wall / peak process RSS | 150.053 s / 25,051,136 B |

The [independent checked-Sage replay](sage_replay.json) reconstructs all 8,288 rotated table coordinates, checks table membership, the exact S3 equation, and trace for **all 8,516 pivotal outputs**, and obtains rank 8,516 using pair monomials ordered by their larger coordinate and low-pivot elimination. The producer orders by the smaller coordinate and uses high-pivot elimination. The preceding [affine-rank Sage replay](../n131_w15_family_affine_rank_20261011/sage_replay.json) independently lifted the positive output and one other output to signed four-point curve sums. The [terminal audit](terminal_audit.json) checks source hashes, caps, positive control, pivotal rows, and independent replay. The wall time is a local arithmetic diagnostic, not an isolated CPU speedup measurement.

The rank certificate narrows the target-conditioned approach: per-block output syndromes of degree two cannot reject this whole valid family. It leaves higher-degree equations and nonlinear constraints coupling two four-atom blocks, the last pair, and the public target open. The next experiment should measure rejection of *joint* seed or product families before mask expansion on an unpinned N41 control, then promote only a source-bound construction that fits the one-worker, 600-second, 4-GiB N131 relation gate. This is a component result with `candidate_id: null`.

Reproduce with `python3 experiments/ecc2k130-ic-goal-20260929/n131_w15_family_quadratic_rank_20261011/run.py execute`, `/Volumes/SSD990/cryptanalysis/sage -python /Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n131_w15_family_quadratic_rank_20261011/verify_sage.py`, and [verify.py](verify.py).
