# Halftrace-basis reuse in exact N41 pair enumeration

For each fixed pair-product coefficient, six halftrace images now generate the quadratic roots for **all 63 nonzero W6 seed sums** by XOR. The complete N41 run replaced **64,161** direct per-seed halftrace evaluations with **12,282** basis evaluations, while producing exactly the same 128,656 relaxed curve points as the independent linear-map enumerator and repeating all nine frozen group-query decisions and probe counts. The in-process local enumeration interval was 313.422 ms for this variant versus 268.838 ms for the linear-map arm, so this version does not improve the measured component wall time on this run.

## Exact transform

On `GF(2)[t]/(t^41+t³+1)`, let `p` be one of the 2,048 product-span elements, `s=Σ_{i=1}^6 s_i t^i`, and let `H` denote the odd-degree halftrace. The quadratic pair-output reduction has a scaled right-hand side `β_p(s)=f_p s²`, where `f_p=(p²+1)/p²` for the nonzero, nonexceptional product branch. Both square and `H` are `GF(2)`-linear. For fixed `p`, precompute `h_{p,i}=H(f_p t^(2i))` and `b_{p,i}=Tr(f_p t^(2i))`. Then

`H(β_p(s))=XOR_{i:s_i=1} h_{p,i}` and `Tr(β_p(s))=XOR_{i:s_i=1} b_{p,i}`.

The zero-product and zero-leading-coefficient branches retain their original handling. Every proposed root still undergoes the exact residual check, nonzero and trace checks, curve lift, both sign insertions, and group-query replay. The [source](basis_compare.cpp) keeps the earlier linear-map enumerator as a complete set-equality control. The frozen [protocol](protocol.json) binds the source, native binary, runner, nine inputs, prior receipts, compiler, one-worker 120-second wall cap, and 4-GiB combined RSS cap.

| Frozen N41 component | Result |
| --- | ---: |
| Complete unrotated point-set equality | **128,656 / 128,656** |
| Root candidates and exact residual passes | **128,385 / 128,385** |
| Reference direct root-halftrace calls replaced | **64,161** |
| Fixed-product basis halftrace calls | **12,282** |
| Net root-halftrace calls removed | **51,879** |
| Linear-map enumeration, same process | 268.838 ms |
| Basis-quadratic enumeration, same process | 313.422 ms |
| Positive middle-point query | `RELAXED_SUM_HIT`, 21,713 probes |
| Eight target-derived middle-point queries | `COMPLETE_RELAXED_NO_SUM`, 128,656 probes each |

The [native receipt](receipt.json), [guarded execution](execution.json), and [audit](audit.json) check the source and binary hashes, resource limits, complete point sets, root counts, and all nine query decisions against the earlier independently Sage-replayed [direct join](../n41_direct_relaxed_pair_join_20261011/RESULT.md). Peak sampled parent-plus-child RSS was 50,085,888 bytes. The timing is a local stage diagnostic without a host-isolation receipt; the exact halftrace-call reduction is the reproducible implementation result.

This is a pair-generation component with `candidate_id: null`. The remaining per-root residual `H((s+z)²)` is also linear in the six seed bits on each fixed-product quadratic branch; a second basis can replace those calls before another exact point-set comparison. The degree-131 transfer still needs the public target to select a small product family before seed enumeration, because scanning all `2^35` W18 product-span elements is outside the current resource gate.
