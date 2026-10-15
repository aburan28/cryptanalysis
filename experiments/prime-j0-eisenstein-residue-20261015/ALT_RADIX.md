# Norm-110557 Eisenstein digit radix

The radix-15 variant selects the Eisenstein digit prime `π = 334 - τ` with `τ² = 3τ - 3` and `N(π) = 110557`. Its 15 full two-x digit rows and terminal table retain **27,429,548 bytes**, below the 32 MiB cap. The frozen implementation reproduced all 12,288 independently computed secp256k1 scalar points on the same unseen uniform fixture used by the norm-136531 cache candidates. The [serial Tier 1 panel](tier1-alt-radix-cpu40-manifest.json) paired it with the norm-136531 ten-row cache under the [frozen acceptance rules](tier1-alt-radix-cpu40-rules.json). Its 96 arms and 48 pairs completed with stable artifacts; one A/A control missed the predeclared range, so the timing aggregate is unknown.

## Recoding and table geometry

Write a scalar-lattice representative as `a + bτ`. For the chosen `π`, reduce `a + 334b` modulo `110557` and choose a nearest digit `d_a + d_bτ` in that residue class. Set `k = (a - d_a + 334(b - d_b))/110557`. The quotient coordinates are

`a' = 331k - (b - d_b)`, `b' = k`.

The identity `(334 - τ)(a' + b'τ) = (a - d_a) + (b - d_b)τ` follows from `τ² = 3τ - 3`. The pinned [Lean module](AlternateRadix.lean) checks the exact quotient identity, `N(334-τ)=110557`, the no-small-divisor certificate, and the factor definition of primality. It also proves pair-norm nonnegativity, norm scaling by the digit prime, and the weighted inequality `100Q(z-d) ≤ 101Q(z)+10100Q(d)`. Its 15-step recurrence theorem shows that an initial norm at most `7·2^260` and digit norms at most `110557` force terminal norm below 5,000; the resulting upper bound is 3,443. The [build output](alternate-radix-lean-check.log) includes `#print axioms`; the selector-corner theorem uses the standard `propext`, `Classical.choice`, and `Quot.sound` foundations, while the other listed structural theorems use `propext` and `Quot.sound`.

The digit-norm premise has an elementary bound that avoids relying on the exhaustive maximum. Put `N=110557`, let `r` be a signed residue with `0≤r≤(N−1)/2`, and set `b₀=round(665r/(2N))`, `a₀=r−334b₀`. For `e=2Nb₀−665r`, nearest rounding gives `|e|≤N`. The exact identity `4NQ(a₀,b₀)=e²+3r²` and the resulting bound `Q(a₀,b₀)<N` are checked in Lean as `digit_candidate_norm_identity` and `rounded_digit_norm_below_prime`. The native selector searches this candidate and takes the minimum norm, giving `Q(d)<N` for every signed residue; Lean checks that implication in `selected_digit_norm_below_prime` under the stated minimum-norm premise. The [digit screen](screen_alt_digit_prime.py) checks the candidate identity, rounding bound, and selected-digit comparison for every residue. `quotient_norm_step_from_selected_digit` then proves the per-step norm recurrence from that digit bound and an exact quotient equation.

The [independent digit screen](screen_alt_digit_prime.py) exhaustively enumerates the 55,279 signed residue representatives, checking the congruence and rotation norm for each. Its [record](alt-digit-geometry.json) reports maximum digit norm 36,631 and 18,427 sign/rotation seeds including zero. The terminal construction uses `|a|,|b| ≤ 100` and norm below 5,000; it has 14,901 points and 3,025 orbit seeds including zero. The native replay reached this terminal domain for every frozen input. Lean now proves that a four-corner selector output lies within the 130-bit coordinate envelope under exact floor-remainder and basis-coordinate hypotheses, that this envelope implies `Q(a,b)≤7·2^260`, that a minimum-norm digit has `Q(d)<110557`, and that fifteen exact selected-digit quotient steps end below 5,000. The theorem `terminal_from_verified_digit_steps` exposes each residue, selection, quotient, and norm-tracking obligation for a fixed-limb implementation. The current implementation asserts the terminal bound when recoding; connecting its actual arithmetic and selector to those Lean hypotheses remains open.

The four-corner selector also has a direct coordinate envelope. Its lattice basis is `W=(671331852483699643819086596696745227419,−367917413016453100223835821029139468248)` and `V=(−238911465918039986966665730306072050094,303414439467246543595250775667605759171)`, with determinant equal to the scalar order `n`. Let `q_w=floor(kV₁/n)` and `q_v=floor(−kW₁/n)`. The identity `k(1,0)=(kV₁/n)W+(−kW₁/n)V` shows that every offset `(d_w,d_v)∈{0,1}²` yields `a+bτ=αW+βV` with `−1≤α,β<1`. Thus `|a|≤|W₀|+|V₀|=910243318401739630785752327002817277513<2^130` and `|b|≤|W₁|+|V₁|=671331852483699643819086596696745227419<2^130`. The [constant screen](screen_selector_corner_bound.py) checks the determinant, subgroup congruences, equal basis norms, and these strict margins. Lean proves the same bound in `selector_corner_coordinate_bound` under exact remainder and coordinate equations. Its `terminal_for_selector_corner` theorem composes the bound with the 15-step recurrence under an explicit per-step hypothesis. The fixed-limb reciprocal extraction, corner-certification dispatch, and digit-selection link to those hypotheses remain to be formalized.

| Result | Lean declaration | Status |
| --- | --- | --- |
| Exact quotient by `334−τ` | `quotient_step` | Checked |
| Centered-error identity for the candidate digit | `digit_candidate_norm_identity` | Checked |
| Rounded digit norm and selected-digit implication | `nearest_digit_rounding_error`, `rounded_digit_norm_below_prime`, `selected_digit_norm_below_prime` | Checked for every signed residue under the minimum-norm premise |
| Norm contraction for the selected digit | `quotient_norm_step_from_selected_digit` | Checked under exact quotient and minimum-norm hypotheses |
| Four-corner coordinate envelope | `selector_corner_coordinate_bound` | Checked under exact remainder and coordinate equations |
| Initial norm at most `7·2^260` | `selector_initial_norm_bound` | Checked from the coordinate envelope |
| Terminal norm below 5,000 after 15 selected-digit steps | `terminal_from_verified_digit_steps` | Checked under exact selector, residue, norm-tracking, and quotient hypotheses |
| Fixed-limb reciprocal extraction, corner dispatch, actual digit-selection minimum, and 15-step implementation composition | — | Open |

The [hash-guarded overlay](native_alt_radix_overlay.py) applies to the frozen norm-136531 native source and builds the new rows using `334G - τG` as the successive base. It retains the same two-x orbit selection and affine layer reduction. The exact source, binary, failed first assertion receipt, corrected build, and replay are preserved in the [native provenance archive](alt-radix-native-provenance.tar.gz), SHA-256 `38194c291c28fe76efd057cdb6f08c60784e0ce9bc0c5dbdadea9cc9113b7090`. The first assertion failure came from a draft overlay that still used the prior `371` digit coefficient; the corrected hash-guarded overlay uses `334` in both digit selection and window-base advance.

## Measurement boundary

Each panel arm performs 96 batches of 128 distinct SHAKE256-derived scalar multiplications, with table construction and fixture loading outside Rust `Instant`. Every output is checked against independent binary multiplication after the interval. The worker serializes jobs, pins execution to CPU 40, and records exposed cloud-instance topology, cgroup limits, throttling, steal time, memory, and adjacent A/A controls. This is Tier 1 batch-throughput evidence; the result status follows the frozen A/A and paired-interval gates.


## Serial panel

The completed job `51a80dfd759e4d5e8d5196a0a031aa78` has [raw arms and pair records](alt-radix-tier1-raw.tar.gz), SHA-256 `fe6bf3c7aa5334cfbfdce606b31000e28876ba00857ef49fdd7b43c6d31cbcdd`. The [independent audit](tier1-alt-radix-cpu40-audit.json) verified the manifest, source and binary hashes, exact replay, all 96 arm outputs, all 48 pairs, and the predeclared gates.

| Tier 1 uniform scalar stream; 12,288 outputs per arm | Norm-136531 ten-row cache | Norm-110557 full two-x |
| --- | ---: | ---: |
| Retained table bytes | 33,318,020 | 27,429,548 |
| Mean timed interval | 66.625558 ms | 65.244457 ms |

The descriptive median paired reference/candidate ratio was `1.019807`, with paired bootstrap 95% interval `[0.995605,1.041598]`. The A/A control after comparison in repeat 4 measured `0.830042`, outside `[0.90,1.11]`. The aggregate remains `unknown_after_tier_gate`; its qualified comparison ratio is `null`.
