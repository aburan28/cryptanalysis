# One linear solve recovers W18 pair seeds from a proposed N131 output

The W18 pair-output inverse now recovers every admissible XOR seed and source-mask pair from one supplied reciprocal coordinate using **one 19-variable binary linear system**, followed by exact source checks. It replaces the archived loop over 262,143 seeds. On the frozen N131 panel, the method recovered all **130** expected pair outputs and rejected all **66** controls; an independent field implementation matched every linear rank, solution count, product, mask pair, and rejection. An exhaustive N41 raw W6 control matched the complete **991-coordinate** pair-output set, including six coordinates whose seed-linear system had rank below full.

## Seed-linear eliminant

Work over `GF(2^131)=GF(2)[t]/(t^131+t^13+t²+t+1)` on `y²+xy=x³+1`, curve `EC1N131Ckb1heb5f1998f20b`. Let `W18=span(t,…,t^18)`. Source x coordinates are `a,b∈W18`, their XOR seed is `s=a+b`, their product is `p=ab`, and `c` is the unrotated reciprocal x coordinate of their pair sum. The exact pair equation is

`(1+p²)c² + pc + s² = 0`.

Setting `z=pc` gives `z²+z=(c+s)²`. For the odd-degree field, halftrace `H` is `GF(2)`-linear. Every solution therefore has

`p = c⁻¹(H(c²) + Σ_(i=1)^18 s_i H(t^(2i)) + ε)`, with `ε∈GF(2)` and `Tr(c²+s²)=0`.

Every product of two W18 elements lies in the **35-dimensional** span `D=span(t²,…,t^36)`; no polynomial reduction occurs at those degrees. Projecting the displayed equation onto the 96 coordinates outside `D` gives 96 binary linear equations in the 18 seed bits and one branch bit. A trace equation is added. The [native solver](native.cpp) eliminates these 97 equations, enumerates every solution if the matrix is deficient, then tests the exact fixed-seed product image `p=a²+sa`, rational source support, distinct folded columns, and the original pair equation. Thus the 35-dimensional span is an early superset filter; accepted masks still satisfy the exact source law. Frobenius rotation is undone before the solve and replayed afterward.

The target-independent setup computes only 18 halftrace basis images. A query performs one field inverse and halftrace, 19 scaled field elements, one 97-by-19 binary elimination, and exact checks for surviving solutions. The [frozen N131 protocol](protocol.json) binds executable, inherited arithmetic, support, panel, and archived all-seed comparator hashes. W18 has **131,307** rational masks, **1,575,684** usable factor-base points across the six rotations, and **131,068** folded columns. Each run used one worker with a 120-second native cap, 130-second parent cap, and 4-GiB RSS cap. The query clock begins with the supplied coordinate after support loading and basis setup.

| Archived supplied coordinate | Linear rank / candidates | Pair hits | Archived all-seed query | Product-span query | Product-span peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| W18 seed 13,686, rotation 26 | 19 / 1 | 1 | 253.474 ms | 0.042 ms | 2,572,288 B |
| W15-subspace seed 12,004, rotation 0 | 19 / 1 | 1 | 178.880 ms | 0.034 ms | 2,588,672 B |
| Published-point raw coordinate | 19 / 0 | 0 | 174.191 ms | 0.055 ms | 2,572,288 B |
| Trace-one coordinate | 10 / 0 | 0 | 0.003 ms | 0.010 ms | 2,588,672 B |

The [panel](panel.json) adds 64 distinct supported mask pairs with different seeds, retains both exact pair-output roots for each, and adds 64 deterministic trace-zero field controls. Across all **196** cases, 195 matrices had rank 19; the trace-one case was inconsistent after rank 10. The 130 positive cases each yielded one candidate and the expected source pair. All 66 controls yielded zero candidates and zero accepted pairs. The native query intervals ranged from **9.917 µs to 995.250 µs**, with a median of **40.750 µs**; all CPU intervals are local diagnostics on an unisolated host. The deterministic improvement is replacing a 262,143-seed search by one bounded-width linear elimination for a proposed coordinate. The archived comparator retained the same positive and control hits on its four paired cases.

The independent [N131 verifier](verification.json) uses separate carryless multiplication, interleaved squaring, Fermat inversion, the opposite Gaussian pivot direction, and its own fixed-seed image inverse. It replayed the exact pair equation and accepted source masks in every case. The [run receipt](run_receipt.json) binds all 200 native executions and their semantic outputs. The [N41 protocol](n41_protocol.json) enumerates every rational raw W6 mask and both roots for all 496 unordered source-mask pairs. Its [exhaustive result](n41_result.json) compares the inverse with all 991 distinct output coordinates plus 128 non-source trace-zero controls: every output's complete pair set matched. The N41 source here is the raw 32-mask W6 pair geometry; its count is distinct from the N131 six-rotation factor-base size.

For a uniformly chosen nonzero trace-zero N131 field coordinate, [exact counting](bound.json) bounds both the chance of a deficient 19-column span matrix and the chance of passing the algebraic product-span filter by **less than 2⁻⁷⁶**. The bound counts nonzero ratios between the 19-dimensional halftrace/branch span and `D`, and at most two pair-quadratic roots for each nonzero seed and `p∈D`, respectively. It applies to that declared uniform field law; source-derived and target-derived coordinates have their own distributions.

This supplied-coordinate inverse has `candidate_id: null`. The next integration gate is to derive candidate pair outputs jointly from the public point and other partial sums, feed them to this exact oracle, and measure how many whole seed/block families are rejected before source-mask expansion. The existing unpinned N41 twelve-column public relation supplies a full-row replay control for that integration; a source-bound one-worker N131 work and memory calculation must precede an ordinary challenge-point relation run.
