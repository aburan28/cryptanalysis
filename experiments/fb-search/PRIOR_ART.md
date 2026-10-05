# Prior art for the factor-base and m = 2 work

This is a check of what in `fb-search/` (and the `pdp-degree-heuristics/` results it builds on) is
already known, in the literature or in this repository, so that nothing is presented as new when
it is not. It covers m = 2 point decomposition on binary curves over prime-degree fields with an
F_2-subspace factor base. "Known" means the result, or a direct special case, is published or
already in this repository. "Refinement" means a small addition to known work, whose novelty is
not claimed. A literature search does not prove novelty; review by someone who knows this
literature is still needed.

## Findings, in order of discovery

| Our finding | Status | Where it already is |
|---|---|---|
| Subgroup targets lie in 2E. On `y^2 + xy = x^3 + b`, `Tr(x1) + Tr(x2) = Tr(1/xR)` is a linear equation in every S_3 descent system, and a trace-zero base makes it vacuous | **Known** | Kosters-Yeo [KY15], Prop. 4.2, 4.7 and 4.9: the morphism `E(F) -> F_2` (kernel 2E) gives a linear polynomial after Weil descent, so S_3 has first fall degree 2. Remark 4.8 suggests adding that equation, or "only look[ing] for relations in the kernel", which is the trace-zero base |
| A trace-zero base doubles `p_dec` but loses that equation | Known mechanism; our tables quantify [KY15] | [KY15] |
| The degree of regularity of the m = 2 system exceeds its first fall degree, and grows with n | **Known** | [KY15] and [HKY15]. Our fitted MXL degree rule is empirical; for m = 2 it is superseded, because no Gröbner solve is needed |
| S_3 is F_2-linear in `e1 = x1 + x2` and `e2 = x1 x2` (squaring is linear), so with `e1 in V` and `e2 in V^(2)` the two-point oracle is a linear system. Equivalently, after the half-trace, `p` is affine in `u` | **Known** | Courtois [Cou16], Sec. 2.4 (half-trace form) and Sec. 2.5. In this repository, `experiments/linearized-half-decomposition` (`lhd.py`) implements exactly this oracle for the polynomial-degree subspace, as an `n x (3l - 1)` system, and checks it against brute force |
| The linearization condition `dim V + dim V^(2) <= n`; for prime n no subspace beats `dim V^(2) >= 2l - 1`, so geometric progressions and the prefix base are optimal | **Known** | `experiments/linearized-half-decomposition/README.md` (the condition `sum_{i<=k} dim V^i <= n`, with Hou-Leung-Xiang [HLX02] and Bachoc-Serra-Zémor [BSZ18] for the bound). Its consequence for this solver is ours (`htsolver.py`) |
| Splitting in two (and three) in `2^(n/3) poly(n)` | **Known** | [Cou16], Sec. 2.5 and 3 |
| Total index-calculus cost with any linearized k-point oracle is at least `2^(2n/3)`, 30 bits above rho at n = 131 | **Known** | `experiments/linearized-half-decomposition/README.md` (`lhd_budget.py`) |
| One-target online cost about `2^(n/3)` after about `2^(2n/3)` precomputation (our online scaling) | **Known exponent; plain rho is not the fair comparison** | Bernstein-Lange [BL12]: rho with a precomputed table reaches about `1.77 l^(1/3)` online after about `1.24 l^(2/3)` precomputation. An IC online figure that excludes setup should also be compared against this, not only against plain `sqrt(pi r / 2)` rho |
| Subspace and basis choice (subfield bases; symmetry-breaking bases); symmetrized summation polynomials; SAT/XOR-SAT solvers; auxiliary-variable splitting | **Known** | Shantz-Teske [ST13], Galbraith-Gebregiyorgis [GG14], Faugère et al. [FHJRV14], Trimoska-Ionica-Dequen [TID19], Semaev [Sem15], Karabina [Kar15] |
| Beyond the linearization limit the oracle degrades gracefully: the search dimension is exactly `max(0, dim V + dim V^(2) - n - 1 + [V in ker Tr])`. The `+[V in ker Tr]` is the trace row of [KY15] becoming vacuous, so once that dimension is positive the trace-zero yield gain and the lost row cancel exactly | **Refinement** of the above; measured on 54 bases (`results/halftrace-compare.jsonl`) | `lhd.py` enumerates the affine solution space too, but states the method only for `3l - 1 <= n`. The exact law, with the trace correction, is our measurement. It does not move the exponent: the cost is minimized at the linearization boundary |
| Lower bound for this solver family: online cost at least `2^(n - 2l) * 2^max(0, 3l - n - 2)`, minimized near `l = (n + 2)/3` at about `2^(n/3)`, the [BL12] exponent | Follows directly from the rows above | It means m = 2 subspace IC **cannot beat generic rho with precomputation asymptotically** |
| `PDP2ht`: the linear oracle wired into the ic-bench one-target pipeline (collection and descent, with walk rerandomization), with an exact online cost model and measured verified runs | Engineering and measurement, not a cryptanalytic claim | The walk rerandomization `Q + i [a0]G` is standard |
| Exact rank-process law and workload replay; the rarest-column predictor; the lazy solution count | Measurement methodology and engineering | — |

## What this means

- In this setting, m = 2 with an F_2-subspace base over a prime-degree binary field, the
  literature together with this repository's `linearized-half-decomposition` experiment covers
  every structural result we found. What our work adds is measurement: exact cost models, an
  integrated end-to-end one-target pipeline, and verified runs. It adds no new exponent.
- The barrier is the product-set bound `dim V^(2) >= 2l - 1`, which holds for every
  F_2-subspace at prime n. Any route below `2^(n/3)` online or `2^(2n/3)` total needs a factor
  base that is **not** an F_2-subspace, or a decomposition that is not a linearized S_3 oracle.
  `linearized-half-decomposition` also records that Frobenius-orbit unions of V do not help this
  oracle.
- One-target comparisons should report both the plain rho reference that AGENTS.md requires and
  the precomputation-rho reference [BL12].

## References

- [BL12] D. J. Bernstein, T. Lange. Computing small discrete logarithms faster. INDOCRYPT 2012; ePrint 2012/458.
- [BSZ18] C. Bachoc, O. Serra, G. Zémor. Revisiting Kneser's theorem for field extensions. Combinatorica 38 (2018).
- [Cou16] N. T. Courtois. On splitting a point with summation polynomials in binary elliptic curves. ePrint 2016/003.
- [FHJRV14] J.-C. Faugère, L. Huot, A. Joux, G. Renault, V. Vitse. Symmetrized summation polynomials. EUROCRYPT 2014.
- [GG14] S. D. Galbraith, S. W. Gebregiyorgis. Summation polynomial algorithms for elliptic curves in characteristic two. INDOCRYPT 2014; ePrint 2014/806.
- [HKY15] M.-D. A. Huang, M. Kosters, S. L. Yeo. Last fall degree, HFE, and Weil descent attacks on ECDLP. CRYPTO 2015; ePrint 2015/573.
- [HLX02] X.-D. Hou, K. H. Leung, Q. Xiang. A generalization of an addition theorem of Kneser. J. Number Theory 97 (2002).
- [Kar15] K. Karabina. Point decomposition problem in binary elliptic curves. ePrint 2015/319.
- [KY15] M. Kosters, S. L. Yeo. Notes on summation polynomials. arXiv:1503.08001.
- [PQ12] C. Petit, J.-J. Quisquater. On polynomial systems arising from a Weil descent. ASIACRYPT 2012.
- [Sem15] I. Semaev. New algorithm for the discrete logarithm problem on elliptic curves. ePrint 2015/310.
- [ST13] M. Shantz, E. Teske. Solving the elliptic curve discrete logarithm problem using Semaev polynomials, Weil descent and Gröbner basis methods. ePrint 2013/596.
- [TID19] M. Trimoska, S. Ionica, G. Dequen. A SAT-based approach for index calculus on binary elliptic curves. ePrint 2019/313.
