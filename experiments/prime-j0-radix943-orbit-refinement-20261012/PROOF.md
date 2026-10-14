# Unit-orbit transport for the radix-943 scalar recoder

The native fixed-base path stores one nearest digit for each canonical
six-unit residue orbit. Its `unit_images` routine transports that digit to
the queried residue. This proof shows that every transported digit retains
the radix-943 norm bound and yields an exact integer quotient. Consequently,
any thirteen-step recoding assembled from these digits terminates whenever
its initial representative satisfies the established lattice bound.

## Mathematical proof

Write an Eisenstein integer as an integer pair `z=(a,b)` with
`Q(z)=a²+3ab+3b²`. The native unit map is

`ω(a,b)=(a+3b,−a−2b)`.

Direct expansion gives `ω³(z)=z` and `Q(ω(z))=Q(z)`. Negation also
preserves `Q`. The six images, in the exact native order, are

`z, −z, ωz, −ωz, ω²z, −ω²z`.

Each image map `U` is additive and integer-linear. Let `c` be a canonical
residue pair, and let its nearest radix step be `c=d+943q`. The prior
four-corner proof establishes `3Q(d)≤943²`. If the atlas code says that
the queried pair `z` has the same two residues modulo 943 as `U(c)`, then
there is an integer pair `t` with `z=U(c)+943t`. Therefore

`z=U(d)+943(U(q)+t)` and `3Q(U(d))=3Q(d)≤943²`.

This argument does not require the transported digit to win the
four-corner tie break for `z`; the norm and exact quotient are sufficient
for the thirteen-window termination inequality. Applying the earlier
termination theorem to a thirteen-digit chain gives terminal pair `(0,0)`
from `3Q(initial)≤n`, where `n` is the exact secp256k1 subgroup order in
`Termination.lean`.

## Proof map

| Result | Lean declaration | Hypotheses | Verification |
| --- | --- | --- | --- |
| Order-three unit and norm preservation | `omega_cubed`, `omega_norm`, `neg_norm`, `unit_image_norm` | Any integer pair; one of the six native unit codes | Checked |
| Additive and scalar transport | `unit_image_add`, `unit_image_scale` | Any integer pairs and integer scalar | Checked |
| Digit bound after transport | `unit_image_digit_bound` | Canonical pair, native unit code, exact nearest step from `DigitCover.lean` | Checked |
| Exact transported step | `orbit_digit_step` | Query differs from coded canonical pair by a multiple of 943 | Checked |
| Residue-code contract to exact step | `orbit_digit_from_residue` | Two componentwise Euclidean remainders agree modulo 943 | Checked |
| Thirteen-window termination | `orbit_thirteen_terminate` | Exactly 13 digits, each a coded nearest digit; exact `Recodes` chain; `3Q(initial)≤n` | Checked |

The theorem statements use integer pairs, Euclidean remainder, the exact
radix 943, and the six code positions used in
`unit_orbit_windows.rs` (`omega`, `unit_images`, and `digit_residue`). The
native atlas's code array is populated from those unit images; its runtime
debug assertion checks the two residue equalities used above. The proof
does not yet refine the array construction, the limb-based initial corner
selector, `Signed192` quotient arithmetic, or the curve evaluation into
Lean. Those are the remaining links for a full executable refinement.

`check.py --check` builds `Termination.lean`, `DigitCover.lean`, and
`OrbitAtlas.lean` with pinned Lean 4.34.1. Its frozen receipt contains the
source SHA-256 values and all nine `#print axioms` lines. The new theorems
use only Lean's `propext`, `Classical.choice`, and `Quot.sound` foundations.
The proof contains no `sorry`, `admit`, `sorryAx`, or custom research axiom.
`lean4checker --fresh` was unavailable on the development host.
