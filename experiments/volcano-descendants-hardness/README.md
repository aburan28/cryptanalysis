# ECC2K-130 volcano descendants: hardness sweep

`sage sweep.sage` (SageMath 10.9, about 4 min on an M4 Pro) writes `results.json` and `descendants.csv`.

E0 is `y^2 + xy = x^3 + 1` over F_{2^131}, using the modulus `x^131 + x^13 + x^2 + x + 1`. Every invariant below is independent of the basis.
Z[π] has conductor `f = 263 · P`, where `P = 146505763881528721` is prime. The volcano therefore has four levels, `O_c = Z + c·O_K` for c | f.

| Level | Disc | h(O_c) | Smallest noninteger degree | τ ∈ End | Instantiated |
|---|---|---|---|---|---|
| c = 1 (crater) | −7 | 1 | 2 | yes | E0 |
| c = 263 | −484183 | 262 | 121046 | no | **all 262** |
| c = P | −7P² | P+1 ≈ 2^57.02 | (1+7P²)/4 | no | algebraic only |
| c = 263P (floor) | −7f² | 262(P+1) ≈ 2^65.06 | (1+7f²)/4 | no | algebraic only |

`(−7|263) = +1`: 263 splits, giving 2 horizontal kernels and 262 descending ones. `(−7|P) = −1`: P is inert, so all P+1 P-isogenies from E0 descend.
To build the P and 263P levels you need isogenies of degree P ≈ 2^57, which is out of reach. Their hardness rows follow from the shared invariants below.

## Exhaustive 263 sweep (264 kernels)

The script works on the twist, where `E0t(F_q)[263] = (Z/263)²`. It computes a Vélu isogeny for each of the 264 kernel lines, then returns to trace t.

- 2 kernels are horizontal and give j = 1, i.e. back to E0. The other 262 descend.
- The 262 descendants have 262 distinct j-invariants, in 2 Frobenius (j ↦ j²) orbits of 131 each. None has j ∈ F_2.
- All 262 are `y^2 + xy = x^3 + b` (a = 0), and each has #E = 4N.
- 263-structure: the twist of every descendant has a cyclic `Z/263²` part, while the crater has `(Z/263)²`. This confirms End = O_263 for each one.
- GHS/Weil descent magic number: E0 has m(b) = 1, and **all 262 descendants have m(b) = 131**. Descent to F_2 would give genus ≈ 2^130, so no descendant is weak to GHS.
- DLP transfer: for each descendant, the script builds the F_q-rational 263-isogeny E0 → E_d from the same kernel polynomial (the char-2 twist fixes x). It maps a point of order N to a point of order N. **Verified for 262/262.**

## Shared invariants (identical for every curve in the isogeny class)

| Quantity | Value |
|---|---|
| #E | 4 · N, N prime (130 bits) |
| Trace | −22283658519494248867 |
| Embedding degree | 216464610000596986937760855436835237 (118 bits), so MOV/FR is infeasible |
| Anomalous / supersingular | no / no |
| Twist order | 2 · 263² · (114-bit prime) |
| Rho, negation only | 2^64.33 iterations |
| Rho, negation + τ (131-orbit) | 2^60.81 iterations |

## Conclusion

No descendant, at any level, is weaker than E0.
On a descendant, native rho is harder (2^64.33) because τ is lost, and GHS gets worse (m goes from 1 to 131). MOV, anomalous and the twist are unchanged.
The ECDLP on each descendant is equivalent to the ECDLP on E0, since one degree-263 isogeny evaluation connects them (verified explicitly on the 263 level). The class's effective hardness is therefore E0's 2^60.81.
The only per-curve differences are the coefficient b, which feeds into summation-polynomial and Gröbner presentations, and End. Neither changes the group.
The next section tests whether b changes the index-calculus cost.

## Summation polynomials and Gröbner bases: does b matter?

`pdp_descendants.py` runs the `../pdp-scaling` pipeline at the real field size n = 131:
S_{m+1}, Weil descent onto an l-dimensional F₂-subspace V, then msolve (F4 over F₂).
Each instance has a planted decomposition, and every returned solution is lifted and re-added to check it. All instances below were solved and verified.
`analyze_pdp.py` produces the tables.

**Standard factor base V = span{1, z, …, z^{l−1}}, m = 3.** `pdp_m3.csv` has 2576 instances in shuffled order: E0 × 80 seeds, all 262 descendants × 4, and 40 random-b curves × 4.

| l | curve | ANF monomials | median peak matrix rows | median pairs reduced | max degree / first fall | median CPU |
|---|---|--:|--:|--:|---|--:|
| 4 | E0 | 1043 | 4474 | 370 | 6 / 6 | 0.069 s |
| 4 | descendants | 1061 | 4625 | 341 | 6 / 6 | 0.071 s |
| 4 | random b | 1061 | 4477 | 340 | 6 / 6 | 0.072 s |
| 5 | E0 | 3436 | 13056 | 586 | 6 / 6 | 0.279 s |
| 5 | descendants | 3466 | 14360 | 476 | 6 / 6 | 0.282 s |
| 5 | random b | 3466 | 14380 | 460 | 6 / 6 | 0.284 s |

- **Descendants vs random-b curves:** no difference on any F4 metric (Mann–Whitney p ≥ 0.06). The descendant b values are unremarkable, even though these curves share E0's group.
- **Orbit 0 vs orbit 1:** no difference (p ≥ 0.16). That's expected, since σ maps (E_b, V) to (E_{b²}, σV) exactly, so each Frobenius orbit is a single PDP class.
- **E0 differs** by 3·C(l, 2) monomials, about 9% fewer peak rows at l = 5, and more pairs. The solving degree is unchanged, and CPU shows no significant difference at l = 5 (p = 0.28).

**Why E0 differs.** For m = 3, the descended coefficient of the monomial pair_{i}(a, a′) · v_{j,c} · v_{k,c} has the factor (b + w_c⁴), where w_c is the c-th basis vector of V.
That factor vanishes exactly when b^{1/4} ∈ V. E0 has b = 1 and 1 ∈ V, so the standard factor base kills these monomials.
The effect belongs to the pair (b, V), not to the curve. The controls check this for m = 3 (runs) and m = 4 (monomial support, `s5_support.txt`, l = 5):

| Factor base | E0 | descendants / random b |
|---|---|---|
| std {1, z, …} | sparse (3436; S₅: 401816) | full (3466; S₅: 404296) |
| shift {z, …, z^l}, 1 ∉ V | full (3466; S₅: 404296), 484 pairs, 13632 rows: same as the descendants on std | — |
| qroot {b^{1/4}, z, …} | = std | sparse (3436; S₅: 401816), but 27 s, 29k pairs, 31k rows |
| dense {w, z, …}, w random | 17.5 s, 17.1k pairs, 28.4k rows | 17.5 s, 17.1k pairs, 28.4k rows (p ≥ 0.1) |

With 1 removed from V, E0 matches the descendants. With b^{1/4} added to V, a descendant matches E0's monomial support, but it pays 60–100× in F4. The dense control shows the reason: any dense basis vector costs that much, for E0 and descendants alike.
So E0's small edge comes from b^{1/4} = 1 being both in F₂ and the sparsest element of the polynomial basis. A descendant's b^{1/4} is a dense element, so it can't have both properties.
None of these runs moves the degree of regularity (6 throughout) or the cost exponent. At m = 4, l = 4, msolve takes more than 10 minutes per instance on this machine, so m = 4 was compared only structurally.

**Frobenius in the index-calculus cost model.** On E0, τ maps F_V onto F_{σV}, and log τP = λ·log P. The factor base can therefore be closed under τ and keep one unknown per 131-orbit, which cuts the linear algebra by 131×.
A descendant has no τ, because σ sends E_d to a different curve. This advantage, like the rho one, belongs to E0.

**Conclusion:** at summation-polynomial and Gröbner level, the 262 descendants are as hard as a generic curve over F₂¹³¹ and never easier than E0. E0 itself keeps two small conveniences, the (b + 1) monomial cancellation and the τ-quotient, and neither changes an exponent.
