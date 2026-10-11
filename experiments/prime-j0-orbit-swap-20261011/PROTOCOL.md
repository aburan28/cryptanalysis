# Fixed-size orbit-cover seed swaps

The construction keeps the radix-1024, twelve-window, 67,338-seed format
fixed. Each seed represents at most four norm-bounded class images under
`1`, `tau`, `tau^2`, and `rho=1+tau`. A class is *rho-only* if none of the
selected seeds reaches it through the first three maps. The objective is
to reduce the number of rho-only classes without adding affine point rows
or weakening complete residue coverage.

For one selected seed, record the classes for which it is the sole
provider. A replacement seed is admissible only if it covers all those
classes. Choose a replacement that strictly reduces the rho-only count;
break ties by seed norm and canonical class index. Sweep seed slots in
order until a full pass makes no swap. Recompute the priority assignment
over the resulting seed set, preferring a tau map when one exists. The
independent verifier must check all 174,764 classes and 1,048,576 exact
residues, selected seed use, digit norms, and the priority rule.

The previously observed 4,096-scalar panel is design data. Commit the
optimizer, resulting cover, complete verifier, and holdout tools before
generating a new 4,096-scalar panel. The new panel rejects modular
collisions with all listed prior panels. Replay both covers on exactly
the same scalar points; retain each digit path and terminal. An
independent verifier checks the digit seed/map/unit, exact scalar
congruence, terminal bound, and prior-panel disjointness. Native point
replay must compare every new scalar point with the priority control and
independent binary checks before promotion to a runtime experiment.

The stage result is a cover and operation-count result. A wall-time
comparison needs a paired end-to-end run that passes
`../../docs/ISOLATED_BENCHMARKS.md`.
