# A fixed N131 W15 four-atom family fills the trace-zero affine space

An exact family with one **fixed first pair**, one **fixed XOR seed**, and 512 admissible second pairs produces 1,024 four-atom reciprocal outputs whose binary linear rank is **130** and affine augmented rank is **131**. All outputs have trace zero, so these ranks attain the maximum allowed by the known trace equation. Consequently, every affine linear equation that holds for the entire fixed-first-pair family is implied by `Tr(z)=0`: an additional linear output-bit syndrome cannot reject this whole family while preserving all of its valid decompositions. This is a focused obstruction for early linear pruning, leaving nonlinear and target-coupled constraints open.

## Frozen family and exact outputs

The field is `GF(2)[t]/(t^131+t^13+t^2+t+1)` and the curve is `y²+xy=x³+1`, curve ID `EC1N131Ckb1heb5f1998f20b`. The source is the audited W15 mask set, with **B=197,292** subgroup-usable points before signed-Frobenius folding and **K=16,381** folded columns. The first pair fixes masks `[5576,8382]` at rotation 26, with XOR seed `13686` and reciprocal output `676093460871150716153371303092316913430`. The second pair uses the same seed at rotation 39. Its complete rotation-26 table contains 8,288 distinct outputs, each with a source-mask witness. The [protocol](protocol.json) fixes the first pair, positive block output, table/source hashes, and a deterministic 512-row selection: the known positive row followed by the earliest table rows whose two folded columns differ from those of the first pair.

For each selected second-pair coordinate `d`, the [producer](run.py) applies the 13-step Frobenius rotation and solves the exact reciprocal S3 quadratic

`(1+c²d²)z² + cdz + (c+d)² = 0`

for both nonzero roots. Every row has four distinct folded source columns. The archived constructed block output `1072442453979696659264084726754206488845` occurs at the expected masks `[3,13685]` on branch 1. The deterministic selection yielded **512** second-pair rows and **1,024** output roots in 8.299 seconds of exploratory local arithmetic.

| Exact property of this fixed-first-pair family | Result |
| --- | ---: |
| Selected admissible second pairs / S3 outputs | 512 / 1,024 |
| Trace of every output | 0 |
| Rank of 131-bit output vectors | **130** |
| Rank of vectors with an appended constant 1 | **131** |
| Independent Sage S3 witness rows checked | 261 |
| Independent signed group sums checked | 2 |

The [result](result.json) stores every rank-increasing row: 130 linear witnesses and 131 affine witnesses. [Checked Sage replay](sage_replay.json) reconstructs the field with the declared modulus, verifies the S3 equation, rotated table membership, and trace for all 261 witness rows, recomputes both GF(2) matrix ranks, and independently lifts the positive output and one other output to signed four-point curve sums. The [terminal audit](terminal_audit.json) binds the frozen table, source, runtime, rank witnesses, and Sage receipt. The independently validated trace equation gives an upper bound of 130 for the output-vector rank; attaining it is an exact certificate that no further homogeneous linear constraint holds on the full family. Affine rank 131 likewise excludes further affine constraints.

The next target-conditioned method should couple two or more four-atom families to the public point with a **nonlinear** eliminant or constraint that rejects entire incompatible source families before their masks are expanded. This rank result says nothing about such joint constraints, ordinary N131 relation yield, useful relation rank, or the single-target online comparison. It is a proposal-stage diagnostic with `candidate_id: null`. Reproduce the source-frozen arithmetic with `python3 experiments/ecc2k130-ic-goal-20260929/n131_w15_family_affine_rank_20261011/run.py execute`, the independent replay with `./sage -python experiments/ecc2k130-ic-goal-20260929/n131_w15_family_affine_rank_20261011/verify_sage.py`, and the archive check with [verify.py](verify.py).
