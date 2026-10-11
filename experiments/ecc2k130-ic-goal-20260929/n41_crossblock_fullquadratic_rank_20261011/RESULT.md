# Full degree-two rank for valid N41 cross-block outputs

The valid eight-column N41 source spans the complete **3,241-dimensional degree-two Boolean feature space** of its two block-output `x` coordinates. An exact rank certificate uses 3,241 pivotal pairs; independent replay reproduced their source rows, the seeded sampling sequence, all rejection counts, and full rank in a different monomial order and elimination direction. Consequently every nonzero polynomial of total degree at most two in these 80 output bits is nonzero on at least one valid source pair. Target-conditioned pruning must use the public-point equation, retained source-product coordinates, or higher-degree information.

The field is `GF(2)[t]/(t^41+t^3+1)` and the curve is `y²+xy=x³+1`, with subgroup order `549756390943`. The exact four-atom source uses W6 windows at rotations `10,15` and `20,25`; the six-window factor base has **B=384** subgroup-usable points and **K=26** folded columns. [The source census and Sage audit](../n41_w6_offset_quad_rank_20261010/RESULT.md) established the block sums. For each pair of block outputs, the second six-bit seed differs from the first by one of eight offsets, and all eight source columns are distinct. Both output `x` coordinates have bit zero equal to zero, leaving 40 bits per block.

The [frozen protocol](protocol.json) binds the two source files and producer, the deterministic sampling law, 3,241 monomials, one worker, and a 200,000-attempt cap. The features are a constant, 80 linear bits, and all `C(80,2)=3,160` square-free quadratic products. [The producer](run.py) used high-pivot GF(2) elimination and saved each pivotal pair's source-row indexes, seeds, outputs, and column masks in [the result](result.json). [The independent replay](verify.py) reconstructed the complete sample stream and used reverse variable order with low-pivot elimination; [its receipt](audit.json) passed.

| Exact stage | Result |
| --- | ---: |
| Feature dimension / independently replayed rank | **3,241 / 3,241** |
| Attempted / eligible cross-block pairs | 7,831 / 3,243 |
| Rejected for column overlap / zero second seed | 4,476 / 112 |
| Independent pivotal witnesses retained | 3,241 |
| Exploratory producer elapsed time, one worker | 12.064 s |

This certificate extends the [bilinear cross-block certificate](../n41_crossblock_bilinear_rank_20261011/RESULT.md) from 1,681 features to every within-block and cross-block quadratic term. It concerns the union of valid source pairs across seeds and offsets; a fixed seed or a public target can impose further equations. Local CPU elapsed time is a stage diagnostic on an unisolated host.

The next constructive experiment is a target-conditioned compressed join over retained pair products and the exact S3 public-point link. It should leave free pairs and seeds unfixed on the N41 public point, recover a relation with independent source-column and group replay, then measure N131 source-bound work and memory under one worker, 600 seconds, and 4 GiB. The complete IC pipeline retains `candidate_id: null` while that gate is open.

Reproduce the independent replay with `python3.12 /Volumes/SSD990/cryptanalysis/experiments/ecc2k130-ic-goal-20260929/n41_crossblock_fullquadratic_rank_20261011/verify.py`.
