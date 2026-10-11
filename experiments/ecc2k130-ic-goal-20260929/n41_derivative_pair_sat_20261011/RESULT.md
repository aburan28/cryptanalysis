# Exact branch elimination in the N41 two-pair target circuit

The free branch bits in the N41 two-pair relaxation can be eliminated exactly. A complete known-positive assignment satisfies the resulting target-conditioned XCNF. The encoding saves six variables, three clauses, three native XOR rows, and 8,697 formula bytes against the frozen halftrace encoding for the same positive input. Four bounded unpinned searches, including one with an active XOR matrix, reached `BOUNDED_UNKNOWN` at the 35-second parent cap. The exact direct join remains the terminal method for these N41 middle-point queries.

## Exact equivalence

For odd field degree, `H(w)²+H(w)=w+Tr(w)`. Write a pair equation as `v+H(u²)+ε=0`, where `v=pz`, `u=s+z`, and `ε` is free in `GF(2)`. Its derivative is

`v²+v+u²+Tr(u)=0`.

The polynomial equation `v²+v+u²=0` itself implies `Tr(u)=0` by taking the field trace. It is therefore equivalent to the existence of a branch bit satisfying the original equation and trace clause. The same argument applies to the reciprocal S3 link with `v=z_left z_right z_target` and `u=z_left+z_right+z_target`. The circuit uses one sparse field multiplication per relaxed pair and two for the middle-point link; squaring is linear. This elimination applies because the branch bits are existential variables in this relaxation. The independently checked positive source masks and pair reciprocals satisfy every clause and native XOR row of the new formula.

## Frozen N41 experiment

The [construction protocol](protocol.json), [solver protocol](solver_protocol.json), and [wide-matrix protocol](matrix_protocol.json) bind source, inputs, solver, flags, formula hashes, one worker, a 35-second parent cap, and a 4-GiB combined RSS guard. The [audit](audit.json) checks source and output hashes, search progress, absence of terminal SAT/UNSAT lines, cap statuses, and actual XOR-matrix use.

| Input / solver mode | Variables | AND gates | Clauses | XOR rows | XCNF bytes | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Positive / default | 3,082 | 1,844 | 5,659 | 1,122 | 178,738 | `BOUNDED_UNKNOWN` at 35.009 s |
| Target-derived control 0 / default | 3,377 | 1,844 | 5,659 | 1,417 | 184,913 | `BOUNDED_UNKNOWN` at 35.170 s |
| Target-derived control 1 / default | 3,396 | 1,844 | 5,659 | 1,436 | 185,470 | `BOUNDED_UNKNOWN` at 35.079 s |
| Positive / enabled XOR matrix | 3,082 | 1,844 | 5,659 | 1,122 | 178,738 | `BOUNDED_UNKNOWN` at 35.082 s |

The parent killed each solver after its recorded cap; peak combined RSS ranged from 45.7 to 74.5 MB. The default solver declined the 1,002-row XOR matrix because its 2,896 columns exceeded its default matrix limit. The widened run used one matrix and still reached its cap. These statuses are censored search evidence. The [direct group join](../n41_direct_relaxed_pair_join_20261011/RESULT.md) gives exact membership for the same positive and target-derived middle points; the SAT rows do not revise those outcomes.

The next N41 component should construct exact pair domains for the present `D=P+π(P)` points and join them against these middle-point inputs, counting the reduction relative to 128,656 relaxed points. The existing [978-state domains](../n41_w6_exact_pair_state_branching/prepare/receipt.json) encode sums of raw source points as `1/(x+1)`; the present relaxation encodes sums of transported points as `1/x`, so those domains cannot be joined directly. For the N131 public query, this suggests an indexed source-pair filter rather than further rewriting of these three XCNF equations. This remains a component design (`candidate_id: null`).
