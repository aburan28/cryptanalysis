# ECDLP hardness across the ECC2K-130 isogeny class

Scope: every F_q-isogeny class member of the Certicom ECC2K-130 Koblitz curve E0 : y² + xy = x³ + 1 over F_q, q = 2^131
(modulus z^131 + z^13 + z^2 + z + 1): the crater curve E0, all 262 conductor-263 floor curves (A000–A130, B000–B130,
Codex labels reproduced exactly), and the two levels of conductor p and 263p that nobody has written down.

Produced by two multi-agent workflows (184 agents; 129 completed, 55 lost to usage limits and backfilled as described in §9).
All numbers below come from scripts under `/Volumes/SSD990/ecdlp-hardness-work/` (paths in §10). No attempt was made on the
actual challenge DLP; all solved DLPs are toy instances with planted logarithms.

## 1. Answer

**No curve in the class is easier than E0. The best known cost is 2^60.81 ideal rho iterations for E0 and for all 262
floor curves.** (2^60.91 with the Bailey et al. 2009 walk.)

| Level (conductor) | End | # curves | Explicitly known | Native rho (log₂ iter.) | Effective (best known) | Why |
|---|---|---|---|---|---|---|
| 1 (crater) | O_K = Z[τ] | 1 | E0 | **60.81** | **60.81** | rho on ⟨−1, τ⟩ classes of size 262 |
| 263 (floor) | Z + 263·O_K | 262 | all 262 | 64.33 | **60.81** | one F_q-rational 263-isogeny up to E0, built and verified on all 262; ≤ 2^15.6 F_q-mults per instance |
| p | Z + p·O_K | p + 1 ≈ 2^57.02 | none | 64.33 | **[60.81, 64.33]** | lower end needs an unimplemented char-2 higher-dimensional (Kani) isogeny pipeline |
| 263p (= Z[π]) | Z[π] | 262(p + 1) ≈ 2^65.06 | none | 64.33 | **[60.81, 64.33]** | cheap 263-step, then as level p |

p = 146505763881528721 (prime, inert in Q(√−7)); f = 263·p is the conductor of Z[π].

- **Floor curves are intrinsically √131 ≈ 11.4× (3.52 bits) harder** than E0 for rho, because their j has degree 131 over F_2,
  so they have no Frobenius self-map (τ^k ∉ O_263 for 0 < k < 131). The cheap ascending isogeny removes that gap entirely.
  Because the dual isogeny also exists, no floor curve is easier than E0 either: all 263 explicit curves are equivalent up to
  a transport costing ~2^15.6 field multiplications.
- **The p and 263p levels are the only place where hardness genuinely differs**, and only conditionally. Classical transport
  (kernel points over F_{q^r} with r ≈ 2^53.4, Φ_p, CM) is infeasible. Galbraith (Res. Number Theory 2025, ePrint 2024/924)
  gives an Õ(√p) ≈ 2^28.5 Kani-type reduction, but as proved it is dimension 8, which lands at ≥ 2^72 (worse than native rho).
  Only an unimplemented, unproved dimension-2 or dimension-4 characteristic-2 variant would bring these levels down to about
  60.9–62.0. Separately, **building even one such curve costs about 2^70–2^71.3 F_q-mults (~2^7–2^8 E0 rho solves)**,
  so no ECDLP instance can feasibly sit on these levels.

## 2. Ground truth (derived twice, independently)

- Build: class polynomial H_{−7·263²} (PARI polclass), squarefree mod 2, two irreducible factors of degree 131, 262 roots in
  F_q; all 263 curves point-counted in both twists (a2 = 0 is the order-4N twist on all 263) plus point-order proofs.
- Independent derivation: Vélu isogenies from a basis of E0[263] over F_{q²} (no H_D, no Φ_263). **262/262 j-invariants
  match, 0 extra on either side.** PARI polmodular(263) confirms Φ_263(1, Y) ≡ (Y + 1)² · H_D(Y) mod 2.
- Codex labels, j/b values and the H_D coefficient hash match exactly (4 independent confirmations).

Constants: t = −22283658519494248867; #E = 4N, N = 680564733841876926932320129493409985129 (prime, Pocklington and
Morrison proofs); t² − 4q = −7f²; class numbers h = 1, 262, p + 1, 262(p + 1) for conductors 1, 263, p, 263p.

## 3. Attack vectors, per curve

Status column: result of the adversarial verification (recompute with independent code + audit of the original).

| Vector | Result on all 263 explicit curves | Effect | Verification |
|---|---|---|---|
| Group order / Pohlig–Hellman | #E = 4N on 263/263; E(F_q) ≅ Z/4N cyclic (2-part Z/4, never Z/2×Z/2) | 0 bits (N prime) | confirmed ×2 (C1–C3), C4 confirmed by recompute |
| Endomorphism ring | End(E0) = O_K; End(floor) = O_263 on 262/262 by ≥ 3 criteria (H_D root, Vélu to j = 1, Φ_263 root structure, 263-Sylow of E(F_{q²}): cyclic Z/263² on floor, (Z/263)² on E0) | defines the levels | confirmed ×2 (C1, C2, C3, C5); C4 by G1 |
| MOV / Frey–Rück | k = ord_N(q) = 216464610000596986937760855436835237 (118 bits), identical on every curve by Tate's theorem | 0 bits | confirmed ×2 |
| Anomalous / supersingular | not applicable anywhere in the class (char 2, N ≠ 2, ordinary) | 0 bits | confirmed ×2 |
| Pairings on 263-torsion | t_263(P, Q_N) = 1 on every curve: blind to the N-part | 0 bits | confirmed (recompute + G6) |
| GHS / Weil descent | magic number m = 1 (E0: the "cover" is E0/F_2, order 4, kills the N-part) or m = 131 (all 262 floor curves; genus 2^130). 131 prime ⇒ F_2 is the only subfield | 0 bits | re-verified on all 263 by G2 |
| Rho automorphisms / endomorphisms | Aut = {±1}; E0 adds τ (eigenvalue of order 131 mod N). On the floor, any endomorphism whose eigenvalue has order < 2^20 (swept exactly to 2^32) has degree ≥ 2^114.6; Codex's ψ = (11-isogeny)∘Frob^16 has eigenvalue order (N−1)/3 | E0 class 262; floor class 2 | re-verified with independent code by G1 |
| Isogeny transport (floor → E0) | unique rational 263-isogeny built for 262/262; codomain j = 1; planted-scalar homomorphism checks pass; dual composition = −[263]; three implementations agree | floor effective = 60.81 | 9 confirmed, 1 partially (cost wording) |
| Index calculus (summation polynomials) | rational-x densities of all 263 curves look like random curves (effectively 2 samples, one per Frobenius orbit); no method family beats rho, closest non-generic model 23.6 bits slower; Codex's E0 d_reg advantage is a basis-presentation effect (0 bits after minimising over presentations) | 0 bits | 7 confirmed, 3 partially; G3, G5 audits |
| Twist / x-only oracle | leaks ±k mod 526 on E0 (8.04 bits), ±k mod 2·263² on floor curves (16.08 bits); twist rho 2^53.27 (E0 twist, ±τ) / 2^56.79 (floor twists) | attacks unvalidated **implementations** only; ECDLP unchanged | partially confirmed (curve assignment and sign-bit corrected) |
| Batch / multi-instance | L instances pooled: amortised gain 0.5·log₂L − 0.675 bits (3.35 bits at L = 263) | no single DLP gets cheaper than 2^60.81 | partially confirmed |

## 4. Toy-scale end-to-end evidence (DLPs actually solved)

Koblitz analogues over F_{2^n} with a small split prime ℓ dividing the Frobenius conductor, so the volcano has the same
shape. Every recovered log was checked against the planted scalar.

Toy A (Floyd/merge rho, C):

| n | ℓ | N (bits) | floor/E0 iterations | predicted √n | (transport + E0)/E0 |
|---|---|---|---|---|---|
| 11 | 23 | 9.95 | 3.03 ± 0.08 | 3.32 | 0.96 ± 0.02 |
| 19 | 457 | 18.0 | 4.29 ± 0.06 | 4.36 | 1.00 ± 0.01 |
| 23 | 967 | 21.0 | 4.84 ± 0.07 | 4.80 | 1.02 ± 0.02 |
| 59 | 5783 | 33.2 | 7.81 ± 0.12 | 7.68 | 1.00 ± 0.02 |
| 109 | 3271 | 44.8 | 10.72 ± 0.36 | 10.44 | 1.05 ± 0.03 |

Toy B (independent code, r-adding walk with distinguished points), n = 179, N ≈ 2^35.8, ℓ = 359: floor rho 238,989 mean
iterations vs E0 16,381 (ratio 14.6; √179 = 13.4, with the excess from fruitless-cycle handling on the floor); transport + E0
16,056 (ratio 0.98). A second-level analogue (conductor prime 1721) reproduces the "large-conductor level" situation: transport
was 4,800× the rho cost at toy size, so there the level curve is effectively as hard as its native rho.

Totals: 24,300 distinct planted DLPs (52,600 solver runs), all solved and verified.

## 5. The p and 263p levels in detail

- Frobenius acts on E0[p] as the scalar c = t/2 mod p = 65861677189822723, of order r = 12208813656794060 ≈ 2^53.44 = (p − 1)/12.
  So order-p kernel points exist only over F_{q^r} (x-coordinates over F_{q^{r/2}}; one element ≈ 2^59.5 bits).
- Kernel-point route: ≥ 2^111.9 F_q-mults. Φ_p route: Õ(p²) ≈ 2^114. CM with |D| = 7p² ≈ 2^116.9. All infeasible.
- Galbraith 2024/924 ("Climbing and descending tall isogeny volcanos"): Theorem 1 computes an evaluable representation of an
  unknown N-isogeny between two **given** curves in Õ(N^{1/2}), using Kani/Robert embeddings of dimension 4, 6 or 8 (the proof
  uses dimension 8). For N = p that climbs a presented level-p curve to E0 in Õ(2^28.5), but:
  - as proved (dimension 8), the concrete cost is ≥ 2^72 F_q-mults, worse than native rho (break-even ≈ 2^66.5–2^67.2);
  - dimension 2 (not in the paper) and dimension 4 (heuristic) variants model at about 2^52.5–2^55.5 · κ F_q-mults;
  - every published implementation of these isogeny chains assumes odd characteristic, and Theorem 1 uses E[4]/level-2
    theta structures that do not carry over to char 2 directly. A char-2 Kani pipeline (gluing and splitting) does not exist.
- Hence **effective hardness ∈ [60.81, 64.33]**; if the char-2 machinery is built with modest overhead, about 60.9–62.0.
- Construction: no structural shortcut. Generic search needs ~2^64.94 candidates per level-p/263p hit; with free 2-adic
  prefilters (#E mod 16, 32, 64 from low coefficients of b's characteristic polynomial) the best known cost is
  ~2^70.0–2^71.3 F_q-mults, more than solving natively on the curve once found. (The earlier "≥ 2^72.97" was one naive
  strategy, not a lower bound.)

## 6. Red team

44 attack ideas from three angles: 37 self-refuted with computations, 4 "work" only amortised or against flawed
implementations (batch rho, Bernstein–Lange precomputation, x-only twist oracle, cross-curve pooling), 2 plausible (both
the conditional p-level Kani transport of §5), 1 open. Seven were independently verified: 1 confirmed, 12 partially confirmed,
1 refuted (verifier votes). The open one, RT8, asks whether a small-genus non-Artin–Schreier cover of the 130-dimensional
factor of the Weil restriction exists; break-even genus would be ~273–314, cyclic order-131/263 covers are excluded below
genus 525, and no construction is known. It affects no curve's cost today.

## 7. Corrections made along the way (all folded into the tables above)

1. Level 263p has 262(p + 1) ≈ 2^65.06 curves, not ~2^57; p is inert (not split).
2. GHS magic number on the floor is exactly 131, not "130 or 131".
3. Transport from p-levels is not "infeasible by known methods" (refuted); it is conditional (§5).
4. x-only twist leak on E0 is ±k mod 2·263 (not 2·263²); twist rho 53.27 is E0's twist, 56.79 the floor twists'; subtract 1 bit for the sign.
5. Transport evaluation is 788 additions (not 787); 2^15.59 is the maximum of 262 measurements, full rebuild ≈ 2^16.19.
6. Batching gains were overstated: 0.5·log₂L − 0.675 bits with independent bases.
7. Rho-endomorphism element was stated in the wrong basis (numbers unchanged).
8. The p-level construction cost is a best-known 2^70.0–2^71.3, not a 2^72.97 lower bound.
9. "Menezes–Qu–Teske" isogeny-walk reference in the prompt was wrong; the relevant work is Galbraith–Hess–Smart and Hess.

## 8. Relation to the Codex investigation

Codex's numbers are correct (0 mismatches across 263 curves) and its "no advantage from descending" verdict stands, but its
per-descendant signals are artefacts: the 262 descendants are two curves up to coordinate Frobenius; Run-08's best ratios are
a winner's curse; the E0 d_reg 8 vs 10–11 gap comes from b = 1 being short in the polynomial basis; B067's +20.7% is a
selection effect reproducible on E0's own subspaces; Run-13 counts targets in the whole group rather than the order-N subgroup
(3.68–4.08× overstatement). Full review: `../codex-review/REVIEW.md`.

## 9. Coverage and residual uncertainty

- Adversarial verification: first workflow 60 sweep claims × 2 verifiers; 67 verdicts returned (54 confirmed, 12 partially,
  1 refuted), 53 lost to the session limit. Backfill: gap agents G1 (rho endomorphisms), G2 (GHS), G4 (literature/levels),
  G6 (48,220 cross-sweep comparisons, 12 errata), then a second workflow re-ran 22 verifiers + 3 p-level crux agents:
  **all group-order, endomorphism-ring and pairing claims confirmed** except group-order C5 (partially: corrections 4 above).
  Two audits (group-order C4, C5) were lost to the weekly limit; both claims have confirming recomputes.
- Not established: whether a char-2 dimension-2/4 Kani isogeny pipeline can be built (decides where in [60.81, 64.33] the
  p-levels sit); the RT8 cover question. Neither affects any curve anyone can write down today.
- Index-calculus statements rest on extrapolation from small parameters (as all such statements do for n = 131); the margin
  to rho is ≥ 23.6 bits for the tightest non-generic model.

## 10. Files

- `report/per_curve_hardness.csv`: 263 rows × 19 columns (level, j, b, order, structure, End certificate, embedding degree,
  GHS magic number, rho class size, intrinsic/effective rho, transport cost, IC density z-score, notes); 0 empty cells.
- `report/hardness_by_level.csv`, `report/claims_ledger.json`, `report/verify2_results.json`, `report/synthesis_return.md`.
- Ground truth: `ground_truth/` (build script, `ground_truth.json`, `ecc2k.py` loader) and `ground_truth_check/`.
- Sweeps: `group-order/`, `endomorphism-ring/`, `pairing-transfer/`, `weil-descent-ghs/`, `rho-endomorphisms/`,
  `transport-263/`, `p-levels/`, `index-calculus/`, `toy-a/`, `toy-b/`, `codex-crosscheck/`, `literature/`.
- Verification: `verify/`, `verify2/` (incl. `verify2/p-levels-crux-*`), `gaps/G1…G6/`, `redteam-{0,1,2}/`.
- Reproduce ground truth: `cd ground_truth && TMPDIR=../tmp sage -python build_ground_truth.py` (~61 s).
