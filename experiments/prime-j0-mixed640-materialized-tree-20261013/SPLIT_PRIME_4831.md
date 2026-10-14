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
the largest is 1,564. A direct two-x point table for 20 positions has
`20 × 806 × 96 = 1,547,520` digit bytes before the terminal table and
metadata. It therefore trades more table memory for one fewer digit
position relative to the 21-step direct-seed format.

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

`SplitPrime4831Bound.lean` contains checked proofs of the quotient identity,
norm scaling, one-step contraction, all 20 radius checks, and the terminal
norm bound from the actual minimum-norm selected lattice representative.
The Lean 4.34.1 `#print axioms` audit reports only standard foundations
`propext`, `Classical.choice`, and `Quot.sound` for the terminal theorem.
The [proof receipt](split-prime-4831-validation.json) pins the model, screen,
Lean module, imported sources, command, and axiom output.
The theorem quantifies over digit trajectories and explicitly assumes the
digit norm and exact step laws. The finite 4,831-residue selector and its
connection to a native point table are currently verified by the Python
enumeration; a Lean selector theorem and native implementation are the next
proof and implementation steps. CPU speed remains unmeasured.

| Result | Lean declaration | Exact bridge and status |
| --- | --- | --- |
| Norm primality screen | `SplitPrime4831.norm_trial_division`, `SplitPrime4831.norm_sqrt_cap` | Checks every divisor from 2 through 69 and bounds the square root; checked. |
| Quotient update | `SplitPrime4831.recoding_step_identity` | Assumes the integer numerator equals `4831k`; checked. |
| Norm scaling and contraction | `SplitPrime4831.pi_norm_identity`, `SplitPrime4831.step_bound` | Assumes the digit norm bound and exact coefficient step; checked. |
| Twenty-step radius | `SplitPrime4831.radius_checks`, `SplitPrime4831.selected_terminal_bound` | Starts at `selectedCandidate scalar`; assumes all 20 digit norms and step identities; checked. |
| Canonical digit selector | Open | Needs a Lean definition and coverage proof for all 4,831 residue classes, followed by a connection to the exact native lookup. |

Reproduce the screen and Lean check from this directory:

```
python3 split_prime_4831.py > split-prime-4831-screen.json
LEAN_PATH=/private/tmp/lean-split-prime /Users/adamburan/.elan/toolchains/leanprover--lean4---v4.34.1/bin/lean SplitPrime4831Bound.lean
```
