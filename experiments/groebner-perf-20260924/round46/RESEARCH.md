# Research context and the next transform hypotheses

Retrieved 2026-10-01. These are primary research sources, not validation of this implementation.

Barbier, Cheballah and Le Bars, [On the computation of the Möbius transform](https://arxiv.org/abs/2004.11146), develop polynomial representations and transform strategies for structured Boolean functions. Their analysis shows that representation and variable order can change work substantially, while sparse-list techniques depend on the intermediate supports. This supports testing structure-specific methods with explicit applicability checks; it does not establish novelty or performance for our block-symmetric recursion.

Banik and Regazzoni, [Compact Circuits for Efficient Möbius Transform](https://eprint.iacr.org/2023/948.pdf), describe degree-bounded compressed ANF recursion and sequential processing that reuses workspace. For fixed degree d, their discussed recursive software storage is O(n^(d+1)). Their implementation discussion also identifies recursion/context-switch overhead. This motivates both compressed or tiled specialization for the current memory limit and the explicit leaf-size variants in our CPU screen. Their circuit measurements do not establish Metal, CUDA, or our full checker performance.

Erginbas, Kang, Polito and Ramchandran, [Adaptive Sparse Möbius Transforms for Learning Polynomials](https://arxiv.org/abs/2602.06246), study sparse real-valued Boolean polynomial learning with adaptive queries. That oracle model and coefficient domain differ from the present exact packed-GF(2) certification task. Its query bound cannot be imported as a Gröbner-basis or independent-verification speedup.

## Conditional degree pruning, after the current screen

The following is a candidate derivation for an additional engineering test. It is not implemented, experimentally validated, or claimed novel here.

Suppose a coefficient slice has independently established fixed-variable degree at most d. During a descending-bit subset transform, the lower, not-yet-transformed bits of an index still specify ANF monomial factors. Thus, at a butterfly of size2^j, a source offset whose lower j bits have weight greater than d must be zero: previously transformed higher bits cannot reduce that lower-bit weight. Its XOR can be skipped. The degree bound can be obtained conservatively from original nonzero terms during the checker's fresh scatter, per residual feature. Duplicate cancellation can only lower it. No producer degree assertion is needed.

The candidate exact XOR count is

`sum(j=0..x-1) 2^(x-j-1) * sum(i=0..min(d,j)) binomial(j,i)`.

This is bounded by `(d+1)*2^x`, since the generating-function sum over j of `binomial(j,i)/2^j` is2 for each fixed i. The full transform uses `x*2^(x-1)` XORs. This bound describes a transform that still writes an exponential output table. It is not an asymptotically subexponential solver, and it must include the costs of degree checking, offset generation, indexing and any loss of vectorization in measurements.

A first exact reference should cover all small low-degree coefficient arrays, variable-order changes, inconsistent claimed bounds, actual bounds recomputed from canceled/unsorted original terms, empty slices, and two equation limbs. Before integration, inspect the real frozen inputs' per-feature degree distribution and the measured share of query time spent on specialization. If specialization is a small share, prioritize affine-proof parity checking or its GPU kernel instead.

Compressed degree-bounded recursion may also be a more direct route around the coefficient table's memory cap than a larger dense allocation. It must stream into complete branch/proof checks with global budgets and complete roots; a smaller transform workspace alone is not larger-variable verification support.
