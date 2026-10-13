# Voronoi-clipped radix-256 terminal table

The opt-in secp256k1 fixed-base evaluator uses fifteen ordinary radix-256 unit-orbit
windows and one directly indexed terminal table. Intersecting the previous
terminal norm disk with the nearest-representative Voronoi strips reduces the
terminal table from 13,314 to **11,023 point entries**. The complete table has
**174,883 point entries**, with at most sixteen selected points per scalar.

## Exact geometry and bound

Use Eisenstein coordinates with `N(a,b)=a²+3ab+3b²` and the subgroup order
`r` in `search.json`. The kernel lattice has basis `U,V` there. Set
`W=U−2V`; direct integer calculation gives
`N(W)=N(V)=N(W+V)=r`. A nearest lattice representative `z` has no larger norm
than its six translates by `±W`, `±V`, and `±(W+V)`. Since
`N(z±w)=N(z)+r±2〈z,w〉`, it follows that
`|2〈z,w〉|≤r` for each of these three vectors.

Every ordinary radix-256 digit `d` obeys `3N(d)≤256²`. The Eisenstein
Cauchy identity
`4N(d)N(w)−(2〈d,w〉)²=3(det(d,w))²≥0` gives
`|2〈d,w〉|≤M`, where the least certified integer support is
`M=100588603464850855725768518207408495723870`. The integer checks are
`3(M−1)²<4·256²·r≤3M²`.

Write `z=Σ(i=0..14) 256^i d_i+256^15 t` and
`S=Σ(i=0..14)256^i=5212658806999670089818851216785665`. Then
`|2〈t,w〉|≤C=floor((r+M S)/256^15)` for each neighbor, where
`C=87506751043387112747509266240600930742795`. The prior norm theorem
also gives `3N(t)≤66051`. These four inequalities define the exact terminal
domain used by `hex.py` and the native table builder.

The domain is unit invariant. `search.py` enumerates every integer pair in
the norm disk, checks all six unit images, and verifies that sector rows are
contiguous. It finds 66,133 pairs: the identity and 11,022 free six-unit
orbits. Each row is addressed with one offset and a contiguous `v` interval,
so scalar evaluation needs no search or large-integer arithmetic for the top
lookup. Fifteen ordinary windows of 10,924 entries each give
`15·10924+11023=174883` entries. This saves 2,291 point entries, or 146,624
point-payload bytes at 64 bytes per entry, against the direct-terminal table.

Under the separate model of sixteen independent selected slots, one stored
entry contributes at most six point choices and each slot has one identity
choice. Balancing `E` entries across the slots maximizes the product
`∏(6e_i−5)`. Binary search over this exact integer capacity first reaches
the subgroup order at `E=174777`. The new table is 106 entries above that
model's capacity threshold. This bound does not apply to dependent digit
choices, shared tables, or different evaluation schedules.

## Lean proof map

The pinned toolchain is `leanprover/lean4:v4.34.1`. Run
`python3 experiments/prime-j0-hex-terminal-20261012/check.py --check` to
rebuild the actual modules and audit every listed declaration with
`#print axioms`. `lean-build.txt` retains the build output and source hashes.

| Mathematical step | Lean declaration | Status |
| --- | --- | --- |
| Three lattice-neighbor norms equal `r` | `PrimeJ0HexTerminal.neighbor_norms` | Checked |
| Minimum among four floor/ceiling corners lies in all three Voronoi strips | `corner_score_norm_identity`, `four_corner_minimum_has_hex_strips` | Checked |
| Both committed seven-word reciprocals satisfy the exact floor inequalities; every reduced scalar is below the 448-bit fraction tail | `native_reciprocals_floor`, `reduced_scalar_below_fraction_tail` | Checked; `check.py` compares the Lean words with the native arrays |
| Exact product splits into high quotient, high fractional word, and seven lower words with bounded remainders | `exact_product_high_fraction_decomposition` | Checked for an exact integer product |
| A native 64-bit multiply-add step fits in 128 bits | `fraction_base_width`, `schoolbook_muladd_fits_double_word` | Checked for 64-bit word inputs and carry |
| One modeled word step preserves weighted value and keeps its output word and carry bounded | `schoolbook_word_step` | Checked for the exact arithmetic step used in the native inner loop |
| A modeled inner pass over reciprocal words preserves the full weighted value and 64-bit bounds | `schoolbook_pass_value`, `schoolbook_pass_bounds` | Checked for an arbitrary finite word list; native array/outer-loop link open |
| Carry propagation preserves weighted value and word bounds; zero carry leaves trailing words unchanged | `carry_pass_value`, `carry_pass_zero`, `carry_pass_bounds` | Checked for an arbitrary finite trailing list |
| A complete modeled pass preserves length and word bounds and adds one shifted scalar-word multiple of the reciprocal | `schoolbook_whole_pass_value`, `schoolbook_whole_pass_length`, `schoolbook_whole_pass_bounds`, `shifted_schoolbook_pass_value` | Checked for arbitrary prefix, reciprocal-word list, and suffix; native four-iteration array mapping open |
| Floor-reciprocal bound and exact product limbs enclose the true scaled cell coordinate within two high-fraction units | `reciprocal_high_fraction_interval` | Checked, conditional on the reciprocal bound and product decomposition |
| Two-unit high-fraction uncertainty gives the classifier score ranges; strict separation certifies a minimum | `fraction_limb_score_intervals`, `strictly_separated_interval_certifies_minimum` | Checked, conditional on the limb interval |
| Cauchy identity and digit support | `inner_cauchy_identity`, `digit_inner_bound`, `support_certificate` | Checked |
| Nearest-neighbor inequalities imply three Voronoi strips | `closest_neighbor_inner` | Checked |
| Fifteen-step reconstruction and terminal strip bound | `terminal_inner_bound` | Checked |
| Norm disk plus strips contain every recoded terminal under the nearest-neighbor hypothesis | `recoded_terminal_in_domain` | Checked |
| Production fixed-width chooser returns a six-neighbor nearest representative for every reduced scalar | Native chooser and prior reciprocal proof; Lean bridge open | Partial |
| Exact 11,023-orbit census and native row indexing | `search.py`, `hex.py`, native audit | Exact executable checks; Lean bridge open |

The checked four-corner lemma uses normalized cell coordinates `0≤x,y≤d`.
It proves that the minimum of the four exact norm-difference scores has all
six Voronoi inequalities. `corner_score_norm_identity` verifies the score
polynomials against the equilateral cell norm. The terminal theorem still
preserves an explicit nearest-neighbor hypothesis. The fixed-width reciprocal
and fraction classifier used by the production chooser are covered by the
earlier exact reciprocal work and independently screened here. The Lean proof
of the classifier's interval geometry is checked. The
`reciprocal_high_fraction_interval` theorem derives the two-unit enclosure
from a floor-reciprocal inequality and exact product-limb decomposition. Its
parameters are arbitrary integers; the native values are `B=2^64` and
`L=2^448`. `native_reciprocals_floor` checks the two seven-word constants
from the native chooser against the exact floor inequalities; `check.py`
compares all fourteen Lean and Rust words before building.
`reduced_scalar_below_fraction_tail` discharges the scalar-range premise.
Proving that the native 512-bit word loop encodes the exact product, handling
the fallback, and composing the branches with `sixNeighborsClosest` remain
open. The formalization is partial at that implementation bridge. The open obligations
and their exit criteria are in
[the problem record](../../problems/prime-j0-hex-terminal-formal-coverage.md).
No theorem uses an assumed conclusion or custom axiom.

`exact_product_high_fraction_decomposition` proves the required decomposition
and remainder bounds when its input is the exact integer product.
`schoolbook_word_step` proves the low-word/carry update preserves weighted
value, and `schoolbook_pass_value` plus `schoolbook_pass_bounds` extend that
identity and 64-bit bounds across an arbitrary list of reciprocal words.
`carry_pass_value` handles the trailing carry, while `carry_pass_zero` proves
that the native loop may stop when carry reaches zero. The whole-pass and
shifted-pass theorems compose these operations and retain the weighted-value,
length, and word-bound invariants for one outer iteration. The native
eleven-word array still needs a verified mapping to four such shifted passes,
including exact slices and the returned high-word indices. Those indices must
then be identified with the exact product quotient and fractional word.
