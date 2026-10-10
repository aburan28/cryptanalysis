# Q1420 selector-derived leaf-coordinate branch gate

The Q1420 component panel selected the 7,380 × 7,524 native-XOR component
containing all 144 W24 selector bits, but its eight ordinary Q0 attempts all
reached a 2,000-conflict cap. The fixed-witness x ladder located a search
frontier between 16 and 32 released bits. This experiment tests a direct
conditional propagation step: once a 24-bit selector mask is fixed, compute
the leaf x and inverse-coordinate z from the W24 field construction, then
insert those units before SAT search.

For each curve and fixed mask `s`, let `w=sum(s_j*b_j)` and
`u=halftrace(w)`. The existing circuit imposes `w*z=1` and
`u*(x+alpha)=alpha`; for valid masks these force
`z=w^-1` and `x=alpha+alpha*u^-1`. The added units are therefore logical
consequences of the pinned mask and field equations. The producer computes
them from the mask and field constants, not from a stored x-coordinate
witness. The audit independently derives them with the reference arithmetic
and replays any SAT model against every ordinary clause, native XOR, and
signed group sum.

Two frozen panels use the same source and oriented degree-263 descendant
curves and exact W24 bases (`B=16,772,828` per curve) as Q1420:

1. **Fixed-witness controls.** On the four archived full-x releases
   (source/descendant × leaf 0/5), read only the 24 fixed selector bits for
   the released leaf, derive its x/z values, verify that archived z units
   agree and that no x units for that leaf are present, then append 131
   derived x units. Reuse the archived `wz_only` XCNF and full-x unit delta.
   Run one solver attempt per cell with 20,000 conflicts, 30-second internal
   and 40-second external wall caps.
2. **Ordinary Q0 branches.** Freeze eight distinct common source/descendant
   subgroup-usable masks from a target-independent stratification of the
   minimum of six sorted uniform mask indices. For stratum `i=0..7`, set
   `q=(2*i+1)/16` and take the smallest integer `t` in `[1,M]`,
   `M=min(source_last_selected_mask,descendant_last_selected_mask)`, with
   `16*(M-t)^6 <= (15-2*i)*M^6`. Scan upward from `t` to the first mask
   valid on both curves, with nonidentity fourfold projections. Freeze
   source and descendant cells for each mask at leaf 0: `selector_only`
   inserts its 24 selector units; `coordinate_cut` inserts the same units
   plus all 131 x and 131 z values derived from that mask. Keep target-lift
   selectors and the other five leaves free. Use the exact archived public
   Q0 `wz_only` XCNFs. Run one attempt per cell with 2,000 conflicts,
   120-second internal and 45-second external wall caps.

All cells use the pinned CryptoMiniSat 5.14.7 binary, one thread, native
XORs, default Gaussian limits, a sampled 4-GiB RSS guard, and archived
stdout/stderr. Ordinary cells use the exact explicit default matrix flags
from the component panel. The control flags match the archived x ladder.
The primary branch comparison is a **search-status and charged-cost** panel:
for each paired mask record preprocessing, full input hash, solver wall/CPU,
conflicts, restart evidence, memory, verified decompositions, and every
failed or capped attempt. Count the complete eight-branch sequence; do not
divide its cost by the number of branches and call it a one-target solve.
Baseline ordinary Q0 is the archived exact-input default cell from the
component panel. The branch's shorter external guard may censor a cell
earlier; such a cell has unknown conflict-cap outcome.

The source, protocol, runner, and auditor must be committed **before**
mask or cell generation. `experiment.py freeze` writes `masks.json`,
`cells.json`, and 36 exact unit deltas; commit those inputs and their
full-formula SHA-256s before solver launch. Run controls first, then ordinary
paired cells in the frozen order. `audit.py --write` must reconstruct the
complete XCNFs, independently check the field/group mask derivation, all
raw transcript and resource receipts, and every SAT model. A solver's
`INDETERMINATE` or wall cap is `BOUNDED_UNKNOWN`, not UNSAT.

This is a conditional-leaf propagation and one-fixed-leaf branch diagnostic,
not a free-selector PDP candidate. Q1420 keeps `candidate_id: null` until
held-out ordinary-query relation yield, rank novelty, complete matrix work,
target descent, and matched one-target online IC/rho accounting are measured.
The host has no CPU-isolation receipt, so all wall times remain exploratory.
