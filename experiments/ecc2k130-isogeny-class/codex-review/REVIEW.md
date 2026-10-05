# Review of the Codex ECC2K-130 volcano-descendant investigation (Runs 01–13)

Source reviewed (read-only): `~/Documents/Codex/2026-09-22/prior-conversation-with-codex-conversation-role-2/outputs/`
Five independent reviewers each recomputed numbers in Sage/Python rather than trusting receipts. Reviewer scratch:
`/private/tmp/claude-501/review-r01-03/`, `/Volumes/SSD990/claude-scratch/review-r04-05/`, `/private/tmp/claude-501/review-r06-08/`,
`/private/tmp/claude-501/review-docs/`. (Some reviewers were partly blocked by the full system disk; noted per section.)

## Verdict

The arithmetic and code are essentially correct: no bug invalidates an exact count, and every headline number
that was re-derived reproduced. The scientific content is much thinner than the write-ups suggest:

1. **The 262 descendants are two curves.** Coordinate Frobenius (x,y) ↦ (x^{2^k}, y^{2^k}) is a free group isomorphism
   A000 → A_k (and B000 → B_k). Every "per-descendant" difference in Runs 01–08 is a difference of factor-base
   *presentation* (subspace σ^{-k}(V) on one curve), not of the curve or its endomorphism ring.
2. **Most findings are consequences of isogeny invariance or hold by construction** (embedding degree, point counts,
   gcd(N,h)=1, O_f/NO_f ≅ O_K/NO_K, identical top-degree row spaces, Run-11 duplicate formula, Run-12 "1 unique system").
3. **The empirical "wins" are selection effects.** Run-08's best ratios (0.7075 → 0.9766 as k grows) and EXPLOITABILITY §1
   (B067, −20.7% attempts) are reproduced by a pure-chance model / by searching E0's own subspaces.
4. **The gates could never have been passed.** Expected natural relations per probe are 2^-96 … 2^-108, so "zero natural
   rows" in 16 – 20,960 probes carries no information, and every downstream gate (rank, sparse LA, extraction) was unreachable.
5. **The negative conclusion is correct — but it was predictable on paper** and is already the literature's position for
   prime-degree binary fields (Petit–Quisquater, Galbraith–Gebregiyorgis, Huang–Kosters–Yeo, Diem).

## Independently verified structural facts (all correct)

| Quantity | Value | Check |
|---|---|---|
| t | −22283658519494248867 | recomputed (Lucas sequence and Sage) |
| #E0 = 4N | N = 680564733841876926932320129493409985129, prime | recomputed |
| t² − 4q = −7f² | f = 263 · 146505763881528721, both prime | recomputed, proven |
| Orders | conductors 1, 263, R, 263R; h = 1, 262, R+1, 262(R+1) | qfbclassno + reduced forms |
| H_{−7·263²} mod 2 | squarefree, two irreducible factors of degree 131 | Sage, 0.4 s |
| Embedding degree | ord_N(q) = 216464610000596986937760855436835237 (118 bits), (N−1)/k = 3144 | recomputed |
| 263-torsion | E0: π = −1 on E0[263] ≅ (Z/263)² over F_{q²}; floor: cyclic Z/263² | recomputed on A000, B000 |
| Degree-263 isogenies | ~13 s each over F_q; A090/B021/B067 kernels rebuild, P,Q images match | rebuilt |
| Run-11 CM scalar | δ ≡ 775 − ω (ω eigenvalue of (1+263√−7)/2), β = δ·2^−16, γ = −δ̄, βγ ≡ −11 | recomputed |
| Rho baselines | 60.81 (±, τ), 64.33 (± only), 64.83 (none) bits | recomputed |

## Run-by-run findings

### Runs 01–03 (yield, "degree of regularity")
- [major] E0's lower row-reduced d_reg at k=6 (8 vs 10–11) is caused by **b = 1 being short in the polynomial basis**
  (fewer independent descended equations: 65/90/116 vs 76/107/131); unrelated curves with b = t or 1+t get d_reg **7**.
  Not an endomorphism-ring effect. Reproduced E0 (8, 623) and A010 (11, 8035).
- [major] "Identical top row space across coefficient substitutions" is trivial: the top Boolean-degree part of S4 is
  r·x1³x2³x3³, independent of b; raw d_reg can differ only through the membership indicator.
- [major] EXPLOITABILITY §1 (B067 gives ~20.7% fewer attempts at k=5) is a selection effect: over 1,500 random
  5-dim subspaces of **E0 itself**, 2.1% reach B067's 832 eligible triples (max 1,504); E0's polynomial subspace sits at ~5th percentile.
- [minor] Run-03 rank test cannot fail (one witness per target already gives full rank).
- [minor] Frobenius collisions (2P3+P5+P17 = O ⇔ τ²+τ+2 = 0) are expected for the only F_2-rational curve.
- [minor] Run-02 overstates its correction (2 of 5 descendants were *lower* than E0 at k=4; d_reg tracks membership-ANF parity).
- "d_reg" is a presentation-specific formal degree (Hilbert regularity of a top-degree ideal after RREF), not an ideal invariant.
- Reproduced exactly: E0 k=4..7 counts 7/14/33/63, eligible triples 80/668/10868/79848, excess 0/8/28/60; all 40 k=4 target cells.

### Runs 04–05 (isogenies, embedding)
- Correct. Only substantive content: explicit 263-isogenies are cheap (~13 s). Candidate selection (A090, B021, B067 by
  Run-01 coverage) is meaningless given Frobenius conjugacy.
- Embedding-degree invariance, point counts, pairing facts, ring-homomorphism obstructions: tautological.
- 263-torsion crater/floor structure: textbook (Kohel; Miret et al.), correctly computed.
- [minor] Run-04 archive not self-contained (imports unfrozen `work/` modules; frozen signature mismatch).
- [note] One pre-registered Run-05 prediction was wrong (π(R)+R ≠ 0); corrected and disclosed honestly.

### Runs 06–08 (end-to-end, half-trace, complete-floor subspaces)
- [major] Run-06 natural probes: expected relations ≈ 2^−91.7 over all 16 targets; gate also needs to beat rho, which is
  44–50 bits lower at k = 8..10. Outcome fixed before running.
- [major] Run-06 yield differences are factor-base cardinality: (516/491)^4 = 1.2197 vs reported 1.2205.
- [major] Run-08 best-of-(262×64) ratios match a pure-chance binomial model (k=8: 0.7075 observed vs 0.724 [0.659, 0.782];
  k=16: 0.9766 vs 0.966 [0.941, 0.989]); 5–95% spreads also match. The gate would pass on chance 28–63% of the time.
- [major] The "membership degree no worse" criterion is a **parity coin flip**: ANF degree = k iff the rational-x count is odd
  (verified on all 44 cells). The B094/B129 disqualifications are parity artifacts.
- [major] Run-07 outcome predictable: an arbitrary sparse set has a dense indicator ANF; term ratio ≈ 2^{2k−1}.
- Code checked correct (lift predicate, Z/4 tags, MITM matching, partition counts).

### Runs 09–13 (atlases, shared core, shared solver)
- [critical, a priori] A Frobenius/horizontal atlas is one curve with a factor base split into m subspaces and mixed relations
  forbidden: W = m·Σcᵢ/Σpᵢ ≥ best chart, and forbidding mixed relations costs ~m^{n−1}. Disjointness of columns is forced
  (collision probability ~2^−110). Runs 09–11 measured quantities fixed in advance.
- [major] Run-10 = Run-09 coverage is forced by isomorphism invariance; Run-11's 130·16·C(c,4) duplicate count holds by construction.
- [major] Run-12's "1 unique system" is a tautology (squaring is F_2-linear on coefficients → same row space).
  The 4.07% figure is dominated by a brute-force Python oracle (111.8 s) in the denominator on 12-variable toy systems,
  and is unstable: Run-13's re-run of the same systems gives 8.8%.
- [minor] 63/131 (Run-12) and 120 (Run-13) systems were already inconsistent after row reduction; their "solver time" is process overhead.
- [minor] Run-13 graph-adjacency signal equals its random baseline (0.917–0.972 vs 0.945); Run-13 has results but no write-up.
- Run-11 CM alignment is sound; the minus-dual sign is natural (Aut = {±1}; reverse edge = ±φ̂).

### Documents (PDFs, status, EXPLOITABILITY)
- Both PDFs are stale (full report through Run-10; summary through Run-11 and recommends the experiment Run-12 already rejected). Run-13 undocumented.
- Inconsistencies: 123× vs 96–98× columns (only the latter reproduces 296.8×); 317.4× vs 317.6×; "16 targets" means 16 probes in Run-06
  but 16 targets in Run-09; 13.98% should be 13.89%; membership degree "12–24" vs "8–24"; stale headlines ("Yes as bounded engineering heuristics").
- Missing framing: the literature already expects summation-polynomial IC on prime-degree binary fields to lose to rho.
- References checked real and correctly attributed; the signed-Frobenius rho baseline should cite Wiener–Zuccherato and Gallant–Lambert–Vanstone.

## What survives
A clean, verified CM/volcano dataset for ECC2K-130 (conductor factorization, four orders and class numbers, 2 × 131 floor split,
explicit 263- and 11-isogenies, the class-group relation 𝔩₁₁ ~ 𝔭₂^16 with the minus-dual calibration), and the clean attribution
that after Weil restriction every curve-dependent effect enters through rational-lift membership Tr(x + b/x²) = 0 and Z/4 tag balance.
Suitable as a short negative-result note, with the tautologies relabelled as expected consequences, an equal-budget E0 subspace-search
control, and computed expected yields replacing "zero natural rows".
