# ECDLP Attack Taxonomy & Applicability Matrix

A comprehensive map of every known attack on elliptic-curve cryptography,
cross-referenced with where each one is implemented in this repository.
The matrix is calibrated to **what an attacker can actually do to a curve**
— not speculative weaknesses.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✗ Breaks | Attack solves ECDLP / extracts the key in time below the curve's nominal security level. |
| ◐ Partial | Attack works but only at the cost of generic ECDLP (Pollard rho); not a speedup. |
| ◌ Impl-dep | Attack works **iff the implementation is broken**.  A correct implementation is immune. |
| ○ N/A | Attack does **not** apply by construction — the precondition fails on this curve class. |
| 🛡 Implemented | This repository contains a working PoC / demo of the attack. |

---

## The diagram (attack taxonomy tree)

```
                      ┌────────────────────────────────────────────────────────┐
                      │                ECDLP attack surface                    │
                      │  "Given Q = xG on E(F_p), recover the secret scalar x" │
                      └──────────────────────────┬─────────────────────────────┘
                                                 │
        ┌────────────────────────┬───────────────┴────────────────┬─────────────────────────┐
        │                        │                                │                         │
        ▼                        ▼                                ▼                         ▼
  ┌──────────┐         ┌──────────────────┐           ┌─────────────────────┐         ┌────────────┐
  │ Generic  │         │   Mathematical / │           │   Implementation /  │         │  Quantum   │
  │ (group-  │         │   structural     │           │   protocol-layer    │         │            │
  │ theoretic)│        │                  │           │                     │         │            │
  └────┬─────┘         └────────┬─────────┘           └──────────┬──────────┘         └─────┬──────┘
       │                        │                                │                          │
       │  Pollard rho           │ Smart-Semaev-Satoh-Araki       │ Invalid-curve attack     │ Shor 1994
       │  Baby-step/giant-step  │   (anomalous curves)           │ Twist attack             │ Proos-Zalka 2003
       │  Pohlig-Hellman        │ MOV / Frey-Rück                │ Small-subgroup attack    │ Roetteler-Naehrig-
       │  GLV/GLS endomorphism  │   (low embedding degree)       │ Fault injection (RowH)   │   Svore-Lauter 2017
       │                        │ Weil descent /                 │ Differential power       │ Häner-Jaques-
       │                        │   Gaudry-Hess-Smart            │ Cache-timing             │   Naehrig-Roetteler
       │                        │ Index calculus /               │ Incomplete-formula       │   -Soeken 2020
       │                        │   summation polynomials        │   edge cases             │ Babbush-Zalcman-
       │                        │   (Semaev / FPPR / PQ / PKM)   │ ECDSA nonce reuse        │   Gidney 2025
       │                        │ Diem on E(F_{p^k})             │ Biased / partial nonce   │ Kim-Jang et al. 2026
       │                        │ Trace-zero variety             │  (HNP, multi-key HNP)    │   ("Minutes" paper)
       │                        │ Special-prime SNFS-style       │
       │                        │  trapdoor (Fried-Gaudry-       │
       │                        │  Heninger-Thomé 2017)          │
```

---

## The applicability matrix

| # | Attack | Class | Prime-order curve (P-256, SM2, secp256k1) | Twist (with bad twist-order) | Anomalous curve | Binary / extension-field curve | Pairing-friendly curve | Repo path |
|---|--------|-------|:--:|:--:|:--:|:--:|:--:|---|
| 1 | **Pollard rho** | generic | ◐ Partial *(this IS the security bound)* | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | 🛡 `cryptanalysis/pollard_rho.rs`<br>🛡 `cryptanalysis/ec_index_calculus.rs::pollard_rho_ecdlp` |
| 2 | **Baby-step / giant-step** | generic | ◐ √n time, √n memory | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | (folded into `pollard_rho.rs`) |
| 3 | **Pohlig-Hellman** | generic | ○ N/A *(prime order)* | ✗ Breaks *(if cofactor has small factors)* | ○ N/A | ◐ Partial | ◐ Partial | 🛡 logic re-used by IC linear-algebra step |
| 4 | **Preprocessed / table rho** | generic | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | 🛡 `cryptanalysis/preprocessing_rho.rs` |
| 5 | **Automorphism-folded rho** (GLV/GLS speedup) | generic | ◐ Partial *(√2 speedup on secp256k1)* | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | 🛡 `cryptanalysis/aut_folded_rho.rs` |
| 6 | **ML-augmented rho walks** | generic | ◐ Partial *(small constant gain)* | ◐ Partial | ◐ Partial | ◐ Partial | ◐ Partial | 🛡 `cryptanalysis/ml_rho_walks.rs` |
| 7 | **Smart-Semaev-Satoh-Araki** *(anomalous curves)* | structural | ○ N/A *(curve order ≠ p)* | ○ N/A | ✗ Breaks *(polynomial time)* | ○ N/A | ○ N/A | 🛡 `cryptanalysis/canonical_lift.rs::smart_attack_anomalous` |
| 8 | **MOV / Frey-Rück** *(low embedding degree)* | structural | ○ N/A *(P-256 embedding degree astronomical)* | ○ N/A | ○ N/A | ○ N/A | ✗ Breaks *(transfers to F_{p^k}\*)* | (target group attacks via `bls12_381/`) |
| 9 | **Weil descent / Gaudry-Hess-Smart** | structural | ○ N/A *(no extension structure)* | ○ N/A | ○ N/A | ✗ Breaks *(on F_{2^n}, n composite)* | partially applicable | (binary_ecc — vulnerable curves not deployed) |
| 10 | **Index calculus / Semaev summation polys** (Semaev 2004, FPPR 2012, PQ 2012, PKM 2016) | structural | ◐ Asymptotically O(p^{3/2}) for 2-decomp; worse than rho | ◐ Same | ◐ Same | ✗ Breaks *(via Weil descent)* | ◐ Same | 🛡 `cryptanalysis/ec_index_calculus.rs` (full pipeline: S₃, S₄, factor base, relations, GE, end-to-end solver)<br>🛡 `cryptanalysis/prime_orbit_index_calculus.rs` (by curve type: automorphism-orbit factor bases for generic, `j = 0` and `j = 1728`; `ca-ic prime`) |
| 10a | **Residual-collision hybrids** (partial decompositions + large-prime cancellation, r-adding residual walks, MITM 4-decompositions) | structural/generic | ◐ Partial *(measured √(2nB) ≥ rho; no non-generic gain)* | ◐ Same | ◐ Same | ◐ Same | ◐ Same | 🛡 `cryptanalysis/residual_walk.rs` ([upstream note](https://github.com/aburan28/crypto/blob/main/research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md)) |
| 10b | **Gaudry index calculus on E(F_{q^k}), subspace base** (Gaudry 2009; k = 3 toy) | structural | ○ N/A *(prime field)* | ○ N/A | ○ N/A | ✗ Breaks asymptotically for fixed k ≥ 3 *(measured: MITM oracle ∝ n^{2/3}; the O(1) S₄ solve costs C₃ ≈ 0.88·10⁶ F_p mults per residual after two optimisation rounds, three orders of magnitude above the rho crossover at these sizes; relation phase n^{1/3}, plain linear algebra n^{0.68} so S bottoms out near 200× rho, double-large-prime variation measured at n^{4/9} with the crossover past 2^230)* | ○ N/A | 🛡 `cryptanalysis/gaudry_cubic.rs` ([upstream note](https://github.com/aburan28/crypto/blob/main/research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md) §11) |
| 11 | **Diem on E(F_{p^k})** *(small composite k)* | structural | ○ N/A | ○ N/A | ○ N/A | ✗ Breaks *(faster than rho)* | ○ N/A | (documented; not implemented) |
| 12 | **Trace-zero variety / Weil restriction (genus ≥ 3)** | structural | ○ N/A *(genus 1)* | ○ N/A | ○ N/A | partial | partial | (documented; not implemented) |
| 13 | **Special-prime SNFS trapdoor** (Fried-Gaudry-Heninger-Thomé 2017) | structural / speculative | ◌ Impl-dep on curve generator *(no known ECDLP analog of F_p\* result)* | ◌ Same | ◌ Same | ○ N/A | ◌ Same | (Solinas-prime correlation study in `cryptanalysis/solinas_correlations.rs`) |
| 14 | **Invalid-curve attack** | implementation | ◌ Impl-dep *(needs missing point validation)* | ✗ Breaks *(if no validation)* | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via `ecc::is_on_curve`) |
| 15 | **Twist attack** *(small-subgroup on quadratic twist)* | implementation | ✗ Breaks *(if no validation AND bad twist)*<br>e.g. brainpoolP256t1: 2⁴⁴·⁵<br>P-224: 2⁵⁸·⁴<br>FRP256v1: 2⁷⁹·⁴ | ✗ Breaks | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via `is_on_curve`) |
| 16 | **Small-subgroup attack** *(on main curve, h > 1)* | implementation | ○ N/A *(P-256/secp256k1 have h=1)* | ✗ Breaks | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via cofactor multiplication) |
| 17 | **Fault injection** (RowHammer, voltage glitch) | implementation | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (out of scope) |
| 18 | **Differential power analysis (DPA)** | implementation | ◌ Impl-dep *(mitigated by scalar blinding)* | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via `ecc/ct.rs::scalar_mul_secret_blinded` — Coron 1999 randomisation) |
| 19 | **Cache-timing / Spectre / FLUSH+RELOAD** | implementation | ◌ Impl-dep *(needs constant-time scalar mul)* | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via `ecc/ct.rs` Montgomery ladder) |
| 20 | **Incomplete-formula edge case** | implementation | ◌ Impl-dep *(P=Q vs P≠Q timing-distinguishable)* | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | ◌ Impl-dep | (defended via Renes-Costello-Batina complete formulas in `ecc/secp256k1_point.rs`, `ecc/p256_point.rs`) |
| 21 | **ECDSA nonce reuse** | protocol | ✗ Breaks *(linear; Sony PS3, Bitcoin drains)* | ✗ Breaks | ✗ Breaks | ✗ Breaks | ✗ Breaks | (defended via RFC 6979 deterministic k in `ecc/ecdsa.rs::sign_hash`) |
| 22 | **ECDSA biased / partial-nonce HNP** (Howgrave-Graham-Smart, Nguyen-Shparlinski) | protocol | ✗ Breaks *(LLL/BKZ on biased lattice)* | ✗ Breaks | ✗ Breaks | ✗ Breaks | ✗ Breaks | 🛡 `cryptanalysis/hnp_ecdsa.rs`<br>🛡 `cryptanalysis/multi_key_hnp.rs` |
| 23 | **ECDSA audit / corpus analysis** | protocol | ✗ Detects-and-recovers *(if biased nonces in transcript)* | ✗ Same | ✗ Same | ✗ Same | ✗ Same | 🛡 `cryptanalysis/ecdsa_audit.rs`<br>🛡 `cryptanalysis/signature_corpus.rs` |
| 24 | **Bleichenbacher's bias attack** | protocol | ✗ Breaks *(if nonces are non-uniform mod n)* | ✗ Same | ✗ Same | ✗ Same | ✗ Same | 🛡 `cryptanalysis/bleichenbacher.rs` |
| 25 | **Shor's algorithm** (Shor 1994, Proos-Zalka 2003) | quantum | ✗ Breaks *(polynomial-time on CRQC)* | ✗ Breaks | ✗ Breaks | ✗ Breaks | ✗ Breaks | 🛡 `cryptanalysis/shor.rs` (educational classical simulation of order-finding) |
| 26 | **Babbush-Zalcman-Gidney 2025 / Kim-Jang 2026** (concrete Shor resource estimates) | quantum | ✗ Breaks at ~256 bits / few-min wall-clock on CRQC | ✗ Same | ✗ Same | ✗ Same | ✗ Same | 🛡 `cryptanalysis/quantum_estimator.rs` (cost-model framework) |

---

## What the matrix tells you

### The two columns that matter

**"Prime-order curve" column** is the column that answers "what happens if you deploy properly?" The answer is overwhelmingly ○ N/A or ◌ Impl-dep: structural attacks don't apply, implementation attacks only bite buggy code. This is **the entire reason ECC works in production**.

**"Twist" column** is the column that answers "what happens if you forget input validation?" Many cells become ✗ Breaks. The defensive answer is one of:
1. *Always* validate input points (`is_on_curve` check before scalar mul).
2. Pick a curve whose twist is also secure (Curve25519, Curve448 — the "SafeCurves" property).

### Generic vs structural vs implementation

- **Generic attacks** (rho, BSGS, Pohlig-Hellman) are the **floor of security**. A 256-bit curve has 128-bit security because rho costs 2¹²⁸ ops. These never disappear; they define the security level.
- **Structural attacks** require specific algebraic pathologies. Anomalous curve order, low embedding degree, composite-extension field, hidden Weil descent. **None apply to deployed prime-order curves.** This is the math working in your favour.
- **Implementation / protocol attacks** are where every real-world break has happened (Sony PS3, OpenSSL ECDSA recovery, Minerva, Bitcoin wallet drains). They're orthogonal to the curve and respond to engineering hygiene.

### Shor

The bottom row is the only one that breaks a properly-deployed, properly-implemented, modern prime-field curve. Everything above it has a mitigation (better curve, better code, better protocol). Shor doesn't. That's the asymmetry driving PQC migration.

---

## Index calculus in this repository

The index-calculus column above corresponds to the most-active live research program against ECDLP. It is implemented in this repo as of commit `8b05099` at `src/cryptanalysis/ec_index_calculus.rs`. Specifically:

| Component | Function / type | Reference |
|-----------|-----------------|-----------|
| Semaev 3rd summation poly (closed form) | `semaev_s3`, `semaev_s3_in_x3` | Semaev 2004, ePrint 2004/031 |
| Semaev 4th summation poly (via 2-quadratic resultant) | `semaev_s4_in_x4` | Semaev 2004 §3 recursive definition |
| Modular square root (general Tonelli–Shanks) | `sqrt_mod_p` | classical |
| Small-x-coordinate factor base | `build_factor_base`, `FactorBaseEntry` | FPPR Eurocrypt 2012 |
| Relation finding via S₃ + sign determination | `find_one_relation`, `Relation` | Petit-Quisquater Asiacrypt 2012 |
| Sparse linear algebra mod n (prime) | `gaussian_eliminate_mod_n` | classical |
| End-to-end ECDLP solver | `ec_index_calculus_dlp` | Petit-Kosters-Messeng PKC 2016 (adapted) |
| Pollard rho ECDLP baseline (for comparison) | `pollard_rho_ecdlp` | Pollard 1978; Teske 1998 3-adding walk; Floyd cycle detection |

### Empirical result

On the test curve `y² = x³ + x + 19 (mod 271)` with prime order `n = 281`,
**both algorithms recover the same random discrete log** (test
`ic_and_rho_agree_on_random_dlp`). Rho terminates in ≈ √(πn/2) ≈ 21 group
operations; IC requires ~thousands of trials × ~16 relations. The gap is
**exactly what the published research predicts**: 2-decomposition IC on
prime-field curves is asymptotically `O(p^{3/2})`, strictly worse than rho's
`O(p^{1/2})`. **This is the good news for prime-curve security.**

### By curve type: `ca-ic prime`

`cryptanalysis/prime_orbit_index_calculus.rs` runs the pipeline on prime-field
curves by type, over certified scaled-down curves of a deployed curve's shape
(`y² = x³ + 7` for secp256k1, `a = −3` for the NIST curves). Its factor base is
a union of whole automorphism orbits — `{±1}` on generic curves, `μ₆` from the
GLV endomorphism on `j = 0` curves, `μ₄` on `j = 1728` curves — so `w·m` points
carry `m` unknowns. That is the prime-field analogue of the Frobenius collapse
the binary Koblitz pipeline uses; `ec_index_calculus_j0` keeps orbit
representatives but accepts only decompositions through them, so there the
automorphism adds no relation coverage. Measured at 28 bits: the logarithm
precomputation is `≈ 2.2·r/|Aut|` operations for every type, a descent with
the database paid beats per-target rho (from width 4 even the folded-rho
expectation), and the whole process still costs 37–360× what rho does over
32–64 targets. The
secp256k1 structure — `|Aut| = 6`, the GLV `λ`, `S₃`'s `ζ`-equivariance — is
computed on the real curve; see [ic/README.md](ic/README.md#prime-field-curves-ic-prime).

### What would change the picture

To make IC beat rho on prime fields requires:
1. Using S_n for n ≥ 4 (decompose `R = ε₁F₁ + ⋯ + ε_{n-1}F_{n-1}`).
2. Solving the resulting `(n-1)`-variate polynomial system over `F_p` — this is where Gröbner-basis cost blows up.
3. A heuristic ("first fall degree assumption" — Petit-Quisquater 2012) that bounds the GB cost; if it holds, IC becomes subexponential.

The current state of the heuristic, per Galbraith 2015 "Notes on summation polynomials" and Huang-Kiltz-Petit Crypto 2015: **doesn't hold uniformly**. Counterexamples exist. So the optimistic-subexponential-complexity claim is not currently believed, even for binary curves. For prime curves the situation is worse for the attacker (no Weil descent).

---

## Country-by-country curve risk picture

Cross-referencing the matrix against the international curve zoo in this
repository (`src/ecc/curve_zoo.rs`):

| Curve | Country / Standard | Worst applicable row | Severity |
|-------|--------------------|----------------------|----------|
| secp256k1 | SECG / Bitcoin | #15 twist attack | ◌ Impl-dep, twist work factor 2¹⁰⁹·⁵ — passes SafeCurves |
| P-256 (NIST) | NIST / NIST | #13 special-prime trapdoor *(speculative)*, #15 twist 2¹²⁰ | ◌ Impl-dep + speculative rigidity |
| P-224 (NIST) | NIST / NIST | #15 twist attack 2⁵⁸·⁴ | **✗ Breaks** if validation skipped |
| P-384 / P-521 (NIST) | NIST | #15 twist 2¹⁹¹·⁸ / 2²²¹·⁸ | ◌ Impl-dep but high margin |
| brainpoolP256r1 / t1 | BSI / RFC 5639 | #15 twist 2⁴⁴·⁵ on t1 | **✗ Breaks** on twisted variant if validation skipped |
| brainpoolP384r1 / t1 | BSI | #15 twist 2¹¹⁸·⁵ | ◌ Impl-dep, narrow margin |
| FRP256v1 | French ANSSI | #15 twist 2⁷⁹·⁴ + #13 rigidity | ◌ Impl-dep + speculative |
| SM2 | Chinese OSCCA | #13 rigidity *(no published derivation)* | ◌ Impl-dep + speculative |
| GOST CryptoPro A/B/C | Russian TC26 | #13 rigidity *(no published derivation for the 2001-era curves)* | ◌ Impl-dep + speculative |
| GOST tc26-512 paramSetA/B | Russian TC26 | #13 rigidity (partial; paramSetC has published seeds) | ◌ Impl-dep + speculative |
| Curve25519 / Curve448 | Bernstein / RFC 7748 | none (twist-secure by design) | passes every SafeCurves row |
| BN254 / alt_bn128 | Brazilian / Ethereum | #8 MOV-style via Kim-Barbulescu 2016 → ~110 bit | **✗ Below 128-bit pairing security**; migration to BLS12-381 advised |
| BLS12-381 | Swiss-academic / Ethereum-2 | #8 future Tower-NFS erosion | ◐ ~120-bit margin holding for now |

---

## Defensive checklist for ECC deployment

Distilled from the matrix. If every box is checked, attacks rows 14–24 are
closed regardless of which curve you picked.

- [ ] Validate every input point: `y² ≡ x³ + ax + b (mod p)` AND ord(P) = n.
- [ ] Reject the point at infinity unless protocol explicitly allows it.
- [ ] Constant-time scalar multiplication (Montgomery ladder / RCB complete-addition projective ladder).
- [ ] Scalar blinding (Coron 1999): k' = k + r·n for fresh 64-bit r.
- [ ] Point blinding: P' = P + R, computed via random R = sG.
- [ ] Deterministic nonces (RFC 6979) — eliminates rows 21–24 entirely.
- [ ] If FIPS-restricted to NIST curves: use a hardened library (BoringSSL / ring / OpenSSL ≥ 3.0). Don't roll your own P-256.
- [ ] If unrestricted: prefer X25519 / Ed25519. The matrix is shortest for them.
- [ ] Plan PQC migration. Row #25 has no implementation defence.

---

*Sources: SafeCurves (safecurves.cr.yp.to), Galbraith *Mathematics of Public Key Cryptography*, Hankerson-Menezes-Vanstone *Guide to Elliptic Curve Cryptography*, RFC 5639, RFC 7748, FIPS 186-4, GB/T 32918, GOST R 34.10-2012, Babbush et al. 2025, Kim-Jang et al. 2026.*
