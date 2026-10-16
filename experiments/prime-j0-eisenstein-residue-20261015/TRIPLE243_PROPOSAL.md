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
`Q(state_16) ≤ 844 < 5000`. The native implementation would use the same
norm-5000 terminal table as the current radix.

## Proof map and implementation gate

| Claim | Lean declaration | Status |
| --- | --- | --- |
| Norm, quotient, and shared point recurrence | `Triple243Radix.conjugate_primePair243`, `quotient_step`, `two_scalar_horner243` | Build and axiom audit recorded in `triple243-lean-check.json` |
| Rounded digit and selector-window inclusion | `Triple243Digit.rounded_digit_norm_below_radix`, `rounded_in_native_window` | Same audit |
| Integral digit quotient | `Triple243Digit.exact_quotient` | Same audit |
| Sixteen-step terminal norm | `Triple243Radix.sixteen_quotients_terminal` | Same audit |

The statement is conditional on the certified initial lattice bound and on
the selector returning a digit no longer than the rounded candidate. The
next implementation step is a separate native `243 + omega` arm with exact
scalar and point replay, followed by a Tier 1 paired comparison against the
frozen `81 + omega` arm and the OpenSSL reference on the same one-restart
point. The current radix-81 panel and transfer bundle remain frozen while
this candidate is developed.
