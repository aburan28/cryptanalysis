# Reciprocal-limb certificate for the radix-943 scalar representative

The native fixed-base path can select its initial Eisenstein lattice
representative from two reciprocal products and a strict four-corner
interval comparison. This Lean proof establishes that, for every reduced
secp256k1 scalar, a returned certified corner is the same exact
minimum-norm corner used by the complete scalar-recoding proof. The fallback
to the exact chooser has the same representative. The selected pair obeys
`3Q(z)≤n` and `a+λb≡k (mod n)`.

## Exact reciprocal coordinates

Let `n` be the secp256k1 subgroup order, `S=2^512`, and `c` be either
`V₂` or `−W₂` from the committed lattice basis. The two native reciprocal
constants satisfy `R_c n≤Sc<(R_c+1)n`; Lean checks both exact 512-bit
integer inequalities by kernel reduction. It also checks explicit modular
inverse certificates `c·inv=1+n·multiple`. These certificates show
`kc mod n≥1` for every `0<k<n` without adding a primality assumption.

For `k=0`, both quotients are zero. For `0<k<n`, multiply the reciprocal
inequalities by `k`. Since `n²<S` and `kc mod n≥1`, integer quotient and
remainder identities force

`⌊kR_c/S⌋=⌊kc/n⌋`.

Lean proves this separately for the exact two constants in
`exact_two_reciprocal_floors`. The proof uses the actual subgroup order and
integer constants from `eisenstein_fixed.rs`, not a finite sample of
scalars.

## High-limb enclosure and corner selection

Put `B=2^64` and `H=2^448`, so `S=BH`. The native high fractional limb is
`h=⌊((kR_c) mod S)/H⌋`. Let `x=(kc) mod n`. From the reciprocal product
bounds, the exact quotient equality, and `0≤k<H`, Lean derives

`hn≤Bx≤(h+2)n`.

This gives the four score enclosures used by the Rust classifier. In native
corner order `(0,0),(1,0),(0,1),(1,1)`, their lower and upper bounds are

| Corner | Lower | Upper |
| --- | --- | --- |
| 0 | `0` | `0` |
| 1 | `B−2h_w+h_v−4` | `B−2h_w+h_v+2` |
| 2 | `B+h_w−2h_v−4` | `B+h_w−2h_v+2` |
| 3 | `B−h_w−h_v−4` | `B−h_w−h_v` |

`native_lower_scaled` and `native_upper_scaled` prove that these are the
exact integer interval expressions in `certified_corner_from_fraction_limb`.
`scalar_corner_difference` proves the exact norm difference of each lattice
corner from corner zero. If one upper bound is strictly below every rival's
lower bound, `rust_interval_certificate_eq_nearest` proves that the returned
corner is the exact four-corner minimum. Its strictness also resolves the
tie-break order: a certified winner has no norm tie.

`native_choice_eq_nearest` covers both native control-flow branches: a
certified corner or the exact fallback. Its precise premise is that any
returned code satisfies the strict comparison checked by the Rust loop.
`native_choice_bound_and_congruence` then transfers the earlier all-scalar
lattice bound and endomorphism congruence. These statements retain the
reduced input range `0≤k<n` and the exact fixed basis.

## Proof map and implementation boundary

| Result | Lean declaration | Exact premise | Status |
| --- | --- | --- | --- |
| Four-corner score intervals and strict winner | `score_in_bounds`, `certificate_unique_minimum`, `certified_corner_nearest` | Two fractional coordinates within their two-unit limb envelopes; strict interval separation | Checked |
| Exact corner norm identity | `scalar_corner_difference`, `exact_corner_score` | Fixed `W,V,n` and four floor/ceiling corners | Checked |
| Constant reciprocal and modular inverse certificates | `reciprocal_constant_certificates`, `coefficient_inverse_certificates` | Exact constants in the Lean module | Checked by kernel reduction |
| All-reduced-scalar reciprocal floors | `exact_two_reciprocal_floors` | `0≤k<n`; explicit inverse certificates handle nonzero scalars | Checked |
| Fractional-limb enclosure | `native_fraction_envelopes` | `0≤k<n`; exact high limb of each integer reciprocal product | Checked |
| Native interval expressions and chooser equality | `native_lower_scaled`, `native_upper_scaled`, `rust_interval_certificate_eq_nearest` | Returned code passes the strict Rust interval predicate | Checked |
| Certified and fallback representative | `native_choice_eq_nearest`, `native_choice_bound_and_congruence` | `0≤k<n`; each returned code satisfies the strict predicate | Checked |

The Lean model uses integer products to define the high limbs and exact
`Option` branch result. The Rust routine calculates those products in
64-bit limbs and converts a winning corner to signed 192-bit coordinates;
those word-level operations are checked by native replay but are not yet
refined into Lean. The Rust classifier's loop directly tests the strict
inequality in `nativeCertified`; the loop-to-predicate correspondence is a
source-level link, not a Lean theorem. The subsequent orbit-atlas digit
transport has its separate checked proof in
`../prime-j0-radix943-orbit-refinement-20261012/PROOF.md`.

`python3 experiments/prime-j0-radix943-corner-certificate-20261012/check.py
--check` builds the actual theorem modules with pinned Lean 4.34.1. The
receipt records Lean and native source hashes and every reported theorem's
`#print axioms` output. The proof uses only `propext`, `Classical.choice`,
and `Quot.sound` from Lean's standard foundations. It contains no `sorry`,
`admit`, or custom research axiom. `lean4checker --fresh` was unavailable on
the development host.
