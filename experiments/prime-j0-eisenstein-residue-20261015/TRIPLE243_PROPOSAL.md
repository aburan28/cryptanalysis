# Sixteen-step `243 + omega` scalar recurrence

The radix `243 + omega = 244 - tau` has Eisenstein norm `58807`. It gives an
exact 16-step representation of a certified secp256k1 scalar pair with initial
norm at most `7·2^260`, using a digit of norm below `58807` at each step. Its
point recurrence is `243P + omega(P)`: five j=0 triplings, one endomorphism
rotation, and one projective addition. The fixed recurrence therefore uses
80 triplings and 16 rotations/additions. The existing `81 + omega` recurrence
uses 80 triplings and 20 rotations/additions. Digit-table construction and
lookups must be measured before selecting either radix.

## Exact integer construction

Represent a scalar by `a + b tau`, where `tau² - 3tau + 3 = 0`, and write
`Q(a,b) = a² + 3ab + 3b²`. For a centered nonnegative residue
`0 ≤ r ≤ 29403`, choose

```text
D = 58807
b = floor((485r + D)/(2D))
a = r - 244b
```

Then `e = 2Db - 485r` satisfies `|e| ≤ D`, and

```text
4D Q(a,b) = e² + 3r².
```

Hence `Q(a,b) < D`. The signed residue uses the negated digit. A selector
that minimizes norm over a window containing this rounded digit inherits the
same bound. With `A = current_a - digit_a` and
`B = current_b - digit_b`, the residue equation is `A + 244B = Dk`, and the
exact next pair is `(241k - B, k)` because

```text
(244 - tau)(241k - B + k tau) = A + B tau.
```

The norm contraction used for the terminal certificate is

```text
100D Q(next) ≤ 101 Q(current) + 10100D.
```

Iterating this inequality from `Q(initial) ≤ 7·2^260` gives
`Q(state_16) ≤ 844 < 5000`. The native implementation uses the same
norm-5000 terminal table as the current radix.

## Proof map and implementation gate

| Claim | Lean declaration | Status |
| --- | --- | --- |
| Norm, quotient, and shared point recurrence | `Triple243Radix.conjugate_primePair243`, `quotient_step`, `two_scalar_horner243` | Build and axiom audit recorded in `triple243-lean-check.json` |
| Rounded digit and selector-window inclusion | `Triple243Digit.rounded_digit_norm_below_radix`, `rounded_in_native_window` | Same audit |
| Integral digit quotient | `Triple243Digit.exact_quotient` | Same audit |
| Sixteen-step terminal norm | `Triple243Radix.sixteen_quotients_terminal` | Same audit |

The statement is conditional on the certified initial lattice bound and on
the selector returning a digit no longer than the rounded candidate.

## Native replay and next gate

The opt-in [native module](joint_norm58807.rs) and
[command module](rho_restart_joint243.rs) implement that arm. The
[hash-guarded overlay](native_rho_restart_joint243_overlay.py) extends an
exact radix-81 source snapshot without changing the frozen radix-81 panel or
its transfer bundle. It uses a ninth doubling power for wider radix-243
digits. The macOS ARM64 release binary with SHA-256
`c963fca09e5e0a2a96adca5f44d0e1f69ffa7eb1c4e3b7f5936acb1a7f1c4ada`
passed [393 independent point-output checks](triple243-local-replay.json):
the frozen one- and 128-restart fixtures, alternate `Q` points, 128 fresh
seeded pairs, and five edge pairs. The same binary retained the frozen
radix-81 first-point output. The replay also enumerated 29,403 positive
centered residue classes; its selected digit norm reached at most `19441`.

The frozen one-restart radix-243 Q graph constructs 17 points through one
graph edge and 16 direct seeds. The radix-81 graph constructs 21 points
through 13 edges and eight direct seeds. In the 128-restart stream the
radix-243 graph constructs 1,821 points. These counts identify Q-table
construction as the next optimization target. The radix-243 direct builder
now chooses the cheapest signed unit-orbit representative by coordinate
popcount, constructs that representative, and rotates it back to the
canonical seed. For the independently reconstructed first-restart digit set,
the 16 direct seeds require 64 modeled group additions under this rule,
versus 112 for constructing the canonical coordinates directly; the one
separate graph edge is unchanged. The
[independent graph audit](triple243-direct-graph-audit.json) freezes the
reconstructed digits, seed list, source hashes, and exact count boundary.
The added rotations and their field costs
belong in the charged Q-preparation interval. Neither operation counts nor
local elapsed times decide the wall comparison. The next gate is a matched
Tier 1 one-restart panel against the frozen radix-81 arm and OpenSSL on the
same public point, with Q preparation charged and A/A controls. The batch
question follows that primary result.
