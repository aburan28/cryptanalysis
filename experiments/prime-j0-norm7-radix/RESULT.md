# Direct norm-seven radix: correctness pass, feasibility rejection

The protocol and Sage source were frozen in `1f271b00` before execution
through the checked repository Sage launcher. `runtime-info.json`
reports `status: verified`. The saved fixture/source hashes in
`result.json` reproduce the checked-in files exactly.

Set `ρ=2−ω=1+τ`, an endomorphism of norm seven. The width-two table
covers all **42 nonzero residue classes modulo `ρ²`**, and its recoder
reconstructed all **64** previously frozen secp256k1 short scalar
representatives with strict norm descent. It used 5,803 positions and
2,715 nonzero digits (90.67 positions and 42.42 digits per scalar).
The derived direct projective map matched Sage's independent group
expression `2P−ω(P)` on every base at three projective scales: **192
point checks**. This validates the algebraic map on the tested points,
not a complete norm-seven scalar evaluator.

The direct map in `PROTOCOL.md` has a literal generic source count of
`13M+4S` per radix step. Even treating multiplication by the small
curve coefficient `b=7` as free additions leaves `12M+4S`, or **16
`M+S` units per step**. The 5,739 steps cost **91,824 units before any
digit addition or point-table preparation**. The frozen native
cached-projective width-four τ path costs **88,656 `M+S` units including
its seed preparation** on the same 64 cases, excluding the common final
inversion. The norm-seven step-only bound loses on all 64 cases.

Under the current 11-unit mixed-add formula, even an optimistic
norm-seven arm with every remaining addition mixed and zero preparation
would pay another `2,651 × 11 = 29,161` units, totaling **120,985**
(36.47% above the τ reference). To tie under those assumptions, the
radix map would need to cost at most **10.37 `M+S` units per step**;
the checked expression costs at least 16 in this model. This makes the
direct map and width-two recoder an unattractive implementation path.
It does **not** rule out a different, substantially cheaper norm-seven
map or a fused digit/endomorphism formula.

Norm-seven CM endomorphisms and Eisenstein digit methods have prior art:
the [Magma CM endomorphism documentation](https://docs.magma-maths.org/ArithmeticGeometry/EllipticCurves/function_field.html)
shows a degree-seven example, and [Heuberger and Mazzoli](https://eprint.iacr.org/2013/705)
study symmetric endomorphism digit sets. The present calculation makes
no academic novelty or CPU speedup claim. All costs are exact counts
for the stated source expressions, with `S=M` and no host timing.
