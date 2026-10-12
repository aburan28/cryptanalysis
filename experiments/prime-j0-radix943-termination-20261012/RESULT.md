# Thirteen-step radix-943 termination implication

The Lean theorem `PrimeJ0Radix943Termination.thirteen_steps_terminate`
proves that a secp256k1 Eisenstein representative satisfying the lattice
cover bound, recoded through thirteen exact radix-943 steps with digits
satisfying the hexagonal cover bound, has **zero terminal pair**. This
closes the geometric implication that the earlier reconstruction theorem
took as a hypothesis. The proof checks with pinned Lean 4.34.1 and uses no
`sorry`, custom research axiom, or native evaluation bypass.

For `Q(a,b)=a²+3ab+3b²`, the exact hypotheses are
`3Q(start) ≤ n`, `3Q(digitᵢ) ≤ 943²` for each of thirteen digits, and
`stateᵢ = digitᵢ + 943 stateᵢ₊₁` in both integer coordinates. Here `n` is
the secp256k1 subgroup order recorded in the Lean source. The theorem does
not assume a zero terminal state. It uses the checked inequality

`(2¹²⁸ + Σⱼ₌₁¹³ 943ʲ)² < 3·943²⁶`

and the positive definiteness of `Q` to derive that state after thirteen
steps is `(0,0)`. The exact left and right integers and their Lean checks
are in `PROOF.md` and `lean-build.txt`.

The existing radix-943 screen checked the digit norm bound over all
`943² = 889,249` residue pairs; its JSON certificate and source are
hash-bound in `receipt.json`. The prior mathematical lattice-cover argument
establishes the initial representative bound. Their concrete four-corner
chooser algorithms, and the link from Rust quotient words to the Lean
`Recodes` relation, remain formalization obligations. `PROOF.md` maps
what is checked and what remains.

This is a proof result for the format merged in PR #787. It changes no
runtime code or operation-count result. Complete-operation performance
still requires a paired host-isolated run.
