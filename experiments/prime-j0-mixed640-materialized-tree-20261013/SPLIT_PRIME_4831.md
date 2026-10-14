# Twenty-step radix `71 − τ`

The Eisenstein radix `π = 71 − τ` has prime norm 4,831 and reduces the
fixed-base expansion from 21 to **20 digit positions** while retaining a
finite terminal ball of norm below `56²`. Its quotient update is especially
simple. With `τ² = 3τ − 3`, `τ ≡ 71 (mod π)`, and a selected unit-orbit digit
`d = dₐ+dᵦτ`, put

```
k = (a − dₐ + 71(b − dᵦ)) / 4831
(a', b') = (68k − (b − dᵦ), k).
```

Then `a+bτ = d + π(a'+b'τ)` exactly. The 4,830 nonzero quotient residues
form 805 six-unit orbits. Adding zero gives 806 canonical integer seeds;
the largest is 1,564. The native evaluator stores these seeds as direct
two-x points in 20 rows: `20 × 806 × 96 = 1,547,520` digit bytes. It also
stores 5,680 sign-canonical terminal points for `N(a+bτ)<56²` and removes
the terminal axis fallback. Total retained memory is **1,940,994 bytes**.
It trades more table memory for one fewer digit position relative to the
21-step direct-seed format.

The existing minimum-norm lattice selector gives `3N(z₀) ≤ r`, where `r`
is the secp256k1 subgroup order. Set `R₀ = 33·69²⁰` and
`Rᵢ₊₁ = ⌊(Rᵢ + 1,564 + 68)/69⌋`. Exact integer checks establish
`r < 3R₀²`, `(Rᵢ+1,564)² < 4,831 Rᵢ₊₁²` for all 20 steps, and
`R₂₀ = 56`. The norm triangle inequality and
`N(πz) = 4,831N(z)` therefore give `N(z₂₀) < 56²` for any trajectory
whose selected digits have norm at most `1,564²`.

The [model](split_prime_4831.py) enumerates all 4,831 residue codes, checks
their unit images and exact quotient identities, and replays the frozen
128-scalar fixture against the independent scalar-to-lattice relation. Its
[screen receipt](split-prime-4831-screen.json) records the radii, input hash,
maximum observed terminal norm (1,867), and 11,359 terminal coefficient
pairs in the proved ball. On the fixture, 127 scalars use 20 nonzero digits
and one uses 19.

`SplitPrime4831Bound.lean` proves norm scaling and contraction.
`SplitPrime4831Digits.lean` checks every quotient residue, the 805 nonzero
canonical seeds, and a bounded exact digit step. The composed
`SplitPrime4831Complete.canonical_scheme_terminal_bound` theorem constructs
the selected 20-step trajectory and proves `N(z₂₀)<56²` for every scalar
input to the existing minimum-norm lattice selector. Its companion
`trajectory_table_digit` theorem identifies each digit as one of the six
unit actions on that residue's canonical seed. The Lean 4.34.1
`#print axioms` audit reports only standard foundations `propext`,
`Classical.choice`, and `Quot.sound` for these theorems.

The [native generator](native_split_prime_4831.py) produced a separate
release evaluator. Five native test families passed: all 4,831 residue
codes and 43,479 quotient cases, all 96,720 digit unit images, all 5,680
terminal indices, 128 frozen scalars, and 518 additional deterministic and
boundary scalars checked against independent binary multiplication. The
[complete validation receipt](split-prime-4831-complete-validation.json)
pins the model, Lean modules and axiom output, generated and compiled Rust
sources, release binary, fixture, temporary include shims, and raw test log.
The earlier [bound-only receipt](split-prime-4831-validation.json) remains
preserved as the stage before the selector proof and native evaluator.
The native mapping from the formalized coefficient actions to secp256k1
points is covered by the exhaustive unit-image and scalar replay tests.
Isolated paired CPU timing remains open.

A separate [three-bucket evaluator](../prime-j0-three-bucket-20261014/README.md)
groups signed affine digits by their three order-three unit classes, applies
the endomorphism once to each finished bucket, and then joins the buckets.
It passed the same five native correctness families with **1,425,154
retained bytes**, saving 515,840 bytes relative to this direct two-x table.
Its coefficient recombination identity is checked in Lean. The bucket joins
change the arithmetic mix, so relative CPU latency awaits a paired isolated
measurement.

| Result | Lean declaration | Exact bridge and status |
| --- | --- | --- |
| Norm primality screen | `SplitPrime4831.norm_trial_division`, `SplitPrime4831.norm_sqrt_cap` | Checks every divisor from 2 through 69 and bounds the square root; checked. |
| Quotient update | `SplitPrime4831.recoding_step_identity` | Assumes the integer numerator equals `4831k`; checked. |
| Norm scaling and contraction | `SplitPrime4831.pi_norm_identity`, `SplitPrime4831.step_bound` | Assumes the digit norm bound and exact coefficient step; checked. |
| Canonical digit selector | `SplitPrime4831Digits.canonical_seed_count`, `canonical_cover`, `bounded_step` | All 4,831 residues, seed count, unit image, digit norm, and exact quotient step; checked. |
| Twenty-step trajectory | `SplitPrime4831Complete.trajectory_table_digit`, `canonical_scheme_terminal_bound` | Starts at `selectedCandidate scalar`; constructs each canonical digit and proves the terminal bound; checked. |
| Native point action | Five Rust test families in the complete receipt | Full formal bridge to the concrete field and curve implementation remains open; checked empirically. |

Reproduce the screen and Lean check from this directory:

```
python3 split_prime_4831.py > split-prime-4831-screen.json
LEAN_PATH=/private/tmp/lean-split-prime /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean SplitPrime4831Bound.lean
LEAN_PATH=/private/tmp/lean-split-prime /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean SplitPrime4831Digits.lean
LEAN_PATH=/private/tmp/lean-split-prime /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean SplitPrime4831Complete.lean
```
