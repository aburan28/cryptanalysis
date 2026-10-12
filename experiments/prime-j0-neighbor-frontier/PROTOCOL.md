# Neighbor-search frontier for paired τ scalar multiplication

## Frozen hypothesis

The gauge-aware search in `prime-j0-gauge-aware-five` compares two or
five axial lattice representatives per scalar. Searching three or four
representatives, ordered by the same L1 lattice norm with stable ties,
may recover much of the five-neighbor point-work reduction for fewer
recodings. These are opt-in scalar-stage experiments. Both new modes
use the same prepared table, exact free-gauge rotation score, point
formulas, and deterministic pair tie-break as the parent experiment.

The frozen diagnostic score is
`6 * tau_steps + 11 * mixed_adds + rotations`. Its weights are an
existing heuristic, not a measured field-operation count. We require
the weighted score to be nonincreasing from the original free-gauge
baseline through two, three, four, and five scored neighbors. Recode
attempts and pair scores must increase with the candidate count.
Every output must match the independent affine point oracle, and each
arm must repeat exactly on its operation counters. The panel retains
the recoding cost even if point work falls. A CPU speedup is not an
acceptance criterion here.

## Held-out gate

Commit source, tests, this protocol, the affine fixture generator, and
the checker before creating fresh 1,024-pair inputs on `glv-j0-32`
and `j0-56`. Freeze the fixture bytes, seeds, and oracle output digest
in a second commit before running any arm. Run baseline, scored two,
three, four, five, five, four, three, two, baseline serially on each
curve under Release and UBSan. Preserve raw successes and failures,
source and binary hashes, operation counters, correctness replay, and
local timing. This host has no verified exclusive CPU and NUMA
partition. Keep `cpu_speedup_claim: null` and
`isolation_receipt: null` regardless of local timing.

The prior five-neighbor result motivates one separate exploratory
screen: parse its atlas recurrence on its older free-gauge fixtures
and count repeated suffix states among the five neighbors of each
nonzero scalar. The script `analyze_tau_suffix.py` and its result are
retained for reproducibility. The shared-state fraction is only an
upper bound on atlas work a perfect suffix cache could save; it is not
a measured CPU benefit or a correctness proof of a cache.

This is a batch scalar-stage diagnostic. A verified one-target result
and a host-level isolation receipt are required for any online CPU
speedup claim. Academic novelty of the combined method is unproved;
τ-adic digit-set recoding has [prior art](https://doi.org/10.1016/j.tcs.2014.06.010).
