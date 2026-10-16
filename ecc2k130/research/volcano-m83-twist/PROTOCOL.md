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

## Addendum, 2026-10-16: rho over the 53-bit floor (frozen before any output of it was read)

Question.  Does Pollard rho on any conductor-6473 floor curve of the a2 = 1 twist behave differently
from the crater's {±P} rho (S = 0.855 ± 0.146, 6 solves, outputs/rho-a1.jsonl)?

Coverage.  The 6474 floor curves form 78 orbits of 83 under b -> b^2.  (x, y) -> (x^2, y^2) is a group
isomorphism E_b -> E_{b^2} (a2 is in F_2), so the discrete-log problem, the subgroup and every walk
statistic are the same on all 83 curves of an orbit.  One representative per orbit (shift 0:
O00-00 ... O77-00) therefore covers the whole floor up to that isomorphism.  All 6474 curves at one
solve each would take ~45 h on this 4-core VM and is not run.

Runs.  scripts/rho_floor.py: f83x rho MODE 1 ({±P}; floor curves have no tau over F_2), DP bits 14,
seeds 1000 and 1001 on each of the 78 representatives (156 solves), 4 processes; every solve must
recover its fixture scalar.

Analysis.  Pooled S mean ± se against sqrt(pi/4) = 0.886 and the crater's {±P} solves; homogeneity
across orbits by one-way ANOVA on S (78 groups of 2; F against F(77, 78)), reported as a p-value with
no promotion of any single orbit (2 solves per orbit cannot rank orbits).  A floor orbit would "beat"
crater rho only if the pooled floor S were below the crater {±τ^i P} S = 0.107, which the derived
absence of tau on floor curves rules out unless the data contradict the theory.

## Addendum 2, 2026-10-16: {±P} rho on every 53-bit floor curve (frozen before any output of it)

Requested: rho on each of the 6474 floor curves individually, not only one per Frobenius orbit.
Runs.  scripts/rho_floor_all.py: f83x rho MODE 1, DP bits 14, seed 2000 on every floor curve O00-00 …
O77-82 (6474 solves; seed 2000 is disjoint from addendum 1's seeds 1000/1001, so no solve repeats one
already recorded).  Sharded by curve index (--shard i --of k) into outputs/rho-floor-all-a1.shard<i>.jsonl,
resumable, checkpointed to git while running.  Every solve must recover its fixture scalar.
Analysis.  Pooled S mean ± se against √(π/4); one-way ANOVA across the 78 orbits (83 curves each,
F(77, 6396)) and a permutation cross-check; the within-orbit isomorphism predicts no orbit effect and
the absence of τ on floor curves predicts S near √(π/4), not √(π/(4·83)).  The distribution of S is
compared with the Rayleigh law of the collision time.  No single curve is promoted.
