# Joint two-orbit width-four τ atlas gate

Freeze `joint_atlas.py`, the alternate native mode, and this protocol before
scoring the existing 256-case held-out fixture or executing a native replay.
The 64-case original fixture was used to choose the candidate and is design
data. Keep its score separate from the held-out score.

Replace the digit seed orbits `(1,2)` and `(2,4)` at slots 5 and 6 with
`(2,-4)` and `(4,-8)`. These are respectively `2*(1,-2)` and
`4*(1,-2)` in the same slots' residue classes modulo `τ⁴`. Keep the
other seven seeds and the full width-four recoding rule. The new native
preparation computes slot 8 before slots 5 and 6, then doubles it twice.
This removes one mixed point addition in exchange for one doubling:
`-4 M+S` per one-use scalar. It uses the same two unit rotations and nine
orbit-image multiplications. The exact precomputation cost is `79 M+S`
instead of `83 M+S` under the frozen source-count model.

Prove global recoder termination by the closed-ball audit in
`alternate_digit_atlas.py`. On the 64 design cases and 256 held-out cases,
reconstruct every short coefficient pair, score all evaluator operations,
include the `79` or `83` units of seed construction and orbit generation,
and retain per-case deltas and raw failures. This excludes scalar-lattice
reduction and final inversion, which are common but still necessary for
full CPU timing. The primary native correctness gate recomputes scalar
representatives and digits, checks the prepared seeds against independently
computed Sage points, and checks all 350 final scalar outputs against the
existing Sage fixtures. Keep edge cases as a separate correctness gate.

These are operation counts, not CPU measurements. `cpu_speedup_claim` and
`academic_novelty_claim` remain null. A CPU speedup requires a paired
isolated-host receipt charging the entire one-use operation, including
reduction, recoding, seed setup, evaluation, and inversion.
