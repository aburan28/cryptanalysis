# Three-orbit linked τ atlas gate

Freeze this protocol, `linked_atlas.py`, the native linked mode, and
`make_linked_fresh_fixture.py` before generating or scoring new scalar
inputs. The original 64-case panel is design data. The new 256-case
Sage fixture has a distinct deterministic label and is held out from
selection.

The width-four digit table retains slots 0–4 and 8. Replace slots
5, 6, and 7 with coefficient seeds `(2,-4)`, `(4,-8)`, and `(4,4)`.
They are respectively twice slot 8, four times slot 8, and twice slot
4. Verify that each unit orbit covers its original six residues modulo
`τ⁴`, that all 54 nonzero residues remain unique, and that every
integer coefficient state recodes to zero via the strict norm-descent
plus finite closed-ball proof.

The native seed path uses six doublings and two mixed additions,
compared with the original four and four. With the same two unit
rotations and nine orbit-image multiplications, preparation falls from
`83` to `75 M+S` per one-use scalar. Score every original and new
held-out scalar with this preparation charged separately, including
failed recoding attempts if any. Retain individual paired operation
counts and signs. Sage must independently compute the three new seed
points and scalar outputs; native replay must check all nine prepared
seeds and the final scalar point on the original, edge, and new
held-out panels. Keep the original path as a regression control.

The original 64-case result only selects this candidate. A claim of CPU
speedup requires a full-operation paired timing receipt from a
physically isolated host. `cpu_speedup_claim` and
`academic_novelty_claim` remain null here.
