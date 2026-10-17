# Norm-6481 rounded digit bound

Every centered residue for the `81+ω=82-τ` radix has an Eisenstein digit
of norm strictly below `6481`. This supplies the uniform digit bound in
the [20-step terminal theorem](Triple81Radix.lean). The pinned
[Lean module](Triple81Digit.lean) proves the bound and places its rounded
candidate in the search window used by the native selector.

Let `0 ≤ r ≤ 3240`, `N=6481`, and
`b=⌊(161r+N)/(2N)⌋`. Set `a=r-82b`. The norm in the `(1,τ)`
basis is `Q(a,b)=a²+3ab+3b²`. Exact expansion gives

`4N Q(r-82b,b)=(2Nb-161r)²+3r²`.

Integer rounding gives `|2Nb-161r|≤N`; the residue interval gives
`r²≤3240²`. These inequalities imply `Q(a,b)<N`. The native selector
tests lift zero and coefficients within two of `⌊161r/(2N)⌋`; the rounded
`b` lies at that center or one above it. A selector that retains a digit
of no greater norm inherits the bound. Signed negative residues use the
negative of the selected positive digit, preserving `Q`; residue zero
uses `(0,0)`.

| Result | Lean declaration | Hypotheses |
| --- | --- | --- |
| Rounding error | `Triple81Digit.rounding_error` | Any integer residue |
| Search-window inclusion | `Triple81Digit.rounded_in_native_window` | Any integer residue |
| Norm identity | `Triple81Digit.norm_identity` | Any integer residue and coefficient |
| Uniform candidate bound | `Triple81Digit.rounded_digit_norm_below_radix` | `0≤r≤3240` |
| Selected-digit bound | `Triple81Digit.selected_digit_norm_below_radix` | Centered residue and selected norm no greater than the rounded candidate |
| Integral quotient | `Triple81Digit.exact_quotient` | The digit matches the current pair's residue modulo `6481` |

Run `python3 verify_triple81_digit_lean.py` from this directory. The
[proof receipt](triple81-digit-lean-check.json) records the pinned
`leanprover/lean4:v4.34.1` build, source hashes, command output, and
`#print axioms` audit. The [native replay verifier](verify_triple81_native.py)
independently checks the selector's exact search rule against every residue
class and records a maximum selected norm of `2107` alongside 393 exact
point outputs. Connecting this mathematical selector to the concrete Rust
loop and refining the Jacobian tripling operation into the abstract point
map are the remaining formal proof steps. The integral quotient lemma gives
`next=(79k-(b-db), k)` when
`(a-da)+82(b-db)=6481k`, the residue equation used by the recoder.
