# Four-atom bucket output polynomials are dense on the N41 W6 control

The exact mixed-rotation four-atom output polynomial for the seed used in
the independently replayed N41 public relation has **1,371 nonzero
coefficients at degree 1,370**. The same full coefficient density holds
at source dimensions 3, 4, and 5. An [independent integer-field
replay](audit_result.json) reconstructed every output root and every dense
coefficient digest. Thus the sparse **pair**-bucket norm does not remain
sparse when its two pair-output domains are combined as an explicit
four-atom root polynomial in this tested geometry.

The field is `GF(2)[t]/(t^41+t^3+1)`, the curve is `y²+xy=x³+1`, and
the source is `W_d=span(t,...,t^d)` for `d=3,4,5,6`. The mask-XOR seed is
`2`; the two pair rotations are 20 and 25. The degree-6 case includes
the pair outputs in the archived [N41 public relation
replay](../n41_seed_partition_indexless_20261010/replay_result.json).
The enumeration covers the complete algebraic product image for that seed
before rational-source support and folded-column filtering. It counts
distinct nonzero reciprocal coordinates of four-atom outputs.

For each seed product `p`, the producer solves
`(1+p²)c²+pc+s²=0` at both rotations. For every resulting pair of outputs
`c,d`, it solves the upper S3 quadratic
`(1+c²d²)z²+cdz+(c+d)²=0`. It then constructs the exact polynomial
`∏(Z+z)` over the distinct nonzero field outputs. The integer-field audit
uses separate bitwise multiplication, half-trace, inversion, root
enumeration, and sequential coefficient multiplication; its coefficient
hashes match the checked-Sage producer for every dimension.

| Source dimension | Product image | Pair outputs per rotation | Distinct four-atom outputs / degree | Nonzero coefficients |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 4 | 5 | 50 | 51 / 51 |
| 4 | 8 | 13 | 170 | 171 / 171 |
| 5 | 16 | 19 | 370 | 371 / 371 |
| 6 | 32 | 37 | 1,370 | **1,371 / 1,371** |

The [frozen checked-Sage run](result.json) completed under one worker,
150 seconds, and 4 GiB. Its [parent receipt](receipt.json) records 6.431
seconds including launcher startup and 276,578,304 B sampled peak RSS.
The independent audit's [receipt](audit_receipt.json) records 18.828
seconds and 17,596,416 B sampled peak RSS. The [terminal audit](terminal_audit.json)
binds source and input hashes, caps, results, and the independent replay.
These are construction and correctness measurements on an unisolated host;
the polynomial is a reusable algebraic constraint and this experiment
has `candidate_id: null`.

For the N131 W15 seed `13686` previously measured, the supported pair
domain has 8,288 outputs at each of rotations 26 and 39. Their Cartesian
product contains 68,690,944 coordinate pairs. If each upper quadratic
contributes two distinct nonzero outputs, an explicit dense block
polynomial would have about 137 million coefficients and require about
2.34 GB for 17-byte field encodings alone. This is a source-size
projection, not an N131 root census; it excludes polynomial-workspace
overhead and the other seed families.

The next target-conditioned design should keep each bucket implicit: use
the fast sparse pair norm or its Artin–Schreier inverse as a membership
constraint while propagating the public target through several free
blocks. The full public-point gate still requires an unpinned N41
relation, a source-bound N131 projection within 600 seconds and 4 GiB,
and independent point replay before N131 promotion.
