# Canonical radix-943 Pareto scalar protocol

Format 174 combines the existing exact thirteen-window radix-943 recoder
with canonical Solinas field arithmetic, XYZZ point formulas, and the
precomputed gauge-tree Pareto plans from format 173. This is a distinct
memory/operation point: the radix-943 point table has 1,926,717 canonical
affine entries, whereas format 173 has 1,004,904 entries.

The design screen used the already frozen 4,096 scalars in
`../prime-j0-sector-digit-20261010/fresh-inputs.json`. It predicted
53,248 active terms, 9,027 gauge rotations, 484,163 ordinary-path field
products, and 199,382 summed modeled product depth for format 174. The
format-173 source model on those inputs has 526,168 products. These are
source operation counts; whole-operation runtime includes recoding, table
access, inversion, and field-kernel latency.

Validate the implementation against format 173 on every design scalar,
and compare the first 128 points with independent binary multiplication.
Check complete scalar and point fields on the existing 129-case fixture.
Freeze the code and this protocol before generating a separate 512-scalar
holdout using `holdout.py` with seed `20261012174`. The holdout generator
computes expected secp256k1 points with a separate Python Jacobian path.
Compare the final output of formats 173 and 174 against those points and
compute their source operation counts using the same frozen plan table.
Preserve every failure and exact source/input/binary hashes.

The prior radix-943 covering-radius certificate proves termination for
every reduced scalar under its stated lattice assumptions. The inherited
`GaugeTree.lean` theorem covers reordered gauge-aware group sums; the
inherited `ParetoCost.lean` theorem covers tree formula costs and Pareto
pruning. The concrete Rust recoder, field formulas, and table construction
remain checked by the native and cross-language point replays. Controlled
CPU timing requires a paired complete-operation run on a host satisfying
the isolated benchmark preflight.
