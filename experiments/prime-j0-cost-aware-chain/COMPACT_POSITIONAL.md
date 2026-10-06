# Compact positional tau table

## Frozen design and claim boundary

The older positional tau mode prepares 64 layers of 18 points, regardless of
subgroup size. The scalar has already been reduced to two Eisenstein
coordinates by an exact lattice search, so its tau expansion usually visits
far fewer layers. On the prior 32,768-scalar full-digit fixture, the highest
used layer was 8 on `glv-j0-32` and 18 on `j0-56`; these observations motivate
this experiment and are **not** its prospective result.

The compact mode allocates `ceil(bitlength(r-1)/3) + 2` layers, capped at 64.
This gives 11 and 21 layers for the two study curves. The rule is a capacity
heuristic, not a proof that every scalar fits. If recoding needs more layers,
the evaluator calls the generic multiplier on that scalar and reports a
fallback. Its output is still correct; its operation score is unknown and
cannot pass the operation gate. The public scalar and subgroup point
requirements match the original positional method.

The compact builder retains only these layers in a heap point table, uses
projective tripling to build the same points as the full table, and batch
normalizes them with one inversion. It does not change the lattice reducer,
digit table, unit rotations, mixed addition formula, or online accounting.
The evaluator uses the same actions and affine output as `pos-global` when
there is no fallback. This is a table-sizing implementation experiment, not
an academic-novelty claim.

Before any new candidate or comparator arm runs, freeze the code, this
protocol, the disjoint-input generator, and the comparison runner in a
commit. Generate eight 4,096-scalar cases for `P`, `37P`, `101P`, and `103P`
on both curves with SplitMix64 rejection seed `0x9CB865CD8130F257`, excluding
all prior fixture scalars and all earlier accepted same-curve scalars. Freeze
the scalar files, hashes, and generic-reference output digests in a separate
commit before running the candidate or comparator.

The prospective gate requires all 16 arms to verify against the frozen
generic outputs; exact equality of compact and full positional addition,
rotation, and output-inversion counts in all eight cases; zero fallbacks;
compact point-table bytes and preparation tripling count each at most one
third of the full positional control. Preserve every raw exit, timeout,
output digest, and preparation field. The ordinary Mac panel is a
correctness and operation experiment. A CPU speedup needs the repository's
host-level isolation receipt and repeated paired timing, so the local timing
fields cannot satisfy this gate.
