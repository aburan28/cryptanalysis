# Proof of the seven-state terminal correction

For every integer scalar, the exact four-corner lattice chooser produces an
Eisenstein pair `z_0=(a,b)` with `3Q(z_0)≤n` and
`a+lambda*b ≡ scalar (mod n)`. The radix-919 four-corner digit chooser
produces `d_i` with `3Q(d_i)≤919²` and exact quotients
`z_i=d_i+919z_(i+1)`. The same bound and quotient equation hold when a
canonical digit is transported to a queried residue by any of the six
unit codes. These are structural theorems in `DigitCover.lean` and
`OrbitAtlas.lean`.

Let `S_0=0` and `S_(i+1)=919+919S_i`. The quadratic-form triangle bound
gives `3Q(sum(i=0..12) 919^i d_i)≤S_13²`. Exact reconstruction and the
initial bound then give

`3·919^26 Q(z_13) ≤ (2^128+S_13)^2`.

Lean checks the exact integer certificate:

| Quantity | Value |
| --- | ---: |
| `S_13` | 333867756040574733089992648544917225639 |
| `(2^128+S_13)^2` | 454478388289023362446632657401249687164436303382907315841385091483451202039025 |
| `6·919^26` | 667351354723430974419167178071941082233653728682536068007331175186676773536486 |

Thus `Q(z_13)<2`. The identity
`4Q(a,b)=(2a+3b)^2+3b²` and finite integer bounds classify a pair with
`Q<3` as exactly one of `(0,0)`, `(1,0)`, `(-1,0)`, `(1,-1)`,
`(2,-1)`, `(-1,1)`, and `(-2,1)`. The norm bound restricts the same seven
states. In particular, the complete scalar representation is

`z_0 = sum(i=0..12) 919^i d_i + 919^13 z_13`.

Applying the scalar map `(a,b)↦a+lambda*b` and multiplying the generator
gives the window sum plus one conditional terminal correction. This
correction belongs to a single six-unit point orbit at weight `919^13`.

| Mathematical result | Lean declaration | Exact hypotheses | Status |
| --- | --- | --- | --- |
| Norm triangle and reconstruction | `norm_sub_bound`, `recodes_reconstruct` | Integer pairs and exact thirteen quotient steps | Checked |
| Seven terminal states | `thirteen_steps_terminal_norm_lt_two`, `thirteen_steps_terminal_unit` | `3Q(z_0)≤n`, thirteen digits with `3Q(d_i)≤919²`, exact steps | Checked |
| Four-corner nearest digit | `nearest_step_equation`, `nearest_digit_bound`, `recode_digit_bounds` | Every integer pair, radix 919 | Checked |
| Initial lattice pair | `nearest_representative_bound`, `nearest_representative_congruence` | Every integer scalar, exact secp256k1 lattice and eigenvalue | Checked |
| Full recoder with terminal correction | `scalar_recode_terminal_unit`, `scalar_recode_reconstruct`, `scalar_recode_congruence` | Every integer scalar, exact four-corner chooser | Checked |
| Six-unit atlas transport | `unit_image_digit_bound`, `orbit_digit_from_residue`, `orbit_thirteen_terminal_unit` | Correct residue-code lookup and exact steps | Checked |

The pinned Lean 4.34.1 build and all `#print axioms` outputs are in
`lean-build.txt`. Every reported theorem uses only the standard Lean
foundations `propext`, `Classical.choice`, and `Quot.sound`, or no axioms.
The proof modules contain no `sorry`, `admit`, or custom research axioms.
The Rust limb quotient, atlas array population, correction-point unit
transport, and XYZZ group evaluation remain implementation refinement
obligations. The design screen audits the complete radix-919 residue map
and replays exact integer reconstruction; a native format implementation
and independent group replay are separate steps.
