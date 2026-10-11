# Linearized roots and residuals for exact N41 pair enumeration

The fixed-product quadratic enumerator now generates both roots **and their exact pair-equation residuals** from six seed-bit images. On the frozen N41 W6 panel it produced the same **128,656** relaxed curve points as the separate linear-map enumerator and repeated all nine public-derived middle-point decisions and probe counts. Relative to direct evaluation in the quadratic path, the two bases remove **165,872 halftrace calls net** across the root and residual equations. The local component interval was 717.655 ms for this variant versus 259.576 ms for the linear-map arm in the same process; this run provides no CPU wall-time improvement.

## Fixed-product linearity

For one product coefficient `p`, write the six-bit seed `s=Σs_i t^i`. The [preceding root basis](../n41_quadratic_basis_enum_20261011/RESULT.md) uses linearity of square and halftrace to form the quadratic root `z_0(s)=Σs_i z_i`, with `z_i=(p/(p²+1))H(((p²+1)/p²)t^(2i))`. The second root is `z_1(s)=z_0(s)+α`, where `α=p/(p²+1)`. For the original halftrace-cubic pair equation, define `e_i=pz_i+H((t^i+z_i)²)`. Its residuals are exactly

`e_0(s)=Σs_i e_i` and `e_1(s)=e_0(s)+pα+H(α²)`.

These identities use only `GF(2)`-linearity. They hold before deciding whether a seed/product choice factors into two source masks. The implementation retains the original exceptional branches, checks that every accepted residual lies in `GF(2)`, checks nonzero trace-zero roots, lifts curve points with both signs, and replays every group query. Its [frozen protocol](protocol.json) binds the source, executable, prior receipts, nine inputs, compiler, one-worker 120-second cap, and 4-GiB RSS guard.

| Complete N41 component check | Result |
| --- | ---: |
| Linear-map and full-basis point sets | **128,656 each; equal** |
| Quadratic root candidates / exact residual passes | **128,385 / 128,385** |
| Direct root halftraces replaced / root basis calls | **64,161 / 12,282** |
| Direct residual halftraces replaced / residual basis calls | **128,322 / 14,329** |
| Net root-and-residual halftrace calls removed | **165,872** |
| Positive middle-point query | `RELAXED_SUM_HIT`, 21,713 probes |
| Eight target-derived middle-point queries | `COMPLETE_RELAXED_NO_SUM`, 128,656 probes each |

The [native receipt](receipt.json) gives the complete point-set and nine-query comparison; [execution.json](execution.json) records a 2.540-second guarded process and 50,216,960 B peak sampled parent-plus-child RSS. The [audit](audit.json) checks source and binary hashes, resource limits, root counts, point-set equality, and exact agreement with the previous independently Sage-replayed [direct join](../n41_direct_relaxed_pair_join_20261011/RESULT.md). The local wall intervals are exploratory because this host has no isolation receipt. In this run, even the unchanged linear-map arm took 259.576 ms, while prior runs of the same algorithm varied substantially; the operation counts and exact outputs are the controlled result.

This remains a pair-generation component with `candidate_id: null`. At degree 131, scanning the full 35-dimensional W18 product span would demand `2^35` product choices and at least 37 basis halftraces per choice before any target-dependent join. A useful transfer must first obtain a small product family from the public target while multiple pair outputs are unresolved; a faster seed scan alone does not clear that search gate.
