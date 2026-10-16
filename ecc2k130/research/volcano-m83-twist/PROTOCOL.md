# Protocol (frozen before any census or screen output was read)

Question. Does any curve reachable by isogeny from the GF(2^83) Koblitz curves, or any
field representation of the Koblitz curve itself, give a factor base that clearly beats
the Koblitz (crater) factor base on four-summand yield?  Both twists: a2 = 0 (81-bit
prime ELL, cofactor 4) and a2 = 1 (53-bit prime N53, cofactor h1 = 2*10459*53951; the
crypto repository's N83 index-calculus instance).

Candidates.
1. The crater E0 (b = 1) and all 6474 conductor-6473 floor curves of ../volcano-m83
   (b = 1/j over the class-polynomial roots), for each a2.  Smaller isogenies (l = 3..13)
   land on E0 itself (scratch check, recorded in the report).
2. The crater in 200 field representations: factor-base domain span{1, rho, ..., rho^(k-1)}
   with rho_i = SHA-256("volcano-m83-twist-rep:%d" % i) truncated to 83 bits (i = 0..199),
   which is the polynomial subspace of the representation with modulus minpoly(rho_i).

Instrument (native/f83x, validated by scripts/control_run06.py, which must reproduce all
24 run06 counts exactly).  k = 12.  Factor base = sign-0 lifts of the rational nonzero x
in the domain.  Tag = log of [n]P in E(F_q)[h] (Z/4 or Z/h1).  Yield = number of
(4-subset, sign vector) with signed tag sum 0 mod h, natural and at equal cardinality
S = 1856 (first S points in SHA-256("%d" % mask) order, run06's rule).
Normalised yield Y = eligible / (16 * C(S, 4) / h).

Decision.  A candidate "clearly beats" the crater only if its equal-cardinality yield
exceeds the crater's by more than 5 % for a2 = 1 (Poisson sd ~ 1 % at S = 1856) or by more
than 0.1 % for a2 = 0, AND it keeps the crater's column folding.  Floor curves are not
defined over F_2 (Frobenius maps E_b to E_{b^2}), so they lose the 83-fold signed-Frobenius
column folding of the N83 pipeline; that cost is reported structurally, not re-measured.
Only a candidate that clearly beats the crater goes on to an end-to-end N83 run against
the 28.688 ms K3425/root4 baseline (crypto: research/n83_final_tournament_results_20261015).
