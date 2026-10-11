#!/usr/bin/env python3
"""Claims ledger: every sweep claim, its adversarial verdicts (recompute + audit),
the gap-fill re-verification, and the red-team idea verdicts, with verdict counts.

Verdict strings are transcribed from the verify agents' structured outputs as relayed
to the synthesis step (they are not stored as verdict files on disk; the verify/
directories hold the evidence).  'null' = the verify step returned no verdict.
Writes report/claims_ledger.json.
"""
import json, os
from collections import Counter

OUT = "/Volumes/SSD990/ecdlp-hardness-work/report/claims_ledger.json"

C, P, R, U = "confirmed", "partially_confirmed", "refuted", None

sweeps = {
 "group-order": [
  ("C1", "pure-python 2-adic AGM gives t for all 263 curves, #E = 4N", U, U, "no verify step ran; reproduced by ground_truth (PARI + point proofs), codex-crosscheck C1 (#E=4N 263/263), G6 crosscheck"),
  ("C2", "E(F_q) = Z/4 x Z/N cyclic, 2-part Z/4 on all 263", U, U, "not audited; consistent with G2 halving rule (8 | #E iff Tr(b)=0) and G6"),
  ("C3", "N, p, 263, P114 prime (Pratt certificates)", U, U, "not audited; N, p proved independently in ground_truth (ECPP / BPSW<2^64), G6 nt_checks, pairing-transfer C1 recompute (Lucas/Pratt)"),
  ("C4", "twists: q+1+t = 2*263^2*P114; E0' has (Z/263)^2, floor twists cyclic", U, U, "not audited as such; reproduced by codex-crosscheck C3 (own + PARI twist counts 1/262) and pairing-transfer C4 audit files"),
  ("C5", "Pohlig-Hellman gain 0; rho 60.81 / 64.33; twist rho 56.79 / 53.27", U, U, "CORRECTION (ERR-02, RT0-8 audits): an E0 x-only twist oracle leaks k mod 2*263 (9.04 bits), not k mod 2*263^2 (17.08 bits), because E0' is not cyclic; 17.08 bits is right only for floor twists"),
 ],
 "endomorphism-ring": [
  ("C1", "End(E0) = O_K, End(floor) = O_263 on all 263 (4 / 3 certificates each)", U, U, "no verify step ran; conductor evidence reproduced by codex-crosscheck C3 (Phi_263 root counts, 263-structure), transport-263 C3, ground_truth_check"),
  ("C2", "263-part of E(F_{q^2}): cyclic Z/263^2 on floor, (Z/263)^2 on E0", U, U, "reproduced by codex-crosscheck C3 recompute/audit (all 263) and pairing-transfer C3 recompute"),
  ("C3", "p inert; h = 1, 262, p+1, 262(p+1); '~2^57 classes for 263p' in shared context is wrong", U, U, "reproduced by p-levels C2 recompute+audit, G4, G6 and this build script"),
  ("C4", "tau^k not in O_263 for 0<k<131; min non-scalar degree 121046", U, U, "confirmed by G1 (d): 263 | b_k only at k=131, minimum 121046 at 131+263tau and 132+263tau, PARI qfminim agrees"),
  ("C5", "Phi_263(j,Y) mod 2 has one F_q root (Y=1) on every floor curve; 264 on E0", U, U, "reproduced by codex-crosscheck C3 recompute (262/262, cofactor irreducible on 8 curves); irreducibility carries to all 262 by Frobenius conjugacy"),
 ],
 "pairing-transfer": [
  ("C1", "k = ord_N(q) = 216464610000596986937760855436835237 (118 bits, log2 117.38), (N-1)/k = 3144", C, C, "audit: Sage/PARI checks are not independent (Sage calls PARI); PARI-free recompute agrees"),
  ("C2", "k identical on all 263 curves", C, C, "wording (ERR-06): equality is forced by the input (#E read from ground truth), not measured per curve; true by Tate"),
  ("C3", "t_263(P, Q_N) = 1 on every curve; 263-pairing blind to the N-part", C, U, "audit never ran (t1.gp overflowed, ERR-07); G6 ran its own gp check on E0, A000, B000: confirmed; Tate-matrix determinant is basis-dependent"),
  ("C4", "twist r = P114 prime, ord_r(q) 105-bit, ord_263(q)=1", C, U, "audit files on disk (verify/pairing-transfer/C4-audit, 263/263 per_curve_all_passed) but no verdict returned"),
  ("C5", "anomalous / supersingular attacks do not apply", C, U, "no audit directory"),
 ],
 "weil-descent-ghs": [
  ("C1", "m = 131 on all 262 floor curves, m = 1 on E0; floor GHS genus 2^130, gGHS min 2^130-1", U, U, "no verify step; G2 recomputed independently on all 263: confirmed; ERR-08 label slip (unrealizable (Phi131,x+1) min pair) in raw_magic_numbers.json"),
  ("C2", "class-wide: Tr(b)=1 forced, so every curve except E0 has m = 131 (incl. levels p, 263p)", U, U, "G2: halving rule held on 50/50 random curves; argument confirmed"),
  ("C3", "the task premise 'm = 130 or 131' is wrong; m = 131 for all b outside F_2", U, U, "G2 confirmed"),
  ("C4", "E0's m=1 cover is E0/F_2 (order 4) and kills the N-subgroup", U, U, "G2 confirmed (5 points, own arithmetic and Sage)"),
  ("C5", "Res(E) ~ E0/F_2 x A, A simple of dim 130, A(1) = N; any N-carrying cover has genus >= 130", U, U, "G2 confirmed (A irreducible, computed two ways); Hess Thm 2 bound 2^128+1 holds only under its hypotheses"),
 ],
 "rho-endomorphisms": [
  ("C1", "floor: eigenvalue order in [3, 2^20) needs degree >= 2^114.62 (min at order 315337)", U, U, "G1 confirmed with two new CVP codes; the quoted element is in basis (1, omega_263), not (1, 263 tau); read literally it has norm 2^115.157"),
  ("C2", "E0: tau eigenvalue order 131, classes of 262, 2^60.809; only +-tau^k below 2^100", U, U, "G1 confirmed (200 elements; best other 2^106.96)"),
  ("C3", "Codex psi acts as +-(774+omega_263), eigenvalue order (N-1)/3", U, U, "G1 confirmed (norm 2^16*11)"),
  ("C4", "Aut = {+-1}; tau^k not in O_263 for k <= 130; no endomorphism of small eigenvalue order", U, U, "G1 confirmed; extended exact sweep to orders 2^20..2^32: min degree 2^103.25 (O_263), 2^95.91 (O_K)"),
  ("C5", "Frobenius-orbit union classes give no reduction (2^64.33)", U, U, "not separately re-verified; consistent with toy-analogue-a/b measurements"),
 ],
 "transport-263": [
  ("C1", "ascending 263-isogeny lands on E0 for all 262; 3 implementations agree", C, C, "audit: 3 implementations are not 3 independent confirmations of the codomain (all use sum x_Q); kernel validity from Sage check=True + subgroup checks"),
  ("C2", "planted-scalar check and toy DLP transport pass on all 262", C, C, "order_4N_preserved flag was vacuous on some curves (A001, A010, A130 in replay); re-proved non-vacuously 262/262"),
  ("C3", "kernel = unique F_q-rational 263-subgroup, two derivations agree", C, C, "the two routes compute the same group; uniqueness proved by char poly (X+1)^2 + cyclic twist Sylow and by 263-division polynomial (A000, B000, B077)"),
  ("C4", "transport cost <= 2^15.59 F_q-mult; effective = 60.8090365640 + <=3.8e-12 bits", C, P, "CORRECTED: eval adds 788 not 787; build ranges 317-323 I, 633-639 M, 831-1617 S; 2^15.59 is a sample max not a bound (expected 2^15.55, full rebuild ~2^16.19); increment ~4e-14 bits with op counts; BBB09 walk 2^60.907"),
  ("C5", "Frobenius conjugation of kernels: one kernel per orbit suffices", C, C, "two kernels total (A000, B000); 131 squarings per step"),
 ],
 "p-levels": [
  ("C1", "pi acts on E0[p] as c = t/2 mod p; r = ord(c) = 12208813656794060 (2^53.44); x in F_{q^(r/2)}", C, C, "minimality holds over all F_{2^m}"),
  ("C2", "p inert; h(O_p) = p+1 (2^57.02), h(O_263p) = 262(p+1) (2^65.06); 0 horizontal p-isogenies", C, C, "Cl(O_263p) = Z/262 x Z/(p+1) is not cyclic; qfbclassno is not independent evidence"),
  ("C3", "ascending p-kernel = ker(pi - c), points only over F_{q^r}; kernel poly degree (p-1)/2 splits into 12 factors", C, C, "toy coverage of the r/2 feature was missing in the sweep; audit toys B-F fill it"),
  ("C4", "transport from levels p / 263p to E0 infeasible by known methods; effective 2^64.33", P, R, "REFUTED: Galbraith 2024/924 Thm 2 (h0 = 1) gives a Kani representation of the ascending p-isogeny in O~(p^1/2) with no p-torsion; effective hardness is conditional, in [60.809, 64.326] (G4). Also: cofactor bound 2^111.9 not 2^113.9; Phi_p O~(p^2) ~2^114 not 2^171"),
  ("C5", "no explicit level-p / 263p curve can be built (random search 2^66.94, CM |D| 2^116.85)", C, P, "CORRECTED: prefilter a2=0, Tr(b)=1 gives 2^64.94 candidates = 2^72.97-2^74.30 F_q-mult (2^9.58-2^11.17 E0 rho solves); generic search is a known (too costly) method, so 'impossible' -> 'not at feasible cost'"),
 ],
 "index-calculus": [
  ("C1", "liftable-x density on 4 subspaces x k=8..16 matches the null; floor indistinguishable from random curves", C, P, "CORRECTED: not exactly binomial on the canonical subspace (excess kurtosis); original 4 subspaces showed a tail excess (26 vs 14.3, p=0.005) that did not replicate on 12 + 64 fresh subspaces; effectively 2 curves (orbits), grand-mean z 1.53 not 1.56"),
  ("C2", "Codex Run-08 best-descendant ratios = winner's curse", C, P, "k=10 percentile 0.035-0.040 (E0-conditioned 0.32); canonical-V winners are only 4 curves (B113 wins 5/9, ~2% null tail, post hoc)"),
  ("C3", "descendant choice = subspace choice (C(X_{j+1},V) = C(X_j, sqrt V)) exactly", C, C, "exact only inside an orbit; across orbits the 263-isogeny carries the DLP but not the linear factor base"),
  ("C4", "class-wide Tr(b)=1 (no point of order 8)", C, C, "z-shift is 1/sqrt(2^k-1) only on subspaces containing 1"),
  ("C5", "tau-invariant factor base is E0-only and cannot be built at (2,131)", C, P, "CORRECTED: GGMP 7.03/14.07-bit gains are an idealised ceiling; GGMP sec 3.1 ordered tau-slots ARE realisable on E0 at n=131 (up to m! in relation collection: 2.6/4.6/6.9 bits for m=3/4/5) and transfer to the floor; toy 61 vs 973 is illustration only"),
 ],
 "toy-analogue-a": [
  ("C1", "native floor rho / E0 rho = sqrt(n) (pooled 1.003+-0.008)", C, C, "iteration counts, not wall time; T11 excluded from the pool"),
  ("C2", "transport + E0 rho = native E0 rho (pooled 1.009+-0.008)", P, C, "CORRECTED: 15,200 transported pairs, not 13,200 (ERR-04); the 360 Sage cross-checks are P-image comparisons, not extra log checks (ERR-05)"),
  ("C3", "52,600 planted DLPs solved", P, P, "CORRECTED: 52,600 solver runs over 24,300 distinct planted DLPs (ERR-03); all correct; blind re-solve of 50,800 runs agrees"),
  ("C4", "T59 rho matches sqrt(pi N/(2c)) within ~2%", C, C, "T11 had 12 abandoned walks; DP tail adds 2-4%"),
  ("C5", "all 262 real floor curves: unique rational 263-line, 786/786 planted relations transported", C, C, "sweep's one-line flag was probabilistic; uniqueness now proved"),
 ],
 "toy-analogue-b": [
  ("C1", "n=179 toy: Velu floor = roots of polclass mod 2 (358 curves); 3448 planted DLPs", C, C, "3448 runs over 2074 distinct instances"),
  ("C2", "measured rho work matches theory; gain 14.88 vs sqrt(179) = 13.38", C, P, "CORRECTED: 9.9% excess = 4.9 cycle handling + 1.6 anti-collision + 1.9 DP tail + noise; implementation-specific expected gain 14.15+-0.10; clean class-count gain 13.4-13.6"),
  ("C3", "transport at toy scale costs 3.2% of E0 rho; (iii)/(i) CPU 0.177", P, C, "CORRECTED: percentages and 0.177 are implementation-specific; independent code gives (iii)/(i) 0.22-0.35"),
  ("C4", "l = 2n+1 split: l | f iff l = 7 mod 8, then pi = +-1 scalar mod l", C, C, "E[l] is F_{q^2}-rational for every split l = 2n+1; the scalar property is what l | f adds; checked to n < 10^7"),
  ("C5", "p-kernels over F_{q^k}, k=(p-1)/12; no cheap transport found; 2^64.33 stands", P, C, "CORRECTED: x-coordinates in F_{q^(k/2)} (2^59.47 bits), polmodular exponent ~3.2 not 3.33; 'no cheap route found' is a search result, not a bound (see p-levels C4 refutation)"),
 ],
 "codex-crosscheck": [
  ("C1", "Codex per-curve labels/values match ground truth on all 263 (0 mismatches)", C, C, "tag splits compared per curve only for run-03; A010 k=4 'best' is a 30-way tie"),
  ("C2", "Codex run-05 embedding degree correct and class-invariant", C, C, ""),
  ("C3", "Codex local 263-torsion claims hold on all 263 (Codex tested 4)", C, C, "stable-line counts computed directly via Phi_263"),
  ("C4", "Codex explicit 263- and 11-isogeny artifacts correct; beta*gamma = -11 sign is a convention", C, C, "line ids basis-dependent; c08 checks only Codex's arithmetic"),
  ("C5", "Codex run-13 counts relation images in all of E(F_q), not the N-subgroup (overstates 3.68x / 4.08x)", C, C, "a labelling/definition inconsistency, not an arithmetic bug"),
 ],
 "literature": [
  ("L1", "two blocks B1 = {1,263}, B2 = {p,263p}; no known efficient bridge", U, U, "G4: CORRECTED - Galbraith 2024 Thm 2 bridges B2 -> B1 for a presented curve in O~(p^1/2) (exponential, not polynomial); B1 -> B2 needs >= 2^72.97 F_q-mult"),
  ("L2", "every known vertical p-isogeny method is infeasible", U, U, "G4: REFUTED as stated (Galbraith 2024 Thm 1 needs no kernel data); holds for kernel-point, kernel-polynomial, cofactor and Phi_p routes"),
  ("L3", "all 262 floor curves poly-time equivalent to E0; l=2,11,29 horizontal graph", U, U, "G4: CONFIRMED (0 mismatches for l=2,11,29 over 262 curves)"),
  ("L4", "B2 at least as hard as E0, not provably equivalent; best known 2^64.33", U, U, "G4: CORRECTED - 'at least as hard' holds; B2 -> E0 reduction exists at O~(p^1/2) asymptotically; concrete cost hinges on a char-2 higher-dimensional isogeny implementation"),
  ("L5", "level-independent attacks (MOV, GHS, summation polynomials) show no difference", U, U, "G4: reconstructed as L5a/L5b, CONFIRMED"),
 ],
}

redteam_verified = [
 ("RT0-6", "Kuhn-Struik multi-instance batch over the 263 B1 curves", "works (amortised)", [P, C],
  "no single DLP gets cheaper than 2^60.81; 263 independent instances cost 2^65.50 total (2^57.46 each), shared base 2^65.00; needs an instance-independent walk"),
 ("RT0-7", "Bernstein-Lange precomputation on E0 serving all B1 curves", "works (amortised)", [P, P],
  "precomputation 2^70.8/2^80.8 exceeds one rho; batch rho beats it for known instance sets; per-instance two table logs when bases differ"),
 ("RT0-8", "twist / x-only oracle", "works (implementations only)", [P, P],
  "E0 oracle leaks k mod 2*263 (9.04 bits) not mod 2*263^2; hashed output (ECDH+KDF) kills the P114 part; stopped by an on-curve check; ECDLP unchanged"),
 ("RT8", "small-genus non-Artin-Schreier cover of the 130-dim factor A", "unknown", [R, P],
  "REFUTED numbers: break-even genus ~273-314 (not 249), cost at g=130 ~2^34.5-2^38 (not 2^41) - more room for an attacker; cyclic order-263 and order-131 covers excluded below genus 525; no construction exists; open"),
 ("RT15", "presented level-p / 263p curves transported to E0 (Galbraith 2024)", "plausible", [P, P],
  "conditional: needs a char-2 odd-degree dim-2 (or dim-4) isogeny algorithm; Thm 1 as proved (dim 8) gives no gain; polylog factor ~2^30-2^34; effective ~60.9-61.3 under assumptions"),
 ("RT2-01", "Kani transport of levels p / 263p (dim-2 variant)", "plausible", [P, P],
  "field degrees are lcm not max; compositum costs 2^55.8-2^62.6 per model; dim 4 worst case gives no gain; treat 60.81 as an upper bound on B2 hardness, not a measurement"),
 ("RT2-13", "multi-instance pooling on E0 across curves", "works (amortised)", [P, P],
  "amortised gain 0.5 log2 L - 0.675 bits with independent bases (3.35 bits at L=263, 0.09 at L=2); B2 curves cannot join without RT2-01"),
]

redteam_other = {  # proposer verdict, later check (if any)
 "RT0-1": ("fails", "G1 recomputed: -4.96 to -9.47 bits"),
 "RT0-2": ("fails", ""), "RT0-3": ("fails", ""), "RT0-4": ("fails", ""), "RT0-5": ("fails", ""),
 "RT0-9": ("fails", "G1 partially confirmed: full cost 2^69.68 (memory 2^65.6), better split 2^68.57; still fails"),
 "RT0-10": ("fails", ""), "RT0-11": ("fails", "estimate only"), "RT0-12": ("fails", ""), "RT0-13": ("fails", ""),
 "RT0-14": ("fails", "not recomputed"),
 "RT1-psi-invariant-factor-base": ("fails", ""), "RT2-psi-ordered-slots": ("fails", ""),
 "RT3-tau-union": ("fails", "G3: 2^67.0 optimum is a generic k-sum (BSGS floor), corrected 2^66.58 with 2^65 entries"),
 "RT4-torsion-symmetry": ("fails", ""),
 "RT5-summation-system-b-dependence": ("fails", "G5 at n=131: 0 bits after minimising over presentations"),
 "RT6-first-fall-degree": ("fails", "G3: 2^126.61 -> 2^122.90"),
 "RT7-Semaev-2015": ("fails", "G3: 2^89.33 -> 2^84.44 (+23.6 bits, tightest non-generic margin)"),
 "RT9-extension-descent": ("fails", ""), "RT10-horizontal-path-endos": ("fails", ""),
 "RT11-trace-zero-IC": ("fails", ""), "RT12-genus-2-gluing": ("fails", ""), "RT13-Cheon": ("fails", ""),
 "RT14-floor-specific": ("fails", ""),
 "RT2-02": ("fails", ""), "RT2-03": ("fails", ""), "RT2-04": ("fails", ""), "RT2-05": ("fails", ""),
 "RT2-06": ("fails (implementation-only 2^53.27/2^56.79)", ""), "RT2-07": ("fails", ""), "RT2-08": ("fails", ""),
 "RT2-09": ("fails", "G4: construction >= 2^72.97 F_q-mult"), "RT2-10": ("fails", ""), "RT2-11": ("fails", ""),
 "RT2-12": ("fails", ""), "RT2-14": ("fails", ""), "RT2-15": ("fails", ""),
}

gap_fills = {
 "G1": "rho-endomorphisms re-verified with new code: all confirmed; notation fix for C1's element; RT0-1 confirmed; RT0-9 partially (2^69.68 / 2^68.57); orders 2^20-2^32 swept exactly",
 "G2": "weil-descent-ghs re-verified on all 263: all confirmed; ERR-08 label slip",
 "G3": "index-calculus cost model audited: no family beats rho; RT3 2^67.0 reclassified as generic; tightest non-generic margin +23.6 bits (Semaev 2015, D<=4); m=5,6 PDP budgets cannot be excluded without extrapolating in l",
 "G4": "B2 levels reconciled: effective in [60.809, 64.326]; construction 2^64.94 candidates / >= 2^72.97 F_q-mult; L1 corrected, L2 refuted as stated, L3 confirmed, L4 corrected, L5 confirmed; 26 stale fields listed",
 "G5": "Codex's E0 d_reg 8 vs 10-11 at n=131 reproduced but is a presentation effect; 0-bit difference after minimising over presentations; < 1 bit at realistic l",
 "G6": "48,220 cross-sweep comparisons; only 2 cosmetic disagreement classes (ERR-01, ERR-08); 12 errata; pairing C3 check run",
}

ledger = {"sweeps": {}, "redteam_verified": [], "redteam_unverified": redteam_other, "gap_fills": gap_fills}
cnt = Counter()
per_sweep = {}
for sw, claims in sweeps.items():
    ledger["sweeps"][sw] = []
    c2 = Counter()
    for cid, text, rv, av, note in claims:
        ledger["sweeps"][sw].append({"claim": cid, "text": text, "recompute": rv, "audit": av, "correction_or_note": note})
        for v in (rv, av):
            cnt[str(v)] += 1
            c2[str(v)] += 1
    per_sweep[sw] = dict(c2)
rt = Counter()
for rid, text, prop, vs, note in redteam_verified:
    ledger["redteam_verified"].append({"idea": rid, "text": text, "proposer_verdict": prop, "verifier_verdicts": vs, "note": note})
    for v in vs:
        rt[v] += 1
prop_counts = Counter()
for rid, text, prop, vs, note in redteam_verified:
    prop_counts[prop.split(" ")[0]] += 1
for rid, (prop, _) in redteam_other.items():
    prop_counts[prop.split(" ")[0]] += 1
ledger["counts"] = {
    "sweep_claim_verdict_slots": sum(cnt.values()),
    "sweep_claim_verdicts": dict(cnt),
    "per_sweep": per_sweep,
    "redteam_idea_verifier_verdicts": dict(rt),
    "redteam_ideas_total": len(redteam_verified) + len(redteam_other),
    "redteam_proposer_verdicts": dict(prop_counts),
}
ledger["_provenance"] = ("verdict strings transcribed from the verify agents' structured outputs relayed to the synthesis step; "
                         "evidence files live under verify/<sweep>/<claim>-{recompute,audit}/ and gaps/G1..G6/")
with open(OUT, "w") as fh:
    json.dump(ledger, fh, indent=1)
print(json.dumps(ledger["counts"], indent=1))
