# Selective-preparation mixed τ alphabet: freeze protocol

Freeze `selective_mixed_atlas.py`, this protocol, and
`make_selective_fixture.py` before generating the new 256-case Sage
panel. The original 64-case panel is design data, including the
exploratory full-union and selective-preparation screens. The prior
portfolio holdout has already been inspected; it is not a new holdout
for this candidate. The new generator uses a distinct deterministic
scalar label and eight bases with 32 scalars each.

Use the original baseline width-four τ expansion once. At every
coefficient residue, offer the distinct original, two-orbit, and
linked three-orbit digits. There are two choices in each of 18 residues
and one elsewhere. Each choice updates the bounded carry by
`c_(i+1)=(d_i+c_i-e_i)/τ`. The carry starts at zero, may continue for
at most 16 positions after the baseline expansion, and must end at
zero. Verify `N(c)≤896` at every transition and reconstruct the exact
short `a+bτ` representative from each selected stream.

The dynamic program minimizes the existing evaluator's exact source
count plus the preparation cost of **only seed orbits used by its
stream**. Its state retains carry, previous nonzero position, highest
seed, cache mask, and used-seed mask. The preparation graph is the
frozen original/linked union: seven-unit doubles, eleven-unit mixed
adds, the two required unit rotations, and one orbit-image unit per
used seed. Dependencies are built even when their point is not itself
a digit. Validate that the graph charges 83 for the original nine
orbits, 75 for linked nine, and 107 for all 12. Verify the dynamic
program's accumulated evaluator cost against a separate recount of
its selected digit stream on every case. Ties use stable seed/state
order.

Report the per-case selected seed set, preparation, evaluator cost,
total, portfolio reference, selected-digit hash, carry-state search
size, and correctness. Compare the 64 design cases and **new** 256
held-out cases without modifying the frozen algorithm. Source counts
exclude the dynamic program's CPU cost, BigInt short-representative
reduction, and final inversion. An isolated paired full-operation
native benchmark is required before any CPU speedup claim. Build and
validate a native selected-seed evaluator separately; mathematical
reconstruction and a Sage scalar fixture do not by themselves prove
that implementation. Academic novelty remains unproved pending
prior-art review.
