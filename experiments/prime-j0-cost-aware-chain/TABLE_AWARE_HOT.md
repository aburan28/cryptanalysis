# Table-aware Eisenstein representative: prospective experiment

The bounded hot-orbit table makes the evaluation cost of equivalent scalar
representatives depend on their eight-digit table hits. The shortest-L1
representative need not minimize that cost. This experiment chooses between
the two shortest distinct lattice representatives before evaluating a public
scalar. It keeps the same prepared point table, positional miss path, and
batch output normalization as `fused-hot-batch128`.

For each scalar, enumerate the existing 25 lattice candidates in the same
`du=-2..2, dv=-2..2` order. Rank by coordinate L1, with enumeration order
breaking ties. Recode only the first two through the frozen four-step atlas.
Predict the number of mixed additions for each complete eight-digit stream:
a hot orbit costs one, a cold pair costs one per nonzero half, and zero halves
cost zero. An out-of-span baseline is scored by its full positional fallback;
an out-of-span second candidate is ineligible. Select the second only if its
predicted addition count is strictly smaller. Ties retain the shortest-L1
baseline. Scalar equivalence is guaranteed by the subgroup lattice; the
selected digit stream must be evaluated directly without a third recode.

This is an optional, variable-time format for public research scalars. The
second recode and 25 L1 evaluations belong to the online interval. Its extra
integer work may outweigh saved group additions. Operation savings alone
cannot establish a CPU speedup. The table and all setup costs are identical
between arms; charge table preparation when the point makes it
target-dependent in a one-target rho comparison.

## Freeze before new candidate inputs

The independent four-case workload will use 4,096 exactly uniform subgroup
scalars per case from SplitMix64 state `20270117 ^ (curve_index << 32) ^
point_index`, with rejection sampling. Curves, generator and `37P` cases,
generic point replay, and the 128-output normalization block match the
previous hot-orbit protocol. Generate scalar files and independent generic
output digests only after this protocol has been committed and a draft PR
opened. Compare `fused-hot-batch128` with
`fused-hot-adapt2-batch128` on those files, alternating arm order.
Preserve raw failures and all operation counts.

The prospective operation gate requires all 16,384 candidate outputs to
match independent generic scalar multiplication and the candidate to have
at least 3% fewer online mixed additions than the ordinary hot arm in
**each** of the four cases, with identical prepared table size and setup
operations. The online wall-time question remains unknown until an isolated
host runs five paired AB/BA repetitions under the repository isolation
contract. No speedup or academic novelty is claimed before that evidence.

The closest located literature covers GLV lattice decomposition, unit-symmetric
Eisenstein digit sets, and fixed-base lookup tables. Those ingredients are
prior art. This experiment tests their table-aware combination; the limited
search is not an academic novelty proof:

- https://eprint.iacr.org/2013/672
- https://eprint.iacr.org/2013/705
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3758659/

## Exploratory screen

`screen_table_aware.py` used 1,000 separate scalars per law from seed base
`20261301`. This is a feasibility screen, not an acceptance sample. It
predicted 5.25%, 5.60%, 6.30%, and 6.78% fewer mixed additions for the four
subgroup/eigenvalue laws. The two-candidate rule roughly doubled atlas
recoding steps; that online overhead could erase the point-operation saving.
The exact row counts and source hashes are in `table-aware-screen.json`.
