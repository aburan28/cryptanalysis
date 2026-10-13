# Sixteen-term hex-terminal gauge tree

The fixed-base secp256k1 evaluator in
`../prime-j0-hex-terminal-20261012/hex_terminal.rs` produces at most sixteen
nonidentity table points. This experiment changes their addition schedule.
The recoder, selected point set, table, and scalar input remain fixed. A
binary tree groups the leaves by unit gauge, rotates each subtree into its
join gauge, and returns the result in gauge zero. Its group-sum identity is
the checked abstract `PrimeJ0GaugeTree.reordered_tree_correct` theorem in
`../prime-j0-gauge-tree-20261012/GaugeTree.lean`, conditional on the concrete
curve automorphism and on the plan containing each selected point once.

The frozen plan table has one record for every gauge-count triple
`(a,b,c)` with `a+b+c≤16`. Records are ordered first by total size and then
by `a,b`; the index is

`C(a+b+c+2,3) + a*(a+b+c+1) - a*(a-1)/2 + b`.

Each 48-byte record contains fifteen three-byte `(i,j,gauge)` join slots,
followed by used-step count, unit-rotation count, and product depth. The
active-node list starts with `a` gauge-zero leaves, then `b` gauge-one and
`c` gauge-two leaves. At a join, remove `j` then `i`, append the parent, and
apply a final rotation if the root gauge is not zero. `make_plans.py`
generates and independently replays every record. The table is 46,512
bytes; a runtime implementation must count these retained bytes.

The planner minimizes `(product dependency depth, products plus rotations,
gauge, i, j)` at each join. Its ordinary-path product charges match the
existing native formulas: affine/affine 6, affine/projective 10, and
projective/projective 14. A gauge change costs one field product in this
model. The serial reference charges 10 products per mixed addition after
the first selected point and one per gauge rotation. The first point and
the final affine recovery are common boundaries and excluded from these
two model totals. The depth model counts the longest product-dependency
chain; it is not a wall-time prediction. Exceptional point branches,
recoding, table access, plan lookup, and memory effects require native
measurement.

`screen.py` reconstructs every selected term on the frozen 4,096-scalar
design fixture. Its serial addition and rotation counts are calibrated to
the existing 512-scalar native replay. `design.json` records both data laws
and source digests. The design artifacts must be committed before a fresh
holdout is generated. The holdout must replay the selected point sum through
an independent point implementation and a native tree evaluator before a
correctness or performance result is promoted. Controlled wall time needs
the repository's isolated benchmark receipt.
