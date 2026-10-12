# Linked mixed-radix recoder: termination and action bound

The linked 2/τ/ρ/conjugate-ρ recoder terminates for every scalar accepted by
the secp256k1 path. With the frozen lattice and norm-4096 tail, its digit
stream has at most **222 actions**. This bounds the 256-action assertion in
`src/mixed_radix.rs` independently of the fixture panels.

Write a state as `z = a + bτ` in `Z[τ]`, where `τ = 1 - ω`,
`τ² = 3τ - 3`, and

`N(z) = a² + 3ab + 3b²`.

The recoder's zero-digit radix steps divide by `2`, `τ`, `ρ = 1+τ`,
or its conjugate `4-τ`, whose norms are 4, 3, 7, and 7. They therefore
reduce a nonzero state's norm by factors 4, 3, 7, and 7. A nonzero digit
is used only with a `τ` step. Every linked width-four digit is a unit
rotation of one of the nine frozen seeds, whose largest norm is 112. The
triangle inequality for the complex absolute value gives, for `N(z)>4096`,

`N((z-d)/τ) ≤ (√N(z) + √112)² / 3
               < q N(z),
 q = (1 + √7/16)²/3 = (263 + 32√7)/768 < 453/1000`.

Thus every step above the tail boundary strictly contracts the norm,
regardless of which eligible radix the selector takes. The divisibility
tests in the implementation are `3 | a` for `τ`, `2 | a,b` for 2,
`7 | a-b` for `ρ`, and `7 | a-3b` for its conjugate. Subtracting the
selected width-four digit before the `τ` division makes that division
exact.

The initial representative has a uniform bound. Let `u` and `v` be the
two frozen kernel-lattice vectors in `src/main.rs`. The central rounded
candidate has coefficient vector `δu u + δv v` with
`|δu|,|δv| ≤ 1/2`. The positive definite quadratic norm is convex,
so its maximum over this square occurs at a corner. The implemented
25-candidate selector chooses a representative with no greater norm:

`N(z₀) ≤ max{N(u+v), N(u-v)}/4 < 2²⁵⁷`.

The last inequality follows by exact integer evaluation of the frozen
lattice constants. Direct integer comparison also gives
`2²⁵⁷(453/1000)²¹⁵ < 4096`. Consequently no more than 215
large-state actions can precede the norm-4096 tail.

For `N(z)≤4096`, `|a|≤128` and `|b|≤73`, so the Rust decoder's
coordinate guard admits every state in the ball. The linked tail generator
enumerates all 29,688 nonzero `(a,b,pending_τ)` states, verifies that
each has a path to zero, reconstructs each path, and asserts a maximum of
seven actions. The native test independently reconstructs every decoded
state and pending-τ value. Together these give `215 + 7 = 222` actions.

This proof concerns termination and a stream-length bound. The charged
field-operation results and the frozen scalar outputs remain in
`LINKED_MIXED_SCREEN.md`; CPU timing requires a host-isolation receipt.
