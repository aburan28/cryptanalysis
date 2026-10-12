# Q1495 rational-lift proof map

The checked structural result rewrites a nonzero-x point on
`y² + xy = x³ + 1` as a solution of `z² + z = x + x⁻²`. The Lean theorem is
`Q1495.curve_lift_iff_artin_schreier` in `RationalLift.lean`. It quantifies
over any field and all nonzero x. It covers both directions with `y = xz`
and `z = y/x`; it has no characteristic or finite-field assumption.

The checked trace algebra is `Q1495.trace_rhs_eq_xor` and
`Q1495.trace_rhs_zero_iff_inverse_parity`. They quantify over an abstract
Boolean-valued trace with explicit additivity and square-invariance
hypotheses. The second theorem also takes the normal-basis weight parity
equation `tr x = weightParity` as an explicit hypothesis. These lemmas prove
the exact reduction of the trace-zero test to inverse trace versus parity.

The finite-field Artin-Schreier bridge remains open in Lean: for each finite
field of characteristic two, prove `∃ z, z² + z = t` iff its absolute trace
is zero. The normal-basis bridge `absoluteTrace(x) = coordinateWeight(x) mod 2`
also remains open. The exhaustive N53 and N83 archive checks are separate
computational evidence for the declared bases and do not close these proof
obligations. Thus the complete Q1495 membership criterion has a readable
mathematical proof and checked structural lemmas, with formalization status
`partial`.

For the mathematical proof, substitute `y=xz` into the curve equation and
divide by `x²`, obtaining `z²+z=x+x⁻²`. Over a finite field of characteristic
two, the additive map `z↦z²+z` has kernel `{0,1}` and hence image of
codimension one over F₂. Absolute trace vanishes on its image because it is
invariant under squaring. Absolute trace is nonzero as a linear map on a
finite separable extension, so its kernel has the same codimension and equals
the image. In a normal basis, all basis elements have trace one; linearity
therefore gives the coordinate-weight parity. Square invariance then yields
`Tr(x+x⁻²)=Tr(x)+Tr(x⁻¹)`, proving the predicate. The archived N53/N83 base
enumerations separately establish that every rational x in the exact weight
domains projects to a distinct usable nonidentity orbit.

Toolchain: `leanprover/lean4:v4.35.0-rc4`. Mathlib revision:
`021c46bdd042f67b538b9f9871d556a93713a9a9`, as pinned in the checked
mathlib project's `lake-manifest.json`. The check command is:

```sh
cd /Volumes/SSD990/crypto/ecdlp-isogenous-curves-a480cf/research/conductor_gap_cm_pairs_20261010/lean_mathlib
lake env lean /Volumes/SSD990/llm/tmp/q1456-work/experiments/compact-s3-m4-20261003/q20261012_exact_rationality_filter/lean/RationalLift.lean
```

`lean_check.txt` retains the exact `#print axioms` output. The checked
declarations use only Lean's standard `propext`, `Classical.choice`, and
`Quot.sound` foundations; the source contains no `sorry`, `admit`, custom
research axiom, or native evaluation. `lean4checker --fresh` was unavailable
on this host. A standalone CI project is deferred until the finite-field
and normal-basis bridges are formalized.
