# Radix-919 terminal-unit scalar multiplication

This scheme replaces the zero-terminal radix-943 recoder with thirteen
radix-919 unit-orbit windows and one conditional terminal correction. It
reduces the canonical affine point table from 1,926,717 to 1,829,893 entries.
The terminal pair is provably zero or one of the six units, so its correction
needs one additional canonical point at weight `919^13` and the same six-unit
transport used by the window atlas.

The curve is secp256k1, with its standard generator and subgroup order
`n = FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141`.
The endomorphism eigenvalue is
`lambda = ac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0`
modulo `n`. An Eisenstein pair `(a,b)` denotes the scalar `a + lambda*b`.
The norm is `Q(a,b)=a^2+3ab+3b^2`. Use the existing exact four-corner
representative chooser, then at each window choose the nearest four-corner
digit on the canonical residue orbit, transport it by its unit code, and
divide both coordinates exactly by 919. At the end, append the terminal
pair when it is nonzero. The point sum is

`sum(i=0..12) [919^i * (d_i.a + lambda*d_i.b)]G
 + [919^13 * (terminal.a + lambda*terminal.b)]G`.

The Lean proof checks the representative norm and congruence, the nearest
digit bound, unit-orbit transport, exact thirteen-step reconstruction,
and the seven possible terminal pairs for every integer scalar. Its
remaining implementation boundary is the native word arithmetic, atlas
storage, correction-point transport, and XYZZ evaluation.

## Frozen design decision

The design input is the existing 4,096-scalar
`../prime-j0-sector-digit-20261010/fresh-inputs.json`. Choose radix 919
before generating another holdout. Compare its exact source operation count
to format 174 on the same scalar and Pareto plan table. A selected nonzero
window or correction counts as one affine term. The ordinary-path product
model is `10*n-14+gauge_rotations` for `n>=2`; the plan table supplies the
rotation count and depth. Keep the correction's unit code in the plan input.
Record every terminal state and verify exact scalar reconstruction. Audit
all `919^2` residues and the exact orbit count. Table storage is modeled as
64 bytes per canonical affine point, four bytes per residue-map slot, and
four bytes per canonical digit; it is not a native heap measurement.

After committing the design protocol, code, proof, and receipt, generate a
new independent 512-scalar holdout with seed `20261012919`. Replay the scalar
and point outputs against an independently implemented secp256k1 group law.
Native complete-operation timing requires a paired run on a host with the
requested CPU isolation receipt. Preserve build and correctness failures.
