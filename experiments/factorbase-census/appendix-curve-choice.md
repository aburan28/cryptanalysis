# Appendix: why no other curve in the isogeny class can help

Draft appendix for the ECC2K-130 descendant factor-base measurement report (23 September 2026 edition). Scope: closes the question "could a different curve in the isogeny class of E0 give summation-polynomial index calculus a better factor base or an easier point decomposition problem". All numbers below were recomputed from the subgroup order alone; scripts are listed at the end.

## A.1 The isogeny class of E0 and which of its members can be constructed

E0 is the a = 0 Koblitz curve y² + xy = x³ + 1 over GF(2^131). Its Frobenius π = τ^131 has trace

    t = -22283658519494248867

which matches the recurrence for τ² + τ + 2 = 0 and not the a = 1 alternative. The order Z[π] has discriminant t² − 2^133 = −7 f² with conductor

    f = 38531015900842053623 = 263 × 146505763881528721.

Both prime factors appear to the first power. The Legendre symbols are (−7 / 263) = +1 and (−7 / p₂) = −1 where p₂ denotes the 57-bit prime. The endomorphism ring of E0 is the maximal order O_K of K = Q(√−7), which has class number 1, so E0 is alone on the crater of every ℓ-volcano in the class. The class decomposes by endomorphism ring as follows.

| Endomorphism ring | Conductor | Number of GF(2^131)-isomorphism classes |
|---|---|---|
| O_K | 1 | 1 (E0) |
| Z + 263·O_K | 263 | 262 |
| Z + p₂·O_K | p₂ | p₂ + 1 = 146 505 763 881 528 722 |
| Z[π] | 263·p₂ | 262·(p₂ + 1) |
| total | | 38 531 015 900 842 054 149 ≈ 2^65.0 |

The 262 curves at conductor 263 are the descendant floor measured in the main report. Every curve at conductor p₂ or 263·p₂ is unconstructible and unreachable:

- Any isogeny from E0 to a curve whose endomorphism ring has conductor divisible by p₂ has degree divisible by p₂, because an isogeny can change the conductor only by divisors of its degree.
- The kernel of such an isogeny is a cyclic subgroup of order p₂ of E0. Since p₂ divides f, π acts on E0[p₂] as the scalar t/2 mod p₂, whose multiplicative order is 12 208 813 656 794 060 ≈ 2^53.4. The kernel points are therefore defined over GF(2^(131·k)) with k ≈ 2^53. No field element of that size can be written down.
- The alternative construction through complex multiplication requires the class polynomial of the order of conductor p₂, of degree p₂ + 1 ≈ 1.5 × 10^17.

Consequently the main report's complete 263-floor census already covers every curve in the isogeny class that can exist on a computer other than E0 itself. There is no further stratum to search. Even in principle, a curve on the p₂ levels could not be used against the challenge, since the discrete logarithm instance cannot be transferred to it.

## A.2 The single parameter through which a curve enters the algorithm

Write a descendant in the form y² + xy = x³ + a₂x² + a₆ and set c = a₆^{1/2} = j^{−1/2}. Every curve-dependent quantity in Gaudry–Diem index calculus with Semaev summation polynomials over a binary field depends on the curve only through c and through the single bit Tr(a₂). The entry points are listed with their consequences.

**Factor-base membership.** Substituting y = xz gives z² + z = x + a₂ + a₆/x², so a nonzero x is the abscissa of a rational point if and only if

    Tr(x) + Tr(c/x) = Tr(a₂),

using Tr(a₆/x²) = Tr(c/x). The substitution y = x/c maps the rational set of curve c onto the set {y : Tr(1/y) + Tr(cy) = Tr(a₂)} and maps F₂-subspaces to F₂-subspaces. The number of rational abscissae in a subspace V is therefore |V|/2 plus a sum of Kloosterman sums, whose typical size is √|V|. At |V| = 32 this fluctuation is the 5-to-23 range of "rational x counts" recorded in the main report. At |V| = 2^33, the smallest size relevant to k = 4 on this field, it is 2^−16.5 relative and invisible.

**Summation polynomials.** In characteristic 2 the third summation polynomial is S₃(x₁, x₂, x₃) = (x₁x₂ + x₁x₃ + x₂x₃)² + x₁x₂x₃ + a₆. This was verified numerically on 200 random curves over GF(2^11). The coefficient a₆ appears only as a constant term and a₂ does not appear at all. Higher summation polynomials are resultants of S₃ with itself and inherit the property. The Weil-descended Boolean systems therefore have identical monomial support on every curve in the class, which is why the main report's 261 reachable controls on each profile all report maximum F4 degree 6 and why the n = 19 study found formal regularity 11 on all 1,371 systems.

**Symmetries available to reduce the system.** Translation by the rational 2-torsion point T = (0, c) acts on abscissae as x ↦ c/x. The substitution u = s/(x + s) with s = a₆^{1/4} conjugates this to u ↦ u + 1, so on every curve equally the factor base can be chosen as a subspace containing 1 in the u-coordinate and the 2-torsion symmetry used. The Frobenius τ exists only on E0, and the F₂-subspaces of GF(2^131) stable under squaring are exactly four, of dimensions 0, 1, 130 and 131, because 2 is a primitive root modulo 131 and Φ₁₃₁ is irreducible over F₂. The Frobenius symmetry is therefore unusable with a subspace factor base on E0 and nonexistent on descendants. Descending the volcano replaces O_K by Z + 263·O_K, so the cheapest non-integer endomorphism changes from τ of norm 2 to 263τ of norm 2·263². No descendant has a symmetry that E0 lacks.

**Weil descent.** The GHS magic number of a curve with a₆ ∉ F₂ over GF(2^131)/F₂ is at least 130, by the same irreducibility of Φ₁₃₁. Genus 2^129 covers are not an attack.

**Transfer.** A 263-isogeny between E0 and any floor curve costs about 2^15.6 field multiplications in either direction. A speedup on a floor curve is a speedup on E0 by definition, and the converse holds as well. The question of this appendix is therefore equivalent to asking whether the Boolean function Tr(1/y) + Tr(cy) has more linear structure for some c than for c = 1, which is the subject of the next section.

## A.3 Census of full-density factor-base subspaces

A subspace V has every nonzero element rational for curve c exactly when Tr(1/y) + Tr(cy) is constant on c^{−1}V minus zero. An adapted factor base of this kind would double the factor-base size for the same point-decomposition cost, worth a factor 2^k in relation yield. Let N_d(c, ε) denote the number of d-dimensional subspaces of GF(2^n) on which Tr(1/y) + Tr(cy) equals the constant ε off zero. The random model for a subset of density ρ predicts E[N_d] = [n, d]₂ · ρ^(2^d − 1).

N_d was computed exactly for every Frobenius class of c at n = 11 and for 30 classes at n = 13 by canonical-basis depth-first search. At n = 17 and n = 19 the search tree exceeds 2^39 nodes, so N_d was estimated by an unbiased Monte Carlo tree-size estimator over ordered bases, with N₁ and N₂ exact. The estimator reproduces the exact n = 13 counts within two standard errors at every dimension. Random subsets of the same density were measured by the identical procedure as a baseline. The table reports N_d divided by the random-model prediction at each set's own density.

| n | curve-like sets / random sets | dim 4 curve-like | dim 4 random | dim 5 curve-like | dim 5 random | dim 6 |
|---|---|---|---|---|---|---|
| 11 | 374 / 40 | 0.877 | 0.943 | 0.079 | 0.755 | none in either |
| 13 | 60 / 10 | 0.969 | 0.989 | 0.652 | 0.951 | none in either |
| 17 | 82 / 15 | 0.998 | 0.999 | 0.975 | 0.997 | 2 hits, model expects 1.6 |
| 19 | 76 / 15 | 0.9995 | 0.9998 | 0.994 | 1.000 | 10 hits, model expects 14.5 |

Observations.

- Curve-like sets lie below the random model at every size and dimension, with Welch t statistics between −6 and −30 against the random baselines. The inverse function has slightly less affine structure than a random set, consistent with its APN property for odd n.
- The deficit shrinks monotonically with n: 92%, 35%, 2.5%, 0.6% at dimension 5. For the dimensions relevant to GF(2^131) the random model is effectively exact.
- The Koblitz parameter c = 1 is unremarkable at every size. Its two twists sit at ordinary positions of the distribution.
- Dimension-6 subspaces first appear at n = 17 and n = 19 at the rate the random model predicts, and no probe at either size reached dimension 7, where the model expects 10^−17 and 10^−13 subspaces respectively.

At n = 131 the random model gives log₂ E[N_d] = 188.8 at d = 10 and −725 at d = 11. The largest full-density subspace on any curve in the class therefore has dimension about 10. A k = 4 factor base on this field needs dimension near 33. Adapted bases cannot supply it on any curve, and the adapted-versus-polynomial coverage differences measured in the main report (median image 152 versus 120 at |V| ≤ 32) are the small-sample Kloosterman fluctuation described in A.2, not a structural effect.

## A.4 Decision rule for natural-target sampling

A natural target lands in a relation image of size I with probability I/r. With the best measured k = 4 image, I = 880 and r ≈ 2^129, the probability is 2^−119.2 per probe. The expected number of hits in the main report's 8,608 probes is 1.1 × 10^−32. To reach a 95% chance of a single hit at this image size would require about 2^120.8 probes. No sample size that can be executed changes the observed zero, and a zero at any executable size carries no information about relative image sizes.

Recommended rule: run natural-target sampling only when (number of probes) × (exact image fraction) ≥ 3, so that at least a 95% detection probability exists under the null. At k = 4 on GF(2^131) this is never satisfied, so natural-target probing at k = 4 should stop. Comparisons between profiles should be made directly on the exact enumerated image sizes, which are already measured and are the quantity a zero-hit sample would be estimating.

## A.5 Claim boundary

The results of this appendix establish, for the full isogeny class of E0 over GF(2^131):

- Verified: the class structure and the unconstructibility of every member outside E0 and the 263-floor.
- Verified: curve dependence of the Gaudry–Diem algorithm reduces to the scalar c = a₆^{1/2} and the bit Tr(a₂).
- Measured: full-density factor-base subspace counts match or fall below the random model at n = 11, 13, 17, 19, converging to it from below.
- Inferred: no curve in the class admits an adapted factor base of useful dimension, and no curve admits a symmetry or endomorphism unavailable on E0.

They do not establish anything about the asymptotic cost of point decomposition on E0, which is curve-independent and remains the open question for the family.

## Scripts

- volcano.py: trace, conductor, factorization, class numbers, reachability of the p₂ levels.
- subsp.c: exact canonical-basis enumeration of full-density subspaces (n ≤ 13).
- subsp2.c: Monte Carlo estimator with exact N₁ and N₂ (n = 17, 19), validated against subsp.c at n = 13.
- analyze.py: normalization by the random model and Welch tests.
- Result files: n11_all.txt, n11_rand.txt, n13_sample.txt, n13_rand.txt, n17_curves.txt, n17_rand.txt, n19_curves.txt, n19_rand.txt. Three of the 41 sampled n = 19 classes did not complete and are absent from n19_curves.txt.
