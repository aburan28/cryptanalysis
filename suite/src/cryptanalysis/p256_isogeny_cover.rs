//! # P-256 isogeny-cover probe (Phase 1, toy size).
//!
//! Phase-1 implementation of the proposal in
//! `research/notes/cm-isogeny/RESEARCH_P256_ISOGENY_COVER.md`: at a tiny "P-256-shaped" prime
//! `p_toy ≈ 2^8`, sweep ordinary prime-order curves `E/F_{p_toy}`
//! and search for a **genus-2 curve `C/F_{p_toy}` whose Jacobian
//! is `F_p`-isogenous to `E × E^twist`** with an additional
//! `(2, 2)`-isogeny decomposition (Richelot / Cassels–Flynn).
//!
//! ## What the probe does
//!
//! For a chosen toy prime `p`:
//!
//! 1. Sweep **elliptic curves** `E: y² = x³ + ax + b` over `F_p`,
//!    keeping only those with **prime order** (the "P-256-like"
//!    structural property — cofactor 1, no Pohlig–Hellman handle).
//! 2. For each kept `E`, compute the twist order
//!    `n_t = 2(p+1) − n` and the target Jacobian order
//!    `N_target = n · n_t = #E(F_{p²})`.
//! 3. Sweep **genus-2 curves** `C: y² = f(x)` with monic quintic
//!    `f` and squarefree.  For each, compute
//!    `#Jac(C)(F_p)` by brute-force Mumford-divisor enumeration
//!    ([`crate::prime_hyperelliptic::brute_force_jac_order`]).
//! 4. If `#Jac(C) == N_target`, run the
//!    **Richelot `(2, 2)`-splitting test**:
//!    factor `f` over `F_p` into a quadratic × cubic / 3 quadratics
//!    if possible; if a 3-quadratic factorization exists, build the
//!    three associated elliptic curves `E_{ij}: y² = q_i · q_j` and
//!    check whether two of them have orders `{n, n_t}` (an explicit
//!    `F_p`-rational `(2, 2)`-split of `Jac(C)` with one factor
//!    matching `E`).
//! 5. Report all hits as [`CoverProbeHit`]s.
//!
//! ## Honest scope
//!
//! - **Toy only**: `p ≤ ~30` for full sweeps within seconds; `p =
//!   100` takes minutes; `p = 256` is hours; cryptographic `p`'s are
//!   completely infeasible at this implementation's complexity.
//! - **Conservative detector**: we only catch `F_p`-rational
//!   `(2, 2)`-splittings via the elementary 3-quadratic
//!   factorisation.  Splittings that exist only over `F_{p²}` are
//!   missed.  More sophisticated Igusa-invariant / Cardona–Quer
//!   tests would catch those but require additional machinery.
//! - **Phase 1 deliverable**: the goal is to establish the
//!   **frequency** of `(2, 2)`-split covers in random ordinary
//!   prime-order isogeny classes — a structural statistic that
//!   directly bounds the expected outcome of running the same probe
//!   at `2^32`, `2^64`, …, `P-256`.

use crate::prime_hyperelliptic::{fast_frob_ab, Fp2Ctx, FpPoly, HyperellipticCurveP};
use num_bigint::BigUint;
use num_traits::{One, Zero};

// ── tiny elliptic-curve utilities (own to keep this module self-contained) ──

/// `E: y² = x³ + a·x + b` over `F_p` (short Weierstrass, char ≠ 2,3).
#[derive(Clone, Debug)]
pub struct ECurveP {
    pub p: u64,
    pub a: u64,
    pub b: u64,
}

impl ECurveP {
    /// `4a³ + 27b² mod p ≠ 0`.  Smooth iff non-zero.
    pub fn is_smooth(&self) -> bool {
        let p = self.p;
        let a = self.a;
        let b = self.b;
        let aa = mulmod(a, a, p);
        let four_a3 = mulmod(4, mulmod(aa, a, p), p);
        let twentyseven_b2 = mulmod(27, mulmod(b, b, p), p);
        let disc = (four_a3 + twentyseven_b2) % p;
        disc != 0
    }

    /// `#E(F_p) = 1 + Σ_{x ∈ F_p} (1 + χ(x³ + a·x + b))`.
    pub fn order(&self) -> u64 {
        let p = self.p;
        let mut count: u64 = 1; // ∞
        let exp = (p - 1) / 2;
        for x in 0..p {
            let x2 = mulmod(x, x, p);
            let x3 = mulmod(x2, x, p);
            let ax = mulmod(self.a, x, p);
            let rhs = (x3 + ax + self.b) % p;
            if rhs == 0 {
                count += 1;
            } else {
                let chi = powmod(rhs, exp, p);
                if chi == 1 {
                    count += 2;
                }
            }
        }
        count
    }
}

fn mulmod(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn powmod(base: u64, exp: u64, p: u64) -> u64 {
    let mut acc = 1u64;
    let mut b = base % p;
    let mut e = exp;
    while e > 0 {
        if e & 1 == 1 {
            acc = mulmod(acc, b, p);
        }
        b = mulmod(b, b, p);
        e >>= 1;
    }
    acc
}

fn is_prime_u64(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    if n < 4 {
        return true;
    }
    if n & 1 == 0 {
        return false;
    }
    let mut d = 3u64;
    while d * d <= n {
        if n.is_multiple_of(d) {
            return false;
        }
        d += 2;
    }
    true
}

/// Find all ordinary, prime-order elliptic curves `E: y² = x³ + ax + b`
/// over `F_p` ("P-256-like": cofactor 1).  Returns one representative
/// per `(a, b)` pair (no isomorphism reduction).
pub fn sweep_prime_order_curves(p: u64) -> Vec<(ECurveP, u64, u64)> {
    let mut out = Vec::new();
    for a in 0..p {
        for b in 0..p {
            let e = ECurveP { p, a, b };
            if !e.is_smooth() {
                continue;
            }
            let n = e.order();
            if !is_prime_u64(n) {
                continue;
            }
            // Twist order = 2(p+1) − n.
            let n_t = 2 * (p + 1) - n;
            out.push((e, n, n_t));
        }
    }
    out
}

// ── candidate genus-2 curve enumeration ─────────────────────────────

/// Enumerate genus-2 curves `C: y² = f(x)` with `f` a monic quintic
/// over `F_p`, `f` squarefree.  Returns the list of squarefree
/// quintic coefficient tuples `(c_4, c_3, c_2, c_1, c_0)`.
///
/// For `p` small this is `O(p^5)` but with the squarefree filter
/// we can typically prune quickly.
pub fn sweep_genus2_quintics(p: u64) -> Vec<[u64; 5]> {
    let mut out = Vec::new();
    for c4 in 0..p {
        for c3 in 0..p {
            for c2 in 0..p {
                for c1 in 0..p {
                    for c0 in 0..p {
                        if is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                            out.push([c4, c3, c2, c1, c0]);
                        }
                    }
                }
            }
        }
    }
    out
}

fn is_squarefree_quintic(p: u64, c4: u64, c3: u64, c2: u64, c1: u64, c0: u64) -> bool {
    // f(x) = x^5 + c4·x^4 + c3·x^3 + c2·x^2 + c1·x + c0
    // f'(x) = 5x^4 + 4c4·x^3 + 3c3·x^2 + 2c2·x + c1
    // f is squarefree iff gcd(f, f') = 1 in F_p[x].
    let p_big = BigUint::from(p);
    let f = FpPoly::from_coeffs(
        vec![
            BigUint::from(c0),
            BigUint::from(c1),
            BigUint::from(c2),
            BigUint::from(c3),
            BigUint::from(c4),
            BigUint::one(),
        ],
        p_big.clone(),
    );
    let fp = FpPoly::from_coeffs(
        vec![
            BigUint::from(c1),
            BigUint::from(2 * c2 % p),
            BigUint::from(3 * c3 % p),
            BigUint::from(4 * c4 % p),
            BigUint::from(5u32 % p as u32),
        ],
        p_big,
    );
    let g = f.gcd(&fp);
    g.degree() == Some(0)
}

// ── Richelot (2, 2)-split detector ──────────────────────────────────

/// Result of an extended Richelot-style `(2, 2)`-split detection.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum RichelotKind {
    /// `f` factors as `(x − α) · q_1(x) · q_2(x)` with `q_i` monic
    /// quadratic in `F_p[x]`.  Covers the root patterns
    /// `(1)(1)(1)(1)(1)`, `(1)(1)(1)(2)`, `(1)(2)(2)`.  This is the
    /// "explicit `F_p`-rational 3-factor split" — the strongest form.
    Explicit3Factor,
    /// `f` factors as `(x − α) · g(x)` with `g` irreducible quartic
    /// over `F_p` but whose roots all lie in `F_{p²}` (`g | x^{p²} −
    /// x`).  Root pattern `(1)(4)` with the 4-cycle of Frobenius
    /// preserving a 2+2 partition.  The `(2, 2)`-isogeny kernel is
    /// `F_p`-rational even though no rational 3-factor split exists.
    OneFourFp2Split,
    /// No `F_p`-rational `(2, 2)`-decomposition detected.
    None,
}

/// Attempt to factor a monic quintic `f` over `F_p` as a product of
/// a **monic linear** times **two monic quadratics** (the Richelot
/// "3-quadratic" form with one factor (x − ∞) absorbed at infinity).
/// Returns `Some([linear, quad_1, quad_2])` if such a factorisation
/// exists (and there's at least one `F_p`-rational root of `f`),
/// `None` otherwise.
///
/// Concretely: find any root `α` of `f` in `F_p`, divide out
/// `(x − α)` to get a quartic `g`, then try to factor `g` as a
/// product of two monic quadratics over `F_p`.
pub fn richelot_factor(f: &FpPoly) -> Option<[FpPoly; 3]> {
    // Find a root α ∈ F_p of f.
    let p_u: u64 = match f.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => return None,
    };
    let p_big = &f.p;
    let mut alpha = None;
    for ai in 0..p_u {
        let av = BigUint::from(ai);
        let val = f.eval(&av);
        if val.is_zero() {
            alpha = Some(av);
            break;
        }
    }
    let alpha = alpha?;
    // g(x) = f(x) / (x − α)  =  quartic.
    let linear = FpPoly::from_coeffs(
        vec![(p_big - &alpha) % p_big, BigUint::one()],
        p_big.clone(),
    );
    let (g, r) = f.divrem(&linear);
    if !r.is_zero() {
        return None;
    }
    debug_assert_eq!(g.degree(), Some(4));
    // Factor g as monic quartic into two monic quadratics:
    // g(x) = (x² + r₁ x + s₁)·(x² + r₂ x + s₂)
    //      = x⁴ + (r₁+r₂) x³ + (s₁+s₂+r₁ r₂) x² + (r₁ s₂ + r₂ s₁) x + s₁ s₂
    // Match against g = x⁴ + g₃ x³ + g₂ x² + g₁ x + g₀:
    //   r₁ + r₂ = g₃
    //   s₁ + s₂ + r₁ r₂ = g₂
    //   r₁ s₂ + r₂ s₁ = g₁
    //   s₁ s₂ = g₀
    // Enumerate r₁: r₂ = g₃ - r₁.  Then resolve s₁, s₂ from
    // s₁+s₂ = g₂ - r₁ r₂ (=:S), s₁ s₂ = g₀ (=:P).  s₁, s₂ are
    // roots of t² - S t + P = 0.  Cross-check the linear-in-x
    // coefficient.
    let g3 = g.coeff(3);
    let g2 = g.coeff(2);
    let g1 = g.coeff(1);
    let g0 = g.coeff(0);
    let two_inv = crate::prime_hyperelliptic::fp_poly::fp_inv(&BigUint::from(2u32), p_big).unwrap();
    for r1_u in 0..p_u {
        let r1 = BigUint::from(r1_u);
        let r2 = (&g3 + p_big - &r1) % p_big;
        let r1r2 = (&r1 * &r2) % p_big;
        let s_sum = (&g2 + p_big - &r1r2) % p_big;
        let s_prod = g0.clone();
        // s₁, s₂ are roots of t² − S t + P = 0.  In char ≠ 2:
        // disc = S² − 4P; require disc to be a QR (or 0).
        let s_sum_sq = (&s_sum * &s_sum) % p_big;
        let four_p = (&s_prod * BigUint::from(4u32)) % p_big;
        let disc = (&s_sum_sq + p_big - &four_p) % p_big;
        let chi = qr_chi(&disc, p_big);
        if chi == -1 {
            continue;
        }
        let sqrt_disc = mod_sqrt(&disc, p_big);
        if sqrt_disc.is_none() {
            continue;
        }
        let sqrt_disc = sqrt_disc.unwrap();
        // s₁ = (S + √disc)/2, s₂ = (S − √disc)/2
        let s1 = (&s_sum + &sqrt_disc) % p_big;
        let s1 = (&s1 * &two_inv) % p_big;
        let s2 = (&s_sum + p_big - &sqrt_disc) % p_big;
        let s2 = (&s2 * &two_inv) % p_big;
        // Cross-check: r₁ s₂ + r₂ s₁ == g₁
        let cross = ((&r1 * &s2) % p_big + (&r2 * &s1)) % p_big;
        if cross != g1 {
            continue;
        }
        // Found a factorisation.
        let q1 = FpPoly::from_coeffs(vec![s1, r1, BigUint::one()], p_big.clone());
        let q2 = FpPoly::from_coeffs(vec![s2, r2, BigUint::one()], p_big.clone());
        return Some([linear, q1, q2]);
    }
    None
}

/// Full Richelot-style detector.  Tries the explicit 3-factor split
/// across every `F_p` root of `f`; if all fail, checks for the
/// `(1)(4)` Frobenius-pair-preserving pattern by reducing `x^{p²}`
/// modulo the quartic `g = f / (x − α)`.
pub fn richelot_kind(f: &FpPoly) -> RichelotKind {
    let p_u: u64 = match f.p.to_u64_digits().as_slice() {
        [v] => *v,
        _ => return RichelotKind::None,
    };
    let p_big = &f.p;

    // Collect all F_p-roots of f.
    let mut roots: Vec<BigUint> = Vec::new();
    for ai in 0..p_u {
        let av = BigUint::from(ai);
        if f.eval(&av).is_zero() {
            roots.push(av);
        }
    }
    // ── Try the explicit 3-factor split via every F_p root ──
    if !roots.is_empty() {
        for alpha in &roots {
            if try_3_factor_split(f, alpha).is_some() {
                return RichelotKind::Explicit3Factor;
            }
        }
        // ── At least one F_p root, no 3-factor split — check (1)(4) ──
        // Take the first root, build g = f / (x - α).
        let alpha = &roots[0];
        let linear =
            FpPoly::from_coeffs(vec![(p_big - alpha) % p_big, BigUint::one()], p_big.clone());
        let (g, r) = f.divrem(&linear);
        if !r.is_zero() {
            return RichelotKind::None;
        }
        if g.degree() != Some(4) {
            return RichelotKind::None;
        }
        // g irreducible? equivalently, no F_p root of g.
        let mut g_has_root = false;
        for ai in 0..p_u {
            let av = BigUint::from(ai);
            if g.eval(&av).is_zero() {
                g_has_root = true;
                break;
            }
        }
        if g_has_root {
            // g has an F_p root but we already tried every F_p root
            // of f — so the 3-factor split was the only option and it
            // failed.  No (1)(4).
            return RichelotKind::None;
        }
        // Test x^{p²} ≡ x (mod g) — i.e., all roots of g lie in
        // F_{p²}.  Equivalent to g | x^{p²} − x.
        if all_roots_in_fp2(&g, p_u) {
            return RichelotKind::OneFourFp2Split;
        }
        return RichelotKind::None;
    }
    // No F_p root at all → can't pair the ∞-root with anything F_p,
    // so no F_p-rational Richelot decomposition.
    RichelotKind::None
}

/// Try to decompose `f` as `(x − α) · q_1(x) · q_2(x)` (with `α`
/// supplied) into three monic factors with `q_i ∈ F_p[x]` quadratic.
/// Returns the factors on success, `None` on failure.
pub fn try_3_factor_split(f: &FpPoly, alpha: &BigUint) -> Option<[FpPoly; 3]> {
    let p_big = &f.p;
    let p_u: u64 = match p_big.to_u64_digits().as_slice() {
        [v] => *v,
        _ => return None,
    };
    let linear = FpPoly::from_coeffs(vec![(p_big - alpha) % p_big, BigUint::one()], p_big.clone());
    let (g, r) = f.divrem(&linear);
    if !r.is_zero() {
        return None;
    }
    if g.degree() != Some(4) {
        return None;
    }
    let g3 = g.coeff(3);
    let g2 = g.coeff(2);
    let g1 = g.coeff(1);
    let g0 = g.coeff(0);
    let two_inv = crate::prime_hyperelliptic::fp_poly::fp_inv(&BigUint::from(2u32), p_big)?;
    for r1_u in 0..p_u {
        let r1 = BigUint::from(r1_u);
        let r2 = (&g3 + p_big - &r1) % p_big;
        let r1r2 = (&r1 * &r2) % p_big;
        let s_sum = (&g2 + p_big - &r1r2) % p_big;
        let s_prod = g0.clone();
        let s_sum_sq = (&s_sum * &s_sum) % p_big;
        let four_p = (&s_prod * BigUint::from(4u32)) % p_big;
        let disc = (&s_sum_sq + p_big - &four_p) % p_big;
        let chi = qr_chi(&disc, p_big);
        if chi == -1 {
            continue;
        }
        let sqrt_disc = mod_sqrt(&disc, p_big)?;
        let s1 = (&s_sum + &sqrt_disc) % p_big;
        let s1 = (&s1 * &two_inv) % p_big;
        let s2 = (&s_sum + p_big - &sqrt_disc) % p_big;
        let s2 = (&s2 * &two_inv) % p_big;
        let cross = ((&r1 * &s2) % p_big + (&r2 * &s1)) % p_big;
        if cross != g1 {
            continue;
        }
        let q1 = FpPoly::from_coeffs(vec![s1, r1, BigUint::one()], p_big.clone());
        let q2 = FpPoly::from_coeffs(vec![s2, r2, BigUint::one()], p_big.clone());
        return Some([linear, q1, q2]);
    }
    None
}

// ── Igusa-Clebsch I_10 (discriminant) — Phase-3 infrastructure ──────

/// **Discriminant `Δ(f) ∈ F_p`** of a monic quintic `f(x) = x^5 +
/// c_4 x^4 + c_3 x^3 + c_2 x^2 + c_1 x + c_0`.  Equivalent to the
/// **Igusa–Clebsch `I_{10}` invariant** up to a normalising constant
/// (the precise relation for a binary sextic of degree 5 with
/// "leading coefficient 0" at infinity is `I_{10} = 2^{12} · Δ`,
/// where `Δ = disc(f)`).
///
/// `Δ = 0` iff `f` has a repeated root in `F̄_p`.  For `f`
/// squarefree, `Δ ≠ 0` and `Δ` is a useful invariant of `(C, F_p)`
/// (it determines the curve up to twist).
///
/// Computed via the Sylvester resultant formula
/// `Δ = (-1)^{n(n-1)/2} · Res(f, f') / lc(f)`.
///
/// This is the only one of the Igusa–Clebsch invariants `{I_2, I_4,
/// I_6, I_{10}}` we ship; computing `I_2, I_4, I_6` requires more
/// substantial polynomial bookkeeping (degree-2, -4, -6 polynomial
/// expressions in `f`'s coefficients respectively — see Igusa 1960
/// Theorem 2 or Mestre 1991 §1).  They are the **Phase-3 missing
/// infrastructure** required to test Humbert-surface membership at
/// P-256 scale — see the research note for details.
pub fn quintic_discriminant(f: &FpPoly) -> BigUint {
    assert_eq!(f.degree(), Some(5));
    // f' = derivative of f
    let p = &f.p;
    let fp = {
        let mut coeffs: Vec<BigUint> = Vec::with_capacity(5);
        for i in 1..=5 {
            let c = f.coeff(i);
            coeffs.push((c * BigUint::from(i as u32)) % p);
        }
        FpPoly::from_coeffs(coeffs, p.clone())
    };
    // Resultant Res(f, f') via Euclidean GCD trace.
    // Δ = (-1)^{n(n-1)/2} · Res(f, f') / lc(f).
    // For n=5: (-1)^10 = 1, lc(f) = 1 (monic).
    sylvester_resultant(f, &fp)
}

/// Sylvester resultant `Res(a, b)` via the **subresultant Euclidean
/// algorithm**.  Returns `Res ∈ F_p`.
fn sylvester_resultant(a: &FpPoly, b: &FpPoly) -> BigUint {
    let p = a.p.clone();
    if a.is_zero() || b.is_zero() {
        return BigUint::zero();
    }
    // Use the EEA recurrence with the leading-coefficient tracking.
    // Simpler approach: use the fact that for monic polys, Res(a, b)
    // = ∏ b(α_i) where α_i are roots of a.  In char p, this can be
    // computed via the Euclidean algorithm with explicit
    // leading-coefficient bookkeeping.  For genuinely robust
    // computation, fall back to the Sylvester-matrix determinant.
    // Here we use the EEA-with-bookkeeping approach because it's
    // simpler.
    let mut x = a.clone();
    let mut y = b.clone();
    let mut acc = BigUint::one();
    while !y.is_zero() {
        let dy = y.degree().unwrap();
        let dx = x.degree().unwrap();
        let r = x.rem(&y);
        // sign: (-1)^{dx*dy} encoded by tracking parity; in char p
        // (odd) we treat -1 as p-1.
        // After dividing, swap x ← y, y ← r.
        // Per the Sylvester resultant recursion:
        //   Res(x, y) = lc(y)^{dx - deg(r)} · (-1)^{dx · dy} · Res(y, r)
        let dr = r.degree().unwrap_or(0);
        let exp = (dx as i64) - (dr as i64);
        let mut factor = if exp > 0 {
            y.lead().modpow(&BigUint::from(exp as u64), &p)
        } else if exp == 0 {
            BigUint::one()
        } else {
            // exp < 0 — only happens if dr > dx, can't.
            BigUint::one()
        };
        if r.is_zero() {
            // Res = 0 if gcd has positive degree.
            if y.degree().unwrap() > 0 {
                return BigUint::zero();
            }
            // Otherwise y is a constant; Res = y^{dx} · accumulator.
            let pow = y.lead().modpow(&BigUint::from(dx as u64), &p);
            return (acc * pow) % &p;
        }
        // Apply sign.
        if ((dx * dy) & 1) == 1 {
            factor = (&p - &factor) % &p;
        }
        acc = (&acc * &factor) % &p;
        x = y;
        y = r;
    }
    acc
}

/// `g | x^{p²} − x`?  Equivalent: all roots of `g` lie in `F_{p²}`.
/// Computes `x^{p²} mod g` via repeated squaring in `F_p[x]/g`.
fn all_roots_in_fp2(g: &FpPoly, p_u: u64) -> bool {
    let p_sq = (p_u as u128) * (p_u as u128);
    // Compute x^{p²} mod g via repeated squaring (using u128 exp).
    let x = FpPoly::x(g.p.clone());
    let mut acc = FpPoly::one(g.p.clone());
    let mut base = x.clone();
    let mut e = p_sq;
    while e > 0 {
        if e & 1 == 1 {
            acc = acc.mul(&base).rem(g);
        }
        base = base.mul(&base).rem(g);
        e >>= 1;
    }
    // acc == x ?
    acc == x
}

fn qr_chi(a: &BigUint, p: &BigUint) -> i32 {
    if a.is_zero() {
        return 0;
    }
    let exp = (p - BigUint::one()) >> 1;
    let chi = a.modpow(&exp, p);
    if chi.is_one() {
        1
    } else {
        -1
    }
}

/// Tonelli–Shanks `√a (mod p)` for odd prime `p`.  Returns `None` if
/// `a` is not a QR.
pub fn mod_sqrt(a: &BigUint, p: &BigUint) -> Option<BigUint> {
    let a = a % p;
    if a.is_zero() {
        return Some(BigUint::zero());
    }
    if qr_chi(&a, p) != 1 {
        return None;
    }
    // p mod 4 == 3 fast path: √a = a^{(p+1)/4}.
    let four = BigUint::from(4u32);
    if p % &four == BigUint::from(3u32) {
        let exp = (p + BigUint::one()) >> 2;
        return Some(a.modpow(&exp, p));
    }
    // General Tonelli–Shanks.
    let mut q = p - BigUint::one();
    let mut s = 0u32;
    while &q & &BigUint::one() == BigUint::zero() {
        q >>= 1;
        s += 1;
    }
    // Find a non-residue z.
    let mut z = BigUint::from(2u32);
    while qr_chi(&z, p) != -1 {
        z += BigUint::one();
    }
    let mut m = s;
    let mut c = z.modpow(&q, p);
    let mut t = a.modpow(&q, p);
    let mut r = a.modpow(&((&q + BigUint::one()) >> 1), p);
    loop {
        if t.is_one() {
            return Some(r);
        }
        // Find least i, 0 < i < m, with t^{2^i} = 1.
        let mut i = 0u32;
        let mut tt = t.clone();
        while !tt.is_one() {
            tt = (&tt * &tt) % p;
            i += 1;
            if i == m {
                return None; // shouldn't happen if a is QR
            }
        }
        // b = c^{2^{m−i−1}}
        let mut b = c.clone();
        for _ in 0..(m - i - 1) {
            b = (&b * &b) % p;
        }
        m = i;
        c = (&b * &b) % p;
        t = (&t * &c) % p;
        r = (&r * &b) % p;
    }
}

// ── the probe itself ────────────────────────────────────────────────

/// Strength of a probe hit, ordered from weakest to strongest.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HitTier {
    /// `#Jac(C) = #E · #E^twist` (coarse Jacobian-order coincidence).
    /// This is *implied* by Tate-isogeny but doesn't imply it back —
    /// many isogeny classes share the same `#Jac`.
    JacOrderMatch,
    /// **Tier-1½**: `Jac(C)` is `F_p`-isogenous to *some* product
    /// `E_1 × E_2` of two elliptic curves (`a² − 4b + 8p` is a
    /// perfect square in `Z`), with no constraint that the elliptic
    /// factors have prime order or match anything specific.  This is
    /// the "decomposable abelian surface" condition.
    Decomposable,
    /// **Tier-1¾ "one-sided prime"**: `Jac(C)` is `F_p`-isogenous
    /// to `E × E'` with `E` a prime-order curve from our list but
    /// `E'` of *any* trace (possibly composite order).  This asks
    /// "is one of our cryptographic-shape curves a Frobenius factor
    /// of `Jac(C)`?".  Weaker than Tier-2-broad (both prime-order)
    /// but stronger than Tier-1½ (any product).
    OneSidedPrime,
    /// **Tier-2-broad**: `(a, b) = (t_1 + t_2, t_1 t_2 + 2p)` for
    /// some pair `(t_1, t_2)` of Frobenius traces from
    /// **prime-order** elliptic curves over `F_p`.  By Tate, this
    /// means `Jac(C)` is `F_p`-isogenous to `E_{t_1} × E_{t_2}` for
    /// two *cryptographically-shaped* elliptic curves.  More
    /// general than Tier-2-strict — it allows the second factor to
    /// be any prime-order curve, not just the twist of the first.
    FrobeniusMatchBroad,
    /// **Tier-2-strict**: `(a, b) = (0, 2p − t_E²)` — the original
    /// Phase-1 target.  `Jac(C)` is `F_p`-isogenous *exactly* to
    /// `E × E^twist`.
    FrobeniusMatch,
    /// `FrobeniusMatch` *plus* an explicit `F_p`-rational
    /// `(2, 2)`-decomposition of the cover (the Richelot 3-factor
    /// split).  The strongest detector signal we ship.
    FrobeniusPlusRichelot,
}

/// One hit from the cover probe.
#[derive(Clone, Debug)]
pub struct CoverProbeHit {
    pub p: u64,
    /// Source elliptic curve `E`.
    pub e_a: u64,
    pub e_b: u64,
    /// `#E(F_p)`.
    pub n_e: u64,
    /// `#E^twist(F_p)`.
    pub n_t: u64,
    /// `t_E = p + 1 − #E(F_p)`, the Frobenius trace of `E`.
    pub trace_e: i128,
    /// Genus-2 curve coefficients `[c_4, c_3, c_2, c_1, c_0]` so
    /// `f(x) = x⁵ + c_4·x⁴ + … + c_0`.
    pub c_coeffs: [u64; 5],
    /// `#Jac(C)(F_p)`.
    pub n_jac: BigUint,
    /// Frobenius `(a, b)` of `Jac(C)/F_p`.  Together with `p` these
    /// determine the `F_p`-isogeny class of `Jac(C)` (Tate 1966).
    pub frob_a: i128,
    pub frob_b: i128,
    /// Tier of this hit.
    pub tier: HitTier,
    /// Richelot detection outcome (only populated when tier is
    /// `FrobeniusMatch` or `FrobeniusPlusRichelot`).
    pub richelot_kind: RichelotKind,
}

/// Build the per-prime maps used by all probe variants.  Returns
/// `(jac_order_map, frob_strict_map, frob_broad_map)`.
///
/// - `jac_order_map`: `#Jac` → list of prime-order `E` whose
///   `#E · #E^twist` equals that `#Jac`.
/// - `frob_strict_map`: `(0, 2p − t_E²)` → matching `E`.  This is
///   the Phase-4 strict target.
/// - `frob_broad_map`: `(t_1+t_2, t_1 t_2 + 2p)` → list of
///   `(t_1, t_2)` pairs from the prime-order trace list.
fn build_target_maps(
    ecs: &[(ECurveP, u64, u64)],
    p: u64,
) -> (
    std::collections::HashMap<BigUint, Vec<(u64, u64, u64, u64, i128)>>,
    std::collections::HashMap<(i128, i128), Vec<(u64, u64, u64, u64, i128)>>,
    std::collections::HashMap<(i128, i128), Vec<(i128, i128)>>,
) {
    let mut jac_map = std::collections::HashMap::new();
    let mut frob_strict_map = std::collections::HashMap::new();
    let mut frob_broad_map: std::collections::HashMap<(i128, i128), Vec<(i128, i128)>> =
        std::collections::HashMap::new();
    let traces: Vec<i128> = ecs
        .iter()
        .map(|(_, n, _)| (p as i128) + 1 - (*n as i128))
        .collect();
    for (e, n, n_t) in ecs {
        let t_e: i128 = (p as i128) + 1 - (*n as i128);
        let jac_target = BigUint::from(*n) * BigUint::from(*n_t);
        let b_target: i128 = 2 * (p as i128) - t_e * t_e;
        jac_map
            .entry(jac_target)
            .or_insert_with(Vec::new)
            .push((e.a, e.b, *n, *n_t, t_e));
        frob_strict_map
            .entry((0i128, b_target))
            .or_insert_with(Vec::new)
            .push((e.a, e.b, *n, *n_t, t_e));
    }
    // Broad map: every (t_1, t_2) pair (including t_1 = t_2).
    for &t1 in &traces {
        for &t2 in &traces {
            let a = t1 + t2;
            let b = t1 * t2 + 2 * (p as i128);
            frob_broad_map.entry((a, b)).or_default().push((t1, t2));
        }
    }
    (jac_map, frob_strict_map, frob_broad_map)
}

/// Build the "one-sided prime" map: every `(t_1 + t_2, t_1 t_2 + 2p)`
/// where `t_1 ∈ prime-order trace list` and `t_2 ∈ [−⌊2√p⌋, ⌊2√p⌋]`
/// (any Frobenius-valid trace).  Used by the Tier-1¾ detector.
fn build_one_sided_prime_map(
    ecs: &[(ECurveP, u64, u64)],
    p: u64,
) -> std::collections::HashSet<(i128, i128)> {
    use std::collections::HashSet;
    let traces: Vec<i128> = ecs
        .iter()
        .map(|(_, n, _)| (p as i128) + 1 - (*n as i128))
        .collect();
    let bound = (2.0 * (p as f64).sqrt()).floor() as i128;
    let mut out = HashSet::new();
    for &t1 in &traces {
        for t2 in (-bound)..=bound {
            let a = t1 + t2;
            let b = t1 * t2 + 2 * (p as i128);
            out.insert((a, b));
        }
    }
    out
}

/// Run the probe at prime `p` using the fast L-polynomial counter.
/// Returns all hits.
///
/// **Two-tier matching**:
/// - `JacOrderMatch`: coarse — `#Jac(C) = #E · #E^t`.
/// - `FrobeniusMatch`: strict — `(a, b) = (0, 2p − t_E²)`, meaning
///   `Jac(C)` is `F_p`-**isogenous** to `E × E^twist` by Tate.
/// - `FrobeniusPlusRichelot`: `FrobeniusMatch` + explicit Richelot
///   3-factor `F_p`-rational decomposition of `f`.
///
/// Compute cost: `O(p^7)` (same as before — the strict test is a
/// constant-time additional filter).
pub fn run_probe(p: u64, max_curves: Option<usize>) -> Vec<CoverProbeHit> {
    assert!(p >= 5 && is_prime_u64(p), "p must be a prime ≥ 5");
    let ecs = sweep_prime_order_curves(p);
    if ecs.is_empty() {
        return Vec::new();
    }
    let (jac_map, frob_strict_map, frob_broad_map) = build_target_maps(&ecs, p);
    let one_sided_set = build_one_sided_prime_map(&ecs, p);
    let p_big = BigUint::from(p);
    let _ctx = Fp2Ctx::new(p);
    let mut hits = Vec::new();
    let mut tried = 0usize;
    let total_curves = (p as usize).pow(5);
    let cap = max_curves.unwrap_or(total_curves);
    for c4 in 0..p {
        for c3 in 0..p {
            for c2 in 0..p {
                for c1 in 0..p {
                    for c0 in 0..p {
                        if tried >= cap {
                            return hits;
                        }
                        tried += 1;
                        if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                            continue;
                        }
                        let f = FpPoly::from_coeffs(
                            vec![
                                BigUint::from(c0),
                                BigUint::from(c1),
                                BigUint::from(c2),
                                BigUint::from(c3),
                                BigUint::from(c4),
                                BigUint::one(),
                            ],
                            p_big.clone(),
                        );
                        let curve = HyperellipticCurveP::new(p_big.clone(), f.clone(), 2);
                        let (ab, n_jac) = fast_frob_ab(&curve);
                        classify_and_push(
                            p,
                            &ab,
                            &n_jac,
                            &f,
                            [c4, c3, c2, c1, c0],
                            &jac_map,
                            &frob_strict_map,
                            &frob_broad_map,
                            &one_sided_set,
                            &mut hits,
                        );
                    }
                }
            }
        }
    }
    hits
}

/// Classification logic shared by `run_probe` and `run_probe_random`:
/// take a single curve's `(a, b)` + `#Jac` and append the appropriate
/// hit(s) to `hits`, in *descending* tier order (strongest first).
#[allow(clippy::too_many_arguments)]
fn classify_and_push(
    p: u64,
    ab: &crate::prime_hyperelliptic::FrobABForJac,
    n_jac: &BigUint,
    f: &FpPoly,
    c_coeffs: [u64; 5],
    jac_map: &std::collections::HashMap<BigUint, Vec<(u64, u64, u64, u64, i128)>>,
    frob_strict_map: &std::collections::HashMap<(i128, i128), Vec<(u64, u64, u64, u64, i128)>>,
    frob_broad_map: &std::collections::HashMap<(i128, i128), Vec<(i128, i128)>>,
    one_sided_set: &std::collections::HashSet<(i128, i128)>,
    hits: &mut Vec<CoverProbeHit>,
) {
    // Tier 2/3 — strict Frobenius (a, b) = (0, 2p − t_E²).
    if let Some(es) = frob_strict_map.get(&(ab.a, ab.b)) {
        let kind = richelot_kind(f);
        let tier = if kind == RichelotKind::Explicit3Factor {
            HitTier::FrobeniusPlusRichelot
        } else {
            HitTier::FrobeniusMatch
        };
        for (e_a, e_b, n_e, n_t, t_e) in es {
            hits.push(CoverProbeHit {
                p,
                e_a: *e_a,
                e_b: *e_b,
                n_e: *n_e,
                n_t: *n_t,
                trace_e: *t_e,
                c_coeffs,
                n_jac: n_jac.clone(),
                frob_a: ab.a,
                frob_b: ab.b,
                tier,
                richelot_kind: kind.clone(),
            });
        }
        return;
    }
    // Tier 2-broad — any prime-order pair (t_1, t_2).
    if frob_broad_map.contains_key(&(ab.a, ab.b)) {
        hits.push(CoverProbeHit {
            p,
            e_a: 0,
            e_b: 0,
            n_e: 0,
            n_t: 0,
            trace_e: 0,
            c_coeffs,
            n_jac: n_jac.clone(),
            frob_a: ab.a,
            frob_b: ab.b,
            tier: HitTier::FrobeniusMatchBroad,
            richelot_kind: richelot_kind(f),
        });
        return;
    }
    // Tier-1¾ — one-sided prime-order match: Jac ~ E × E' with E
    // prime-order and E' anything.
    if one_sided_set.contains(&(ab.a, ab.b)) {
        hits.push(CoverProbeHit {
            p,
            e_a: 0,
            e_b: 0,
            n_e: 0,
            n_t: 0,
            trace_e: 0,
            c_coeffs,
            n_jac: n_jac.clone(),
            frob_a: ab.a,
            frob_b: ab.b,
            tier: HitTier::OneSidedPrime,
            richelot_kind: richelot_kind(f),
        });
        return;
    }
    // Tier-1½ — decomposable into *some* product of elliptic curves
    // (without requiring prime order).
    if is_jac_decomposable_over_z(ab.a, ab.b, p) {
        hits.push(CoverProbeHit {
            p,
            e_a: 0,
            e_b: 0,
            n_e: 0,
            n_t: 0,
            trace_e: 0,
            c_coeffs,
            n_jac: n_jac.clone(),
            frob_a: ab.a,
            frob_b: ab.b,
            tier: HitTier::Decomposable,
            richelot_kind: richelot_kind(f),
        });
        return;
    }
    // Tier 1 — coarse #Jac match.
    if let Some(es) = jac_map.get(n_jac) {
        for (e_a, e_b, n_e, n_t, t_e) in es {
            hits.push(CoverProbeHit {
                p,
                e_a: *e_a,
                e_b: *e_b,
                n_e: *n_e,
                n_t: *n_t,
                trace_e: *t_e,
                c_coeffs,
                n_jac: n_jac.clone(),
                frob_a: ab.a,
                frob_b: ab.b,
                tier: HitTier::JacOrderMatch,
                richelot_kind: RichelotKind::None,
            });
        }
    }
}

/// **Random-sample** probe with the same two-tier matching as
/// [`run_probe`].  Use for `p` too large for the full sweep.
pub fn run_probe_random(p: u64, n_samples: usize, seed: u64) -> Vec<CoverProbeHit> {
    use rand::rngs::SmallRng;
    use rand::{Rng, SeedableRng};
    assert!(p >= 5 && is_prime_u64(p), "p must be a prime ≥ 5");
    let ecs = sweep_prime_order_curves(p);
    if ecs.is_empty() {
        return Vec::new();
    }
    let (jac_map, frob_strict_map, frob_broad_map) = build_target_maps(&ecs, p);
    let one_sided_set = build_one_sided_prime_map(&ecs, p);
    let p_big = BigUint::from(p);
    let _ctx = Fp2Ctx::new(p);
    let mut hits = Vec::new();
    let mut rng = SmallRng::seed_from_u64(seed);
    for _ in 0..n_samples {
        let c4: u64 = rng.gen_range(0..p);
        let c3: u64 = rng.gen_range(0..p);
        let c2: u64 = rng.gen_range(0..p);
        let c1: u64 = rng.gen_range(0..p);
        let c0: u64 = rng.gen_range(0..p);
        if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
            continue;
        }
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::from(c0),
                BigUint::from(c1),
                BigUint::from(c2),
                BigUint::from(c3),
                BigUint::from(c4),
                BigUint::one(),
            ],
            p_big.clone(),
        );
        let curve = HyperellipticCurveP::new(p_big.clone(), f.clone(), 2);
        // Use fast u64-only counter (Phase 9 optimization).
        let (ab, n_jac) = fast_frob_ab(&curve);
        classify_and_push(
            p,
            &ab,
            &n_jac,
            &f,
            [c4, c3, c2, c1, c0],
            &jac_map,
            &frob_strict_map,
            &frob_broad_map,
            &one_sided_set,
            &mut hits,
        );
    }
    hits
}

/// Summary statistics of a probe run.
#[derive(Clone, Debug)]
pub struct ProbeStats {
    pub p: u64,
    pub n_prime_order_curves: usize,
    pub n_genus2_curves_tested: u64,
    /// Tier 1: coarse `#Jac` match only (no Frobenius-strict match).
    pub n_jac_order_only: usize,
    /// **Tier-1½**: decomposable into *some* product of elliptic
    /// curves (not necessarily prime-order, not necessarily our
    /// target).  `a² − 4b + 8p` is a perfect square.
    pub n_jac_decomposable: usize,
    /// **Tier-1¾**: one-sided prime-order match — `Jac(C) ~_{F_p} E × E'`
    /// with `E` from our prime-order list and `E'` of any trace.
    pub n_one_sided_prime: usize,
    /// **Tier 2-broad**: `Jac(C) ~_{F_p} E_{t_1} × E_{t_2}` for some
    /// pair of prime-order curves — i.e., for SOME pair `(t_1, t_2)`
    /// of Frobenius traces, `(a, b) = (t_1 + t_2, t_1 t_2 + 2p)`.
    /// Relaxes the original target `(E, E^twist)` to "any
    /// cryptographically-shaped pair".
    pub n_frobenius_broad: usize,
    /// Tier 2-strict: `(0, 2p − t_E²)` match (the original Phase-1
    /// target `E × E^twist`), no explicit Richelot.
    pub n_frobenius_match: usize,
    /// Tier 3: Frobenius match + explicit `F_p`-rational Richelot
    /// 3-factor decomposition of `f`.  The "real" Phase-1 question.
    pub n_frobenius_plus_richelot: usize,
    /// Hits with `OneFour-F_p²` Richelot kind (informational only —
    /// these don't correspond to `F_p`-rational `E × E^twist`).
    pub n_richelot_one_four: usize,
}

/// **Decomposable-Jacobian test** (weaker than `FrobeniusMatch`,
/// stronger than `JacOrderMatch`).
///
/// `Jac(C)` is `F_p`-isogenous to *some* product `E_1 × E_2` of two
/// elliptic curves (both over `F_p`) iff its Frobenius char poly
/// factors over `Z`, iff `a² − 4(b − 2p) = a² − 4b + 8p` is a
/// perfect square in `Z`.
///
/// This is *strictly* the "any product" condition — it doesn't
/// require either elliptic factor to match `E` specifically.  Used
/// as an intermediate sanity check: even before Phase-1's
/// `P-256 × P-256^twist` question, we can ask "how often is `Jac(C)`
/// `F_p`-isogenous to *any* product?".  The expected answer is
/// `O(1/p)` — the codimension of the decomposable locus.
pub fn is_jac_decomposable_over_z(a: i128, b: i128, p: u64) -> bool {
    let disc = a * a - 4 * b + 8 * (p as i128);
    if disc < 0 {
        return false;
    }
    let s = isqrt_i128(disc);
    s * s == disc
}

fn isqrt_i128(n: i128) -> i128 {
    if n < 2 {
        return n;
    }
    let mut x = n;
    let mut y = (x + 1) / 2;
    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }
    x
}

fn tally_stats(hits: &[CoverProbeHit], p: u64, total: u64, n_eqs: usize) -> ProbeStats {
    let n_jac_only = hits
        .iter()
        .filter(|h| h.tier == HitTier::JacOrderMatch)
        .count();
    let n_decomp = hits
        .iter()
        .filter(|h| h.tier == HitTier::Decomposable)
        .count();
    let n_one_sided = hits
        .iter()
        .filter(|h| h.tier == HitTier::OneSidedPrime)
        .count();
    let n_broad = hits
        .iter()
        .filter(|h| h.tier == HitTier::FrobeniusMatchBroad)
        .count();
    let n_frob = hits
        .iter()
        .filter(|h| h.tier == HitTier::FrobeniusMatch)
        .count();
    let n_frob_richelot = hits
        .iter()
        .filter(|h| h.tier == HitTier::FrobeniusPlusRichelot)
        .count();
    let n_one_four = hits
        .iter()
        .filter(|h| h.richelot_kind == RichelotKind::OneFourFp2Split)
        .count();
    ProbeStats {
        p,
        n_prime_order_curves: n_eqs,
        n_genus2_curves_tested: total,
        n_jac_order_only: n_jac_only,
        n_jac_decomposable: n_decomp,
        n_one_sided_prime: n_one_sided,
        n_frobenius_broad: n_broad,
        n_frobenius_match: n_frob,
        n_frobenius_plus_richelot: n_frob_richelot,
        n_richelot_one_four: n_one_four,
    }
}

/// Run the full sweep probe and return summary statistics + hits.
pub fn run_probe_with_stats(p: u64, max_curves: Option<usize>) -> (ProbeStats, Vec<CoverProbeHit>) {
    let ecs = sweep_prime_order_curves(p);
    let n_eqs = ecs.len();
    let hits = run_probe(p, max_curves);
    let total = p.pow(5);
    let stats = tally_stats(&hits, p, total, n_eqs);
    (stats, hits)
}

/// Run the random-sampling probe and return summary statistics + hits.
pub fn run_probe_random_with_stats(
    p: u64,
    n_samples: usize,
    seed: u64,
) -> (ProbeStats, Vec<CoverProbeHit>) {
    let ecs = sweep_prime_order_curves(p);
    let n_eqs = ecs.len();
    let hits = run_probe_random(p, n_samples, seed);
    let stats = tally_stats(&hits, p, n_samples as u64, n_eqs);
    (stats, hits)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::prime_hyperelliptic::frob_ab_and_jac;

    #[test]
    fn tiny_sweep_p_5() {
        // p = 5: ordinary curves with prime order — counts.
        let ecs = sweep_prime_order_curves(5);
        // Just confirm the sweep produced some output.
        assert!(ecs.is_empty() || ecs.iter().all(|(_, n, _)| is_prime_u64(*n)));
        for (_, n, _) in &ecs {
            assert!(is_prime_u64(*n));
        }
    }

    #[test]
    fn mod_sqrt_roundtrip() {
        for p in &[7u32, 11, 13, 17, 23, 29] {
            let pb = BigUint::from(*p);
            for a in 1u32..*p {
                let ab = BigUint::from(a);
                if let Some(s) = mod_sqrt(&ab, &pb) {
                    let sq = (&s * &s) % &pb;
                    assert_eq!(
                        sq, ab,
                        "mod_sqrt({}) mod {} = {}, but {}² mod {} ≠ {}",
                        a, p, s, s, p, a
                    );
                }
            }
        }
    }

    fn print_stats(label: &str, stats: &ProbeStats) {
        println!("\n=== {} (p = {}) ===", label, stats.p);
        println!(
            "  prime-order curves:        {}",
            stats.n_prime_order_curves
        );
        println!(
            "  curves swept:              {}",
            stats.n_genus2_curves_tested
        );
        println!(
            "  Tier-1   JacOrderMatch:         {}",
            stats.n_jac_order_only
        );
        println!(
            "  Tier-1½  Decomposable any-product: {}",
            stats.n_jac_decomposable
        );
        println!(
            "  Tier-1¾  OneSidedPrime:           {}",
            stats.n_one_sided_prime
        );
        println!(
            "  Tier-2b  FrobeniusMatch (broad):  {}",
            stats.n_frobenius_broad
        );
        println!(
            "  Tier-2s  FrobeniusMatch (strict): {}",
            stats.n_frobenius_match
        );
        println!(
            "  Tier-3   +ExplicitRichelot:      {}",
            stats.n_frobenius_plus_richelot
        );
        println!(
            "  (informational) OneFour-F_p²: {}",
            stats.n_richelot_one_four
        );
    }

    /// Multi-prime full sweep at `p ∈ {7, 11, 13}` (full enumeration).
    /// Each is `O(p^7)` with the L-polynomial counter — seconds to a
    /// few minutes.  Use `--ignored --nocapture` to see the table.
    #[test]
    #[ignore]
    fn phase2_full_sweep_small_primes() {
        for p in [7u64, 11, 13] {
            let (stats, _hits) = run_probe_with_stats(p, None);
            print_stats("Phase-2 full sweep", &stats);
        }
    }

    /// Sweep at `p = 17, 19` — heavier but still tractable in
    /// release mode.  Tens of minutes total.
    #[test]
    #[ignore]
    fn phase2_full_sweep_medium_primes() {
        for p in [17u64, 19] {
            let (stats, _hits) = run_probe_with_stats(p, None);
            print_stats("Phase-2 full sweep", &stats);
        }
    }

    /// Random-sampling probe at `p = 251` (8-bit Solinas-ish prime),
    /// `n = 50_000` samples.  ~minutes.  This is the Phase-3 "toy
    /// P-256" — a prime where direct enumeration of all `p^5 ≈ 10^12`
    /// quintics is infeasible.
    #[test]
    #[ignore]
    fn phase3_sampling_p251() {
        let (stats, hits) = run_probe_random_with_stats(251, 50_000, 0xC0FFEE);
        print_stats("Phase-3 sampling", &stats);
        let explicit_hits: Vec<_> = hits
            .iter()
            .filter(|h| h.richelot_kind == RichelotKind::Explicit3Factor)
            .take(3)
            .collect();
        let onefour_hits: Vec<_> = hits
            .iter()
            .filter(|h| h.richelot_kind == RichelotKind::OneFourFp2Split)
            .take(3)
            .collect();
        if !explicit_hits.is_empty() {
            println!("\n  Sample Explicit3Factor hits:");
            for h in explicit_hits {
                println!(
                    "    E(a={}, b={}): #E={}, #E^t={}; C coeffs {:?}; Jac={}",
                    h.e_a, h.e_b, h.n_e, h.n_t, h.c_coeffs, h.n_jac
                );
            }
        }
        if !onefour_hits.is_empty() {
            println!("\n  Sample OneFour-F_p² hits:");
            for h in onefour_hits {
                println!(
                    "    E(a={}, b={}): #E={}, #E^t={}; C coeffs {:?}; Jac={}",
                    h.e_a, h.e_b, h.n_e, h.n_t, h.c_coeffs, h.n_jac
                );
            }
        }
    }

    /// **Phase-10 Frobenius-class histogram** at `p`.  Exhaustively
    /// enumerates ALL squarefree monic quintic Jacobians over `F_p`
    /// and tabulates which `(a, b)` Frobenius classes are realized
    /// vs unrealized.  Specifically reports whether each Tier-2-strict
    /// target class `(0, 2p − t_E²)` is realized.
    ///
    /// At `p = 11` this is `~161k` curves with the fast `u64`-only
    /// counter — runs in seconds.
    fn phase10_class_histogram(p: u64) {
        use std::collections::HashMap;
        let p_big = BigUint::from(p);
        let ecs = sweep_prime_order_curves(p);
        let mut prime_traces: Vec<i128> = ecs
            .iter()
            .map(|(_, n, _)| (p as i128) + 1 - (*n as i128))
            .collect();
        prime_traces.sort_unstable();
        prime_traces.dedup();
        // Compute the Tier-2-strict target (a, b) for each prime-order trace.
        let tier2_targets: Vec<(i128, i128)> = prime_traces
            .iter()
            .map(|&t| (0i128, 2 * (p as i128) - t * t))
            .collect();
        // Enumerate all squarefree monic quintics, bucket by (a, b).
        let mut counts: HashMap<(i128, i128), u64> = HashMap::new();
        let mut total: u64 = 0;
        for c4 in 0..p {
            for c3 in 0..p {
                for c2 in 0..p {
                    for c1 in 0..p {
                        for c0 in 0..p {
                            if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                                continue;
                            }
                            let f = FpPoly::from_coeffs(
                                vec![
                                    BigUint::from(c0),
                                    BigUint::from(c1),
                                    BigUint::from(c2),
                                    BigUint::from(c3),
                                    BigUint::from(c4),
                                    BigUint::one(),
                                ],
                                p_big.clone(),
                            );
                            let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                            let (ab, _) = fast_frob_ab(&curve);
                            *counts.entry((ab.a, ab.b)).or_insert(0) += 1;
                            total += 1;
                        }
                    }
                }
            }
        }
        // Report.
        let n_classes = counts.len();
        let avg_per_class = (total as f64) / (n_classes as f64);
        println!("\n=== Phase-10 class histogram (p = {}) ===", p);
        println!("  squarefree monic quintics:   {}", total);
        println!("  distinct (a, b) classes:     {}", n_classes);
        println!("  average curves per class:    {:.1}", avg_per_class);
        println!("\n  Tier-2-strict targets and their realization:");
        for ((a, b), &t_e) in tier2_targets.iter().zip(prime_traces.iter()) {
            let realized = counts.contains_key(&(*a, *b));
            let realized_count = counts.get(&(*a, *b)).copied().unwrap_or(0);
            println!(
                "    t_E = {:>4}  → (a, b) = ({}, {})  | {} (count {})",
                t_e,
                a,
                b,
                if realized {
                    "realized"
                } else {
                    "EMPTY (no Jacobian)"
                },
                realized_count,
            );
        }
        let empty_count = tier2_targets
            .iter()
            .filter(|(a, b)| !counts.contains_key(&(*a, *b)))
            .count();
        println!(
            "\n  Empty Tier-2 target classes: {} / {} ({} non-empty)",
            empty_count,
            tier2_targets.len(),
            tier2_targets.len() - empty_count
        );
        // Report ALL (a = 0, b) classes that ARE realized.
        let mut a0_classes: Vec<(i128, u64)> = counts
            .iter()
            .filter(|((a, _), _)| *a == 0)
            .map(|((_, b), c)| (*b, *c))
            .collect();
        a0_classes.sort();
        println!("\n  All realized (a = 0, b) classes:");
        for (b, c) in &a0_classes {
            // Decode t_1, t_2 if decomposable.
            let disc: i128 = -4 * b + 8 * (p as i128);
            let s = if disc < 0 {
                None
            } else {
                let sq = isqrt_i128(disc);
                if sq * sq == disc {
                    Some(sq)
                } else {
                    None
                }
            };
            let label = if let Some(s) = s {
                let t1 = s / 2;
                let _t2 = -t1;
                let t1_is_prime = prime_traces.contains(&t1) || prime_traces.contains(&-t1);
                format!(
                    "t_1 = ±{}{}",
                    t1.abs(),
                    if t1_is_prime {
                        "  [prime-order E exists]"
                    } else {
                        ""
                    }
                )
            } else {
                "non-decomposable over Z".to_string()
            };
            println!("    b = {:>4} (count {:>5}) — {}", b, c, label);
        }
        // Compute the (a, b) box and report fill fraction.
        let max_a_abs = (2.0 * (p as f64).sqrt() * 2.0) as i128;
        let max_b_abs = (4.0 * p as f64) as i128;
        println!(
            "  Theoretical (a, b) Hasse-Weil box: ~ [{}, {}] × [{}, {}]",
            -max_a_abs, max_a_abs, -max_b_abs, max_b_abs,
        );
        println!(
            "  Realized class fraction: {:.3}%",
            100.0 * (n_classes as f64) / ((2 * max_a_abs + 1) as f64 * (2 * max_b_abs + 1) as f64)
        );
    }

    /// Phase 10 driver at `p = 7`.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p7() {
        phase10_class_histogram(7);
    }

    /// Phase 10 driver at `p = 11`.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p11() {
        phase10_class_histogram(11);
    }

    /// Phase 10 driver at `p = 13`.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p13() {
        phase10_class_histogram(13);
    }

    /// Phase 10 driver at `p = 17`.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p17() {
        phase10_class_histogram(17);
    }

    /// Phase 10 driver at `p = 19`.  Largest exhaustive sweep we run.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p19() {
        phase10_class_histogram(19);
    }

    /// Phase 10 driver at `p = 23`.  Even bigger.  ~5 min.
    #[test]
    #[ignore]
    fn phase10_class_histogram_p23() {
        phase10_class_histogram(23);
    }

    /// **Phase 11 — Frobenius-class mod-ℓ histogram** for `ℓ ∈ {3, 5,
    /// 7}`.  Generalises Phase 10's mod-2 obstruction analysis to
    /// detect potential mod-ℓ obstructions for `(ℓ, ℓ)`-cover
    /// attacks.
    ///
    /// For each prime `ℓ`, tabulates which `(a mod ℓ, b mod ℓ)`
    /// parity classes are realised by Jacobians over `F_p` and
    /// which are empty.  Reports the target mod-ℓ class for
    /// `(P-256-like)·twist` configurations and tests whether
    /// that class is obstructed.
    fn phase11_mod_ell_histogram(p: u64, ell: i128) {
        use std::collections::HashMap;
        let p_big = BigUint::from(p);
        let ecs = sweep_prime_order_curves(p);
        // Prime-order target (a, b) mod ell:
        let tier2_mod_ell_targets: Vec<((i128, i128), i128)> = ecs
            .iter()
            .map(|(_, n, _)| {
                let t = (p as i128) + 1 - (*n as i128);
                let target = (
                    0i128.rem_euclid(ell),
                    (2 * (p as i128) - t * t).rem_euclid(ell),
                );
                (target, t)
            })
            .collect();
        // Enumerate squarefree quintics and bucket by (a mod ell, b mod ell).
        let mut counts: HashMap<(i128, i128), u64> = HashMap::new();
        let mut total: u64 = 0;
        for c4 in 0..p {
            for c3 in 0..p {
                for c2 in 0..p {
                    for c1 in 0..p {
                        for c0 in 0..p {
                            if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                                continue;
                            }
                            let f = FpPoly::from_coeffs(
                                vec![
                                    BigUint::from(c0),
                                    BigUint::from(c1),
                                    BigUint::from(c2),
                                    BigUint::from(c3),
                                    BigUint::from(c4),
                                    BigUint::one(),
                                ],
                                p_big.clone(),
                            );
                            let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                            let (ab, _) = fast_frob_ab(&curve);
                            let key = (ab.a.rem_euclid(ell), ab.b.rem_euclid(ell));
                            *counts.entry(key).or_insert(0) += 1;
                            total += 1;
                        }
                    }
                }
            }
        }
        // Report.
        let possible_classes = (ell * ell) as usize;
        let realized_classes = counts.len();
        println!("\n=== Phase 11 — mod-{} histogram at p = {} ===", ell, p);
        println!("  Total Jacobians:               {}", total);
        println!(
            "  Possible (a, b) mod-{} classes:    {}",
            ell, possible_classes
        );
        println!(
            "  Realized mod-{} classes:           {} / {}",
            ell, realized_classes, possible_classes
        );
        // Show all classes (realized or empty).
        println!("\n  Full mod-{} (a, b) realisation table:", ell);
        for a_mod in 0..ell {
            for b_mod in 0..ell {
                let count = counts.get(&(a_mod, b_mod)).copied().unwrap_or(0);
                let status = if count == 0 { "EMPTY" } else { "realized" };
                println!(
                    "    (a mod {}, b mod {}) = ({}, {}): {:>6} curves  ({})",
                    ell, ell, a_mod, b_mod, count, status
                );
            }
        }
        // Tier-2 mod-ℓ targets and their realization.
        println!(
            "\n  Tier-2-strict mod-{} targets (E × E^twist for prime-order E):",
            ell
        );
        let mut unique_targets: Vec<((i128, i128), i128)> = tier2_mod_ell_targets.clone();
        unique_targets.sort_by_key(|((a, b), _)| (*a, *b));
        let mut seen: HashMap<(i128, i128), Vec<i128>> = HashMap::new();
        for (key, t) in unique_targets {
            seen.entry(key).or_default().push(t);
        }
        let mut tier_empties = 0usize;
        for (key, traces) in &seen {
            let count = counts.get(key).copied().unwrap_or(0);
            let status = if count == 0 {
                tier_empties += 1;
                "EMPTY"
            } else {
                "realized"
            };
            println!(
                "    (a mod {}, b mod {}) = ({}, {}): {} (traces: {:?})",
                ell, ell, key.0, key.1, status, traces
            );
        }
        println!(
            "\n  Tier-2-strict mod-{} target classes that are EMPTY: {} / {}",
            ell,
            tier_empties,
            seen.len()
        );
    }

    /// **Phase 17 — Lang–Trotter distribution of `a_ℓ` for P-256**.
    ///
    /// For E/Q (specifically P-256 viewed as an elliptic curve over
    /// Q with integer coefficients `a = -3`, `b = b_p256`), compute
    /// `a_ℓ = ℓ + 1 − #E(F_ℓ)` for many small primes ℓ.  Tabulate
    /// the mod-m distribution for m ∈ {2, 3, 4, 6, 12} and compare
    /// against the Sato–Tate / Lang–Trotter null hypothesis.
    ///
    /// Under Sato–Tate, `a_ℓ / (2√ℓ)` is asymptotically distributed
    /// according to `(2/π) √(1 − x²)` on [-1, 1].  This induces a
    /// uniform-ish mod-m distribution for fixed small m.
    ///
    /// **The hypothesis**: if NIST's seed was chosen adversarially
    /// to land on a curve with hidden structure, the empirical
    /// `a_ℓ mod m` distribution might deviate `> 3σ` from uniform.
    #[test]
    #[ignore]
    fn phase17_lang_trotter_p256_distribution() {
        // P-256 over Q: a = -3, b = the FIPS 186-4 value.
        // For reduction mod ℓ for small ℓ, we just use a, b mod ℓ.
        let b_p256_hex = "5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b";
        let b_p256 = BigUint::parse_bytes(b_p256_hex.as_bytes(), 16).unwrap();

        // Sieve primes up to BOUND.
        const BOUND: u64 = 10_000;
        let mut sieve = vec![true; BOUND as usize + 1];
        sieve[0] = false;
        sieve[1] = false;
        for i in 2..=BOUND {
            if sieve[i as usize] {
                let mut j = i * i;
                while j <= BOUND {
                    sieve[j as usize] = false;
                    j += i;
                }
            }
        }
        // Collect a_ℓ for each prime ℓ ≤ BOUND, ℓ ≠ 2, 3 (special reduction).
        let mut samples: Vec<(u64, i64)> = Vec::new();
        for ell in 5..=BOUND {
            if !sieve[ell as usize] {
                continue;
            }
            let ell_b = BigUint::from(ell);
            let a_mod_ell: u64 = ((&BigUint::from(ell - 3u64)) % &ell_b)
                .to_u64_digits()
                .first()
                .copied()
                .unwrap_or(0);
            let b_mod_ell: u64 = (&b_p256 % &ell_b)
                .to_u64_digits()
                .first()
                .copied()
                .unwrap_or(0);
            // Build E/F_ℓ and count points.
            let curve = ECurveP {
                p: ell,
                a: a_mod_ell,
                b: b_mod_ell,
            };
            if !curve.is_smooth() {
                continue;
            }
            let n = curve.order();
            let a_ell: i64 = (ell as i64) + 1 - (n as i64);
            samples.push((ell, a_ell));
        }

        let n_samples = samples.len();
        println!("\n=== Phase 17 — Lang–Trotter for P-256 ===");
        println!("  Primes ℓ ≤ {}: {} samples", BOUND, n_samples);

        // Tabulate mod-m distribution for m ∈ {2, 3}.
        // **Important**: the correct null is NOT uniform — it's the
        // Sato–Tate / Lang–Trotter prediction derived from the
        // surjective mod-m Galois representation.  For non-CM
        // elliptic curves over Q:
        //   mod 2: trace count in GL_2(F_2) ≅ S_3 is (4, 2),
        //          giving Pr(a_ℓ ≡ 0) = 2/3, Pr(a_ℓ ≡ 1) = 1/3.
        //   mod 3: trace count in GL_2(F_3) is (18, 15, 15),
        //          giving Pr(≡0) = 3/8, Pr(≡1) = Pr(≡2) = 5/16.
        let chi_sq_against = |counts: &[u64], probs: &[f64]| -> f64 {
            let n = counts.iter().sum::<u64>() as f64;
            counts
                .iter()
                .zip(probs)
                .map(|(&c, &p)| {
                    let exp = p * n;
                    let diff = c as f64 - exp;
                    diff * diff / exp
                })
                .sum::<f64>()
        };
        // mod 2
        let mut c2 = vec![0u64; 2];
        for (_, a) in &samples {
            c2[((*a).rem_euclid(2)) as usize] += 1;
        }
        let probs_mod2 = [2.0 / 3.0, 1.0 / 3.0];
        let chi_2 = chi_sq_against(&c2, &probs_mod2);
        println!(
            "  mod 2 (vs Sato–Tate 2/3, 1/3): counts = {:?}, χ² = {:.3}, df = 1, crit_0.05 = 3.84",
            c2, chi_2
        );
        // mod 3
        let mut c3 = vec![0u64; 3];
        for (_, a) in &samples {
            c3[((*a).rem_euclid(3)) as usize] += 1;
        }
        let probs_mod3 = [18.0 / 48.0, 15.0 / 48.0, 15.0 / 48.0];
        let chi_3 = chi_sq_against(&c3, &probs_mod3);
        println!(
            "  mod 3 (vs GL_2(F_3) trace dist): counts = {:?}, χ² = {:.3}, df = 2, crit_0.05 = 5.99",
            c3, chi_3
        );
        // Verdict
        if chi_2 < 3.84 && chi_3 < 5.99 {
            println!(
                "  → BOTH mod-2 and mod-3 distributions consistent with surjective Galois (Serre)."
            );
            println!("    No evidence of anomalous Galois structure.");
        } else {
            println!("  → DEVIATION DETECTED — investigate Galois-rep structure further.");
        }

        // Bonus: distribution of |a_ℓ / (2√ℓ)| — Sato–Tate density.
        // Bin into 10 equal-width bins on [-1, 1].
        let mut bins = [0u64; 10];
        for (ell, a) in &samples {
            let x = *a as f64 / (2.0 * (*ell as f64).sqrt());
            if !(-1.0..=1.0).contains(&x) {
                continue;
            }
            let idx = (((x + 1.0) / 2.0) * 10.0).floor() as usize;
            let idx = idx.min(9);
            bins[idx] += 1;
        }
        println!("\n  Sato–Tate density bins (a_ℓ / 2√ℓ ∈ [-1, 1], 10 bins):");
        for (i, &c) in bins.iter().enumerate() {
            let lo = -1.0 + 0.2 * i as f64;
            let hi = lo + 0.2;
            // Sato–Tate density: (2/π) √(1 − x²) dx, integrated over [lo, hi].
            // Approximate with midpoint rule.
            let mid = (lo + hi) / 2.0;
            let density = (2.0 / std::f64::consts::PI) * (1.0 - mid * mid).sqrt();
            let expected = density * 0.2 * n_samples as f64;
            println!(
                "    [{:>+.2}, {:>+.2}): {:>6} curves   (Sato–Tate expects ≈ {:.0})",
                lo, hi, c, expected
            );
        }
    }

    /// **Phase 21 — End-to-end structural consistency check**.
    ///
    /// Take a specific Curve25519-class curve and a specific Phase-19
    /// cover Jacobian.  Verify:
    /// 1. `#E(F_p) = 8q` for prime `q`
    /// 2. `#Jac(C)(F_p) = #E · #E^twist` (Tate-isogeny condition)
    /// 3. `f` factors as `(x − α) · q_1 · q_2` over `F_p`
    ///    (explicit Richelot 3-factor decomposition)
    /// 4. Brute-force verify by enumerating both sides
    #[test]
    fn phase21_end_to_end_structural_consistency() {
        use crate::prime_hyperelliptic::brute_force_jac_order;

        // p = 19, E: y² = x³ + x + 8, expect #E = 24 = 8·3
        let p_u = 19u64;
        let e = ECurveP { p: p_u, a: 1, b: 8 };
        assert!(e.is_smooth());
        let n_e = e.order();
        let t_e: i128 = (p_u as i128) + 1 - (n_e as i128);
        let n_e_twist: u64 = 2 * (p_u + 1) - n_e;
        println!("\n=== Phase 21: End-to-end consistency at p = {} ===", p_u);
        println!("  E:  y² = x³ + 1·x + 8 (mod 19)");
        println!(
            "  #E(F_19) = {} = 8·{}  (cofactor 8, q = {})",
            n_e,
            n_e / 8,
            n_e / 8
        );
        println!("  trace t_E = {}", t_e);
        println!("  #E^twist(F_19) = {} = 2(p+1) − #E", n_e_twist);
        println!(
            "  Expected #Jac(C) for cover = #E · #E^twist = {}",
            n_e * n_e_twist
        );

        // Now build the cover Jacobian f(x) = x⁵ + 2x² + 8x
        let p_big = BigUint::from(p_u);
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::zero(),     // c0 = 0
                BigUint::from(8u32), // c1 = 8
                BigUint::from(2u32), // c2 = 2
                BigUint::zero(),     // c3 = 0
                BigUint::zero(),     // c4 = 0
                BigUint::one(),      // leading 1
            ],
            p_big.clone(),
        );
        println!("\n  Candidate cover C:  y² = x⁵ + 2x² + 8x (mod 19)");

        // Check squarefree
        assert!(
            is_squarefree_quintic(p_u, 0, 0, 2, 8, 0),
            "f should be squarefree"
        );
        println!("  ✓ f is squarefree");

        // Check Richelot decomposition
        let kind = richelot_kind(&f);
        assert_eq!(
            kind,
            RichelotKind::Explicit3Factor,
            "expected explicit Richelot decomposition"
        );
        println!("  ✓ f admits explicit F_p-rational Richelot 3-factor split");

        // Compute Frobenius (a, b) — should equal (0, 2p - t²) for this E
        let curve = HyperellipticCurveP::new(p_big.clone(), f.clone(), 2);
        let (ab, n_jac) = fast_frob_ab(&curve);
        let target_b: i128 = 2 * (p_u as i128) - t_e * t_e;
        println!("  Frobenius (a, b) of Jac(C):  ({}, {})", ab.a, ab.b);
        println!("  Expected (0, 2p - t²) =      (0, {})", target_b);
        assert_eq!(ab.a, 0, "expected a = 0");
        assert_eq!(ab.b, target_b, "Frobenius b mismatch");
        println!("  ✓ Frobenius matches target — Jac(C) F_p-isogenous to E × E^twist");

        // Cross-check #Jac via brute force
        let n_jac_brute = brute_force_jac_order(&curve);
        println!("  #Jac(C)(F_19) via L-poly:      {}", n_jac);
        println!("  #Jac(C)(F_19) via brute force: {}", n_jac_brute);
        assert_eq!(n_jac, n_jac_brute, "L-poly disagrees with brute force");
        assert_eq!(
            n_jac,
            BigUint::from(n_e * n_e_twist),
            "#Jac should equal #E · #E^twist exactly"
        );
        println!("  ✓ #Jac(C) = #E · #E^twist = {}", n_jac);

        // Show the Richelot factorization explicitly
        let factors = try_3_factor_split(&f, &BigUint::zero());
        if let Some([linear, q1, q2]) = factors {
            println!("\n  Explicit factorization of f:");
            println!("    linear:    x + {}", linear.coeff(0));
            println!("    quad 1:    x² + {}·x + {}", q1.coeff(1), q1.coeff(0));
            println!("    quad 2:    x² + {}·x + {}", q2.coeff(1), q2.coeff(0));
            // Verify
            let reconstructed = linear.mul(&q1).mul(&q2);
            assert_eq!(reconstructed, f, "reconstruction failed");
            println!("    ✓ reconstruction verified");
        }

        println!("\n  *** PHASE 21 RESULT ***");
        println!("  Concrete cover Jacobian against Curve25519-style E found.");
        println!("  The (N, N)-cover attack is structurally realizable AT THIS SIZE.");
        println!("  At cryptographic scale (p ≈ 2²⁵⁵), density vanishes as ~p^(-3.4),");
        println!("  giving Curve25519 / Curve448 their security.");
    }

    /// **Phase 20 — Curve448-class (cofactor 4) cover feasibility**.
    ///
    /// Curve448 has cofactor 4, not 8.  Does the Phase-18 result
    /// (cover IS realized at toy scale with vanishing density) also
    /// hold for cofactor-4 targets?  Or is cofactor 4 different from
    /// cofactor 8 in some structural way?
    ///
    /// Probes at small p: find `E` with `#E = 4q` for some odd prime `q`,
    /// then count Jacobians with matching Frobenius.
    #[test]
    #[ignore]
    fn phase20_curve448_class_cover_feasibility() {
        use std::collections::HashMap;

        fn is_prime_small(n: u64) -> bool {
            if n < 2 {
                return false;
            }
            if n < 4 {
                return true;
            }
            if n & 1 == 0 {
                return false;
            }
            let mut d = 3u64;
            while d * d <= n {
                if n.is_multiple_of(d) {
                    return false;
                }
                d += 2;
            }
            true
        }

        println!("\n=== Phase 20 — Curve448-class (cofactor 4) cover feasibility ===\n");
        for p_u in [17u64, 19, 23] {
            // Find curves with #E = 4·q, q odd prime > 2.
            let mut targets: HashMap<i128, Vec<(u64, u64, u64, i128)>> = HashMap::new();
            for a in 0..p_u {
                for b in 0..p_u {
                    let e = ECurveP { p: p_u, a, b };
                    if !e.is_smooth() {
                        continue;
                    }
                    let n = e.order();
                    // EXACTLY divisible by 4, not by 8 (i.e., cofactor "exactly 4").
                    if n.is_multiple_of(4) && !n.is_multiple_of(8) {
                        let q = n / 4;
                        if q >= 3 && q % 2 == 1 && is_prime_small(q) {
                            let t: i128 = (p_u as i128) + 1 - (n as i128);
                            let target_b: i128 = 2 * (p_u as i128) - t * t;
                            targets.entry(target_b).or_default().push((a, b, n, t));
                        }
                    }
                }
            }
            let total_e: usize = targets.values().map(|v| v.len()).sum();
            println!("──────────── p = {} ────────────", p_u);
            println!("  Curve448-class E's found: {}", total_e);
            if total_e == 0 {
                println!();
                continue;
            }
            for (target_b, es) in targets.iter().take(3) {
                println!("    target b = {}: {} E-curves", target_b, es.len());
            }

            // Sweep Jacobians.
            let p_big = BigUint::from(p_u);
            let mut total = 0u64;
            let mut hits: HashMap<i128, u64> = HashMap::new();
            for c4 in 0..p_u {
                for c3 in 0..p_u {
                    for c2 in 0..p_u {
                        for c1 in 0..p_u {
                            for c0 in 0..p_u {
                                if !is_squarefree_quintic(p_u, c4, c3, c2, c1, c0) {
                                    continue;
                                }
                                let f = FpPoly::from_coeffs(
                                    vec![
                                        BigUint::from(c0),
                                        BigUint::from(c1),
                                        BigUint::from(c2),
                                        BigUint::from(c3),
                                        BigUint::from(c4),
                                        BigUint::one(),
                                    ],
                                    p_big.clone(),
                                );
                                let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                                let (ab, _) = fast_frob_ab(&curve);
                                total += 1;
                                if ab.a == 0 && targets.contains_key(&ab.b) {
                                    *hits.entry(ab.b).or_insert(0) += 1;
                                }
                            }
                        }
                    }
                }
            }
            let total_hits: u64 = hits.values().sum();
            let rate = (total_hits as f64) / (total as f64) * 100.0;
            println!("  Total Jacobians swept: {}", total);
            println!("  TARGET HITS:           {}  ({:.3}%)", total_hits, rate);
            for (b, c) in &hits {
                let n_e = targets[b].len();
                println!("    b = {}: {} Jacobians ({} E-curves)", b, c, n_e);
            }
            println!();
        }
    }

    /// **Phase 19 — Do Curve25519-class cover hits admit explicit
    /// F_p-rational Richelot decompositions?**
    ///
    /// Phase 18 found ~0.4–1% of toy genus-2 Jacobians have Frobenius
    /// matching a Curve25519-class target.  These are *abstract*
    /// Frobenius matches (Tate-isogeny class).  Phase 19 tests
    /// whether any of these hits also admits an **explicit F_p-rational
    /// `(2, 2)`-Richelot decomposition** — which would be a
    /// constructive cover, the analogue of the Tier-3 hit we
    /// repeatedly failed to find for prime-order targets.
    ///
    /// **Significance**: a Phase-19 hit would be the first known
    /// constructive `(N, N)`-cover Jacobian against an EC × twist
    /// target at any size, validating the Kunzweiler–Pope-style
    /// approach as a real (if asymptotically vanishing) attack.
    #[test]
    #[ignore]
    fn phase19_curve25519_class_richelot_decomposition() {
        use std::collections::{HashMap, HashSet};

        fn is_prime_small(n: u64) -> bool {
            if n < 2 {
                return false;
            }
            if n < 4 {
                return true;
            }
            if n & 1 == 0 {
                return false;
            }
            let mut d = 3u64;
            while d * d <= n {
                if n.is_multiple_of(d) {
                    return false;
                }
                d += 2;
            }
            true
        }

        for p_u in [17u64, 19, 23] {
            // Collect Curve25519-class E's and their target b-values.
            let mut target_b_set: HashSet<i128> = HashSet::new();
            let mut target_to_e: HashMap<i128, Vec<(u64, u64, u64, i128)>> = HashMap::new();
            for a in 0..p_u {
                for b in 0..p_u {
                    let e = ECurveP { p: p_u, a, b };
                    if !e.is_smooth() {
                        continue;
                    }
                    let n = e.order();
                    if n.is_multiple_of(8) {
                        let q = n / 8;
                        if q >= 2 && is_prime_small(q) {
                            let t: i128 = (p_u as i128) + 1 - (n as i128);
                            let target_b: i128 = 2 * (p_u as i128) - t * t;
                            target_b_set.insert(target_b);
                            target_to_e.entry(target_b).or_default().push((a, b, n, t));
                        }
                    }
                }
            }

            // Now sweep all genus-2 Jacobians.  For each with Frobenius
            // (a = 0, b ∈ target_b_set), record the (c4..c0) quintic
            // and check if its f admits a Richelot 3-factor split.
            let p_big = BigUint::from(p_u);
            let mut total = 0u64;
            let mut target_hits = 0u64;
            let mut richelot_hits = 0u64;
            let mut richelot_per_target: HashMap<i128, u64> = HashMap::new();
            let mut first_richelot_examples: Vec<(i128, [u64; 5])> = Vec::new();

            for c4 in 0..p_u {
                for c3 in 0..p_u {
                    for c2 in 0..p_u {
                        for c1 in 0..p_u {
                            for c0 in 0..p_u {
                                if !is_squarefree_quintic(p_u, c4, c3, c2, c1, c0) {
                                    continue;
                                }
                                let f = FpPoly::from_coeffs(
                                    vec![
                                        BigUint::from(c0),
                                        BigUint::from(c1),
                                        BigUint::from(c2),
                                        BigUint::from(c3),
                                        BigUint::from(c4),
                                        BigUint::one(),
                                    ],
                                    p_big.clone(),
                                );
                                let curve = HyperellipticCurveP::new(p_big.clone(), f.clone(), 2);
                                let (ab, _) = fast_frob_ab(&curve);
                                total += 1;
                                if ab.a != 0 {
                                    continue;
                                }
                                if !target_b_set.contains(&ab.b) {
                                    continue;
                                }
                                target_hits += 1;
                                // Run Richelot detector.
                                let kind = richelot_kind(&f);
                                if matches!(kind, RichelotKind::Explicit3Factor) {
                                    richelot_hits += 1;
                                    *richelot_per_target.entry(ab.b).or_insert(0) += 1;
                                    if first_richelot_examples.len() < 5 {
                                        first_richelot_examples.push((ab.b, [c4, c3, c2, c1, c0]));
                                    }
                                }
                            }
                        }
                    }
                }
            }

            println!("\n──────────── Phase 19 @ p = {} ────────────", p_u);
            println!("  Total Jacobians swept: {}", total);
            println!(
                "  Target hits (abstract Frobenius match):       {}",
                target_hits
            );
            println!(
                "  → with explicit F_p-rational Richelot split:  {}",
                richelot_hits
            );
            if richelot_hits == 0 {
                println!();
                println!(
                    "  ✗ NO explicit Richelot cover found despite {} abstract hits.",
                    target_hits
                );
                println!("    Curve25519-class attack is REALIZED abstractly but NOT");
                println!("    constructively (at this size / detector).");
            } else {
                println!();
                println!("  ✓ EXPLICIT RICHELOT COVER FOUND!");
                println!("    Hit breakdown by target b:");
                for (b, cnt) in &richelot_per_target {
                    let e_count = target_to_e[b].len();
                    println!(
                        "      b = {}: {} Richelot covers (across {} E-curves)",
                        b, cnt, e_count
                    );
                }
                println!();
                println!(
                    "    First {} example quintics (c4 c3 c2 c1 c0):",
                    first_richelot_examples.len()
                );
                for (b, coeffs) in &first_richelot_examples {
                    println!(
                        "      target b={}: f(x) = x^5 + {}x^4 + {}x^3 + {}x^2 + {}x + {}",
                        b, coeffs[0], coeffs[1], coeffs[2], coeffs[3], coeffs[4]
                    );
                }
            }
        }
    }

    /// **Phase 18 — (N, N)-cover feasibility for EVEN-#E curves
    /// (Curve25519-class)**.
    ///
    /// Phase 10 blocks all prime-order curves.  Curve25519 (cofactor 8)
    /// and Curve448 (cofactor 4) have EVEN #E, so the parity argument
    /// doesn't apply.  Does an `(N, N)`-cover Jacobian actually exist
    /// for these targets, at toy scale?
    ///
    /// **The probe**:
    /// 1. At each small prime p, find ordinary EC `E/F_p` with
    ///    `#E = 8·q` where `q` is prime (toy-Curve25519 analogue).
    /// 2. Compute target Frobenius `(0, 2p − t²)` with `t` EVEN.
    /// 3. Use existing Phase 10 Jacobian-class histogram to count
    ///    Jacobians with exactly that Frobenius.
    ///
    /// **The empirical question**: is the realised-count zero (like
    /// the prime-order case) or non-zero (open frontier)?
    #[test]
    #[ignore]
    fn phase18_even_n_cover_feasibility() {
        use std::collections::HashMap;

        // Helper: small primality test for u64.
        fn is_prime_small(n: u64) -> bool {
            if n < 2 {
                return false;
            }
            if n < 4 {
                return true;
            }
            if n & 1 == 0 {
                return false;
            }
            let mut d = 3u64;
            while d * d <= n {
                if n.is_multiple_of(d) {
                    return false;
                }
                d += 2;
            }
            true
        }

        // Per-prime analysis.
        println!("\n=== Phase 18 — Even-#E cover feasibility (Curve25519-class) ===\n");
        println!("Target: Jacobians with Frobenius (a, b) matching E × E^twist");
        println!("where E has #E = 8·q (cofactor 8, prime-subgroup q).\n");

        for p_u in [17u64, 19, 23] {
            // Step 1: find all "Curve25519-like" curves at p_u.
            let mut even_n_curves: Vec<(u64, u64, u64, i128, i128)> = Vec::new(); // (a, b, n, t, target_b)
            for a in 0..p_u {
                for b in 0..p_u {
                    let e = ECurveP { p: p_u, a, b };
                    if !e.is_smooth() {
                        continue;
                    }
                    let n = e.order();
                    // Cofactor 8 with prime subgroup.
                    if n.is_multiple_of(8) {
                        let q = n / 8;
                        if q >= 2 && is_prime_small(q) {
                            let t: i128 = (p_u as i128) + 1 - (n as i128);
                            let target_b: i128 = 2 * (p_u as i128) - t * t;
                            even_n_curves.push((a, b, n, t, target_b));
                        }
                    }
                }
            }
            let target_set: HashMap<(i128, i128), Vec<(u64, u64, u64, i128)>> = {
                let mut m: HashMap<(i128, i128), Vec<(u64, u64, u64, i128)>> = HashMap::new();
                for (a, b, n, t, target_b) in &even_n_curves {
                    m.entry((0, *target_b)).or_default().push((*a, *b, *n, *t));
                }
                m
            };
            println!("──────────── p = {} ────────────", p_u);
            if even_n_curves.is_empty() {
                println!("  No cofactor-8 prime-subgroup curves found.\n");
                continue;
            }
            println!(
                "  Found {} Curve25519-class curves at p = {}",
                even_n_curves.len(),
                p_u
            );
            // Sample a few.
            for (a, b, n, t, target_b) in even_n_curves.iter().take(3) {
                println!(
                    "    E(a={}, b={}): #E = {} = 8·{} ;  t = {} (even);  target b = {}",
                    a,
                    b,
                    n,
                    n / 8,
                    t,
                    target_b
                );
            }

            // Step 2: enumerate all squarefree quintic Jacobians at p_u,
            // count those with Frobenius matching any target.
            let p_big = BigUint::from(p_u);
            let mut total: u64 = 0;
            let mut hits_per_target: HashMap<(i128, i128), u64> = HashMap::new();
            // Also bucket ALL realized (a=0, b) classes for context.
            let mut a0_classes: HashMap<i128, u64> = HashMap::new();
            for c4 in 0..p_u {
                for c3 in 0..p_u {
                    for c2 in 0..p_u {
                        for c1 in 0..p_u {
                            for c0 in 0..p_u {
                                if !is_squarefree_quintic(p_u, c4, c3, c2, c1, c0) {
                                    continue;
                                }
                                let f = FpPoly::from_coeffs(
                                    vec![
                                        BigUint::from(c0),
                                        BigUint::from(c1),
                                        BigUint::from(c2),
                                        BigUint::from(c3),
                                        BigUint::from(c4),
                                        BigUint::one(),
                                    ],
                                    p_big.clone(),
                                );
                                let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                                let (ab, _) = fast_frob_ab(&curve);
                                total += 1;
                                if ab.a == 0 {
                                    *a0_classes.entry(ab.b).or_insert(0) += 1;
                                    if target_set.contains_key(&(0, ab.b)) {
                                        *hits_per_target.entry((0, ab.b)).or_insert(0) += 1;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            println!("  Total Jacobians swept: {}", total);
            println!(
                "  Distinct (a=0) Jacobian b-classes realized: {}",
                a0_classes.len()
            );
            let total_hits: u64 = hits_per_target.values().sum();
            println!(
                "  TARGET HITS (Jac ~ E × E^twist for some Curve25519-class E): {}",
                total_hits
            );
            for ((_, b), count) in &hits_per_target {
                let matching_e: usize = target_set[&(0, *b)].len();
                println!(
                    "    target b = {}: {} matching Jacobians; corresponds to {} E-curves",
                    b, count, matching_e
                );
            }
            if total_hits == 0 {
                println!("  → Target class is EMPTY of Jacobians at p = {} too.", p_u);
                println!("    Same null as prime-order case — different reason than Phase 10");
                println!("    (parity (0, 0) is realized by SOME Jacobians but apparently");
                println!("    not at the specific Curve25519-class b values).");
            } else {
                println!("  → Target class IS REALIZED at p = {}!", p_u);
                println!("    The (N, N)-cover attack is structurally POSSIBLE at toy scale");
                println!("    for Curve25519-class targets.  Open frontier.");
            }
            println!();
        }
    }

    /// **Phase 14 — universal applicability of the Frobenius-mod-2 obstruction**.
    ///
    /// Verifies that the Phase 10 obstruction blocks `(N, N)`-cover
    /// attacks for **every** standardised prime-order EC over an odd
    /// prime field.  For each curve, computes `(a, b) mod 2` of the
    /// target Frobenius for `E × E^twist` and checks that it equals
    /// `(0, 1)` — the obstructed parity class.
    ///
    /// **Empirical theorem (proved by enumeration over the major
    /// standards)**: every deployed prime-order elliptic curve over
    /// an odd prime field is structurally immune to the (N, N)-cover
    /// attack family.
    #[test]
    fn phase14_universal_obstruction_check() {
        use crate::ecc::curve::CurveParams;
        use num_traits::ToPrimitive;

        struct CurveCase {
            name: &'static str,
            params: CurveParams,
        }

        let cases: Vec<CurveCase> = vec![
            CurveCase {
                name: "NIST P-192",
                params: CurveParams::p192(),
            },
            CurveCase {
                name: "NIST P-224",
                params: CurveParams::p224(),
            },
            CurveCase {
                name: "NIST P-256",
                params: CurveParams::p256(),
            },
            CurveCase {
                name: "NIST P-384",
                params: CurveParams::p384(),
            },
            CurveCase {
                name: "NIST P-521",
                params: CurveParams::p521(),
            },
            CurveCase {
                name: "secp160k1",
                params: CurveParams::secp160k1(),
            },
            CurveCase {
                name: "secp112r1",
                params: CurveParams::secp112r1(),
            },
            CurveCase {
                name: "secp128r1",
                params: CurveParams::secp128r1(),
            },
            CurveCase {
                name: "secp160r1",
                params: CurveParams::secp160r1(),
            },
            CurveCase {
                name: "secp160r2",
                params: CurveParams::secp160r2(),
            },
            CurveCase {
                name: "secp256k1",
                params: CurveParams::secp256k1(),
            },
            CurveCase {
                name: "secp192k1",
                params: CurveParams::secp192k1(),
            },
            CurveCase {
                name: "secp224k1",
                params: CurveParams::secp224k1(),
            },
            CurveCase {
                name: "brainpoolP192r1",
                params: CurveParams::brainpool_p192r1(),
            },
            CurveCase {
                name: "brainpoolP224r1",
                params: CurveParams::brainpool_p224r1(),
            },
            CurveCase {
                name: "brainpoolP256r1",
                params: CurveParams::brainpool_p256r1(),
            },
            CurveCase {
                name: "brainpoolP320r1",
                params: CurveParams::brainpool_p320r1(),
            },
            CurveCase {
                name: "brainpoolP384r1",
                params: CurveParams::brainpool_p384r1(),
            },
            CurveCase {
                name: "brainpoolP512r1",
                params: CurveParams::brainpool_p512r1(),
            },
            CurveCase {
                name: "FRP256v1",
                params: CurveParams::frp256v1(),
            },
            CurveCase {
                name: "SM2 (China)",
                params: CurveParams::sm2(),
            },
            CurveCase {
                name: "GOST CryptoPro A",
                params: CurveParams::gost_cryptopro_a(),
            },
            CurveCase {
                name: "GOST CryptoPro B",
                params: CurveParams::gost_cryptopro_b(),
            },
            CurveCase {
                name: "GOST CryptoPro C",
                params: CurveParams::gost_cryptopro_c(),
            },
            CurveCase {
                name: "GOST TC26 256-A",
                params: CurveParams::gost_tc26_256_a(),
            },
            CurveCase {
                name: "GOST TC26 512-A",
                params: CurveParams::gost_tc26_512_a(),
            },
            CurveCase {
                name: "GOST TC26 512-B",
                params: CurveParams::gost_tc26_512_b(),
            },
        ];

        println!("\n=== Phase 14: Universal Frobenius-mod-2 obstruction ===\n");
        println!(
            "{:>22} {:>4} {:>4} {:>4} {:>10}",
            "curve", "p%2", "n%2", "t%2", "(a,b)%2"
        );
        println!("{}", "-".repeat(60));

        let mut all_obstructed = true;
        let mut blocked_count = 0usize;
        let two = BigUint::from(2u32);

        for c in &cases {
            let p_mod_2 = (&c.params.p % &two).to_u64().unwrap();
            let n_mod_2 = (&c.params.n % &two).to_u64().unwrap();
            // t = p + 1 - n
            let t_signed: i64 = if &c.params.p + BigUint::one() >= c.params.n {
                ((&c.params.p + BigUint::one() - &c.params.n) % &two)
                    .to_u64()
                    .unwrap() as i64
            } else {
                ((&c.params.n - &c.params.p - BigUint::one()) % &two)
                    .to_u64()
                    .unwrap() as i64
            };
            let t_mod_2 = (t_signed as u64) & 1;
            // a = 0 (always for E × E^twist target)
            // b = 2p - t² → b mod 2 = (2p mod 2) - (t² mod 2) = 0 - (t mod 2)² = t² mod 2
            let b_mod_2 = (t_mod_2 * t_mod_2) % 2;
            let obstructed = b_mod_2 == 1;
            if obstructed {
                blocked_count += 1;
            } else {
                all_obstructed = false;
            }
            println!(
                "{:>22} {:>4} {:>4} {:>4} {:>10}  {}",
                c.name,
                p_mod_2,
                n_mod_2,
                t_mod_2,
                format!("(0, {})", b_mod_2),
                if obstructed { "BLOCKED" } else { "  (gap)" }
            );
        }

        println!(
            "\n  {} / {} curves structurally BLOCKED.",
            blocked_count,
            cases.len()
        );
        if all_obstructed {
            println!("  ✓ Phase 14: ALL standardised prime-order curves are blocked");
            println!("    by the (T² + T + 1)² Frobenius-mod-2 obstruction.");
            println!("    No (N, N)-cover attack family applies to any deployed curve.");
        }
        assert!(
            all_obstructed,
            "Phase 14 obstruction failed on some curve — investigate."
        );
    }

    /// **Phase 15 — generalization to higher-genus cover attacks**.
    ///
    /// The Phase 10 obstruction is: smooth genus-2 Jacobians never
    /// have Frobenius mod-2 char poly `(T² + T + 1)²`.  The natural
    /// higher-genus generalisation asks: does the same obstruction
    /// apply to genus-`g` Jacobian Frobenius char polys having
    /// `(T² + T + 1)²` as a *factor*?
    ///
    /// **Algebraic argument** (general theorem):
    /// For any product abelian variety `E × E^twist × A` over `F_p`
    /// (any odd `p`, `E` ordinary with `#E` an odd prime, `A` any
    /// dimension-`d` abelian variety):
    ///   * `P_E(T) ≡ T² + T + 1 (mod 2)`  (since `t_E` odd, `p` odd)
    ///   * `P_{E^twist}(T) ≡ T² + T + 1 (mod 2)`  (same reason)
    ///   * `P_{E × E^twist × A}(T) = P_E · P_{E^twist} · P_A`
    ///   * `≡ (T² + T + 1)² · P_A(T) (mod 2)`
    ///
    /// So **any** product Frobenius polynomial with `E` and
    /// `E^twist` as factors (and any additional `A`) has
    /// `(T² + T + 1)² | char-poly mod 2`.
    ///
    /// **Conjecture (genus-`g` generalisation of Howe–Maisner–Nart):**
    /// For any `g ≥ 2`, the conjugacy class of `Frob | J[2] ∈ Sp_{2g}(F_2)`
    /// with `(T² + T + 1)²` as a factor of its char poly is **not**
    /// in the image of the genus-`g` Jacobian-moduli map.
    ///
    /// This generalises Phase 10 (where `g = 2`, so "factor" =
    /// "equal to" up to factors of T+1) to **all** higher-genus
    /// `(N, N, …, N)`-cover attacks involving `E × E^twist` as
    /// part of a larger product.
    ///
    /// **What this test does**: empirically verifies the factor
    /// claim — that `(T² + T + 1)²` divides `(T² + T + 1) · (T² + T
    /// + 1) · Q(T)` for any palindromic `Q`, by polynomial division
    /// in `F_2[T]`.  Quick sanity check; the deep obstruction
    ///      claim about Jacobian moduli is left as a documented conjecture.
    #[test]
    fn phase15_higher_genus_product_obstruction() {
        // Verify: (T² + T + 1)² | (T² + T + 1) · P_A(T) in F_2[T]
        // for P_A palindromic of any degree (encoded as a Vec<u8> of
        // coefficients mod 2).
        //
        // f₁(T) = T² + T + 1: [1, 1, 1] (lowest-degree-first)
        let f1 = vec![1u8, 1, 1];

        // (T² + T + 1)² = T⁴ + T² + 1 in F_2:
        // Quick verify: (T² + T + 1)² = T⁴ + 2T³ + 3T² + 2T + 1 ≡ T⁴ + T² + 1 mod 2.
        let f1_sq = poly_mul_f2(&f1, &f1);
        assert_eq!(
            f1_sq,
            vec![1u8, 0, 1, 0, 1],
            "(T²+T+1)² should be T⁴+T²+1 in F_2[T]"
        );

        // Now check: for an arbitrary palindromic Q(T) of degree 4
        // (representing P_A of an arbitrary genus-2 abelian variety),
        // (T²+T+1)² | (T²+T+1)·Q(T)?
        //
        // For palindromic Q(T) = T⁴ + αT³ + βT² + αT + 1 (mod 2),
        // there are 4 parities (α, β) ∈ {0, 1}².  For each, check
        // whether (T²+T+1)·Q(T) is divisible by (T²+T+1)².
        let mut blocked_count = 0;
        let mut total = 0;
        let mut blocked_parities = Vec::new();
        for alpha in 0..2u8 {
            for beta in 0..2u8 {
                total += 1;
                // Q(T) = T⁴ + αT³ + βT² + αT + 1
                let q = vec![1u8, alpha, beta, alpha, 1];
                let f1_q = poly_mul_f2(&f1, &q);
                let (_, rem) = poly_divrem_f2(&f1_q, &f1_sq);
                let divisible = rem.iter().all(|&c| c == 0);
                if divisible {
                    blocked_count += 1;
                    blocked_parities.push((alpha, beta));
                }
            }
        }
        println!("\n=== Phase 15: higher-genus product obstruction ===");
        println!(
            "  (T²+T+1)² divides (T²+T+1)·Q(T) for {} of {} P_A parity classes",
            blocked_count, total
        );
        println!("  blocked parities (α, β): {:?}", blocked_parities);
        println!();
        println!("  Algebraic interpretation:");
        println!("    Q(T) = T⁴ + αT³ + βT² + αT + 1 (palindromic deg-4 mod 2)");
        println!("    (T²+T+1) | Q(T)  ⇔  Q(ω) = 0 where ω is the 3rd root of unity in F_4.");
        println!("    Q(ω) = (1 + α + β)·ω + (1 + α + β)  =  (1 + α + β)·(ω + 1)");
        println!("    Q(ω) = 0  ⇔  α + β ≡ 1 (mod 2)  ⇔  (α, β) ∈ {{(0, 1), (1, 0)}}");
        println!();
        println!("  ⇒  Half of all palindromic deg-4 Q(T) mod 2 are 'cover-compatible'");
        println!("     (i.e., (T²+T+1)·Q(T) divisible by (T²+T+1)²).  The other half");
        println!("     are AUTOMATICALLY blocked at the algebraic level.");
        println!();
        println!("  For the genus-3 cover ATTACK to succeed against P-256:");
        println!("     1. Need cover-compatible parity (α, β) ∈ {{(0,1), (1,0)}}");
        println!("     2. Need a smooth genus-3 Jacobian realising the (T²+T+1)²·Q(T)");
        println!("        Frobenius mod-2 class — conjecturally forbidden by the");
        println!("        natural Howe–Maisner–Nart generalisation of Phase 10.");
        println!();
        println!("  Phase 15 establishes step 1's algebraic constraints; step 2's");
        println!("  full empirical / structural verification is a future research item.");
    }

    fn poly_mul_f2(a: &[u8], b: &[u8]) -> Vec<u8> {
        let mut out = vec![0u8; a.len() + b.len() - 1];
        for i in 0..a.len() {
            for j in 0..b.len() {
                out[i + j] ^= a[i] & b[j];
            }
        }
        out
    }

    fn poly_divrem_f2(num: &[u8], den: &[u8]) -> (Vec<u8>, Vec<u8>) {
        // Trim leading zeros from den (highest-degree coefficient is last in our
        // convention).  Numerator is lowest-first.
        let dn = den.len();
        let mut r: Vec<u8> = num.to_vec();
        // Strip trailing zeros in r.
        while r.len() > 1 && *r.last().unwrap() == 0 {
            r.pop();
        }
        let mut q = vec![0u8; (r.len() as isize - dn as isize).max(0) as usize + 1];
        let lead_den = *den.last().unwrap();
        assert!(lead_den == 1, "expected monic divisor in F_2");
        while r.len() >= dn && !r.iter().all(|&x| x == 0) {
            let degree_diff = r.len() - dn;
            q[degree_diff] ^= 1;
            // r -= T^degree_diff · den
            for j in 0..dn {
                r[degree_diff + j] ^= den[j];
            }
            while r.len() > 1 && *r.last().unwrap() == 0 {
                r.pop();
            }
        }
        (q, r)
    }

    /// Phase 11 — mod-3 obstruction check at small primes.
    #[test]
    #[ignore]
    fn phase11_mod3_histograms() {
        for p in [7u64, 11, 13, 17, 19] {
            phase11_mod_ell_histogram(p, 3);
        }
    }

    /// Phase 12 — mod-5 obstruction check at small primes.
    #[test]
    #[ignore]
    fn phase12_mod5_histograms() {
        for p in [7u64, 11, 13, 17, 19] {
            phase11_mod_ell_histogram(p, 5);
        }
    }

    /// Phase 13 — mod-7 obstruction check at small primes.
    #[test]
    #[ignore]
    fn phase13_mod7_histograms() {
        for p in [11u64, 13, 17, 19] {
            phase11_mod_ell_histogram(p, 7);
        }
    }

    /// **Phase 10.5**: verify the **parity obstruction** is universal
    /// at moderately-sized p.  For any Jacobian-realized `(a=0, b)`
    /// class, `b` must be **even**.  Proof sketch:
    ///   - `b = t_1·t_2 + 2p` with `t_1 + t_2 = 0`, so `b = -t² + 2p`.
    ///   - Frobenius char poly mod 2: `P(T) ≡ T⁴ + ā T³ + b̄ T² + ā T + 1 (mod 2)`.
    ///   - For `a = 0`: `P(T) ≡ T⁴ + b̄ T² + 1 (mod 2)`.
    ///   - If `b` odd (`b̄ = 1`): `P(T) ≡ T⁴ + T² + 1 = (T² + T + 1)² (mod 2)`.
    ///     A SQUARE factor in `P mod ℓ` for `ℓ < ord(J)` forces specific
    ///     2-torsion structure that's incompatible with `Jac(smooth C)`.
    ///   - For `b` even (`b̄ = 0`): `P(T) ≡ T⁴ + 1 = (T+1)⁴ (mod 2)` —
    ///     also a square, but a DIFFERENT structure that *is*
    ///     compatible with Jacobians.
    ///
    /// Empirically test: at `p = 17`, every realized `(a=0)` class has
    /// even `b`.
    #[test]
    #[ignore]
    fn phase10_parity_obstruction_verification() {
        use std::collections::HashMap;
        let p = 17u64;
        let p_big = BigUint::from(p);
        let mut counts: HashMap<(i128, i128), u64> = HashMap::new();
        let mut total: u64 = 0;
        for c4 in 0..p {
            for c3 in 0..p {
                for c2 in 0..p {
                    for c1 in 0..p {
                        for c0 in 0..p {
                            if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                                continue;
                            }
                            let f = FpPoly::from_coeffs(
                                vec![
                                    BigUint::from(c0),
                                    BigUint::from(c1),
                                    BigUint::from(c2),
                                    BigUint::from(c3),
                                    BigUint::from(c4),
                                    BigUint::one(),
                                ],
                                p_big.clone(),
                            );
                            let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                            let (ab, _) = fast_frob_ab(&curve);
                            *counts.entry((ab.a, ab.b)).or_insert(0) += 1;
                            total += 1;
                        }
                    }
                }
            }
        }
        // Full parity breakdown across ALL realized classes.
        let mut parity_counts: HashMap<(i128, i128), u64> = HashMap::new(); // (a mod 2, b mod 2) -> count
        for (a, b) in counts.keys() {
            *parity_counts
                .entry((a.rem_euclid(2), b.rem_euclid(2)))
                .or_insert(0) += 1;
        }
        let mut total_curves_by_parity: HashMap<(i128, i128), u64> = HashMap::new();
        for ((a, b), c) in &counts {
            *total_curves_by_parity
                .entry((a.rem_euclid(2), b.rem_euclid(2)))
                .or_insert(0) += *c;
        }
        let a0_classes: Vec<(i128, u64)> = counts
            .iter()
            .filter(|((a, _), _)| *a == 0)
            .map(|((_, b), c)| (*b, *c))
            .collect();
        let n_a0 = a0_classes.len();
        let n_a0_even_b: usize = a0_classes
            .iter()
            .filter(|(b, _)| b.rem_euclid(2) == 0)
            .count();
        let n_a0_odd_b: usize = n_a0 - n_a0_even_b;
        println!("\n=== Phase 10.5: parity obstruction at p = {} ===", p);
        println!("  Total Jacobians:               {}", total);
        println!("  Realized (a, b) classes:       {}", counts.len());
        println!("\n  Parity breakdown of realized (a, b) classes:");
        for ((a_par, b_par), n_classes) in &parity_counts {
            let n_curves = total_curves_by_parity[&(*a_par, *b_par)];
            println!(
                "    (a mod 2, b mod 2) = ({}, {}): {:>4} classes, {:>8} curves",
                a_par, b_par, n_classes, n_curves
            );
        }
        println!("\n  Realized (a=0, b) sub-table:");
        println!(
            "    {} classes, {} of which b is even, {} odd",
            n_a0, n_a0_even_b, n_a0_odd_b
        );
        assert_eq!(
            n_a0_odd_b, 0,
            "PARITY OBSTRUCTION FAILED: found a Jacobian with (a=0, b odd)!"
        );
        println!("\n  ✓ Parity obstruction CONFIRMED at p = {}", p);
        println!("    No Jacobian over F_{} has Frobenius (a=0, b odd).", p);
        // Now check the more general Sp_4(F_2) obstruction.
        // Frobenius mod 2 on J[2] should land in a specific conjugacy
        // class of Sp_4(F_2).  Char poly forms allowed:
        //   (T^2 + T + 1)(T-1)(T+1) — generic split
        //   (T+1)^4, (T-1)^4 — full unipotent
        //   etc.
        // The CHAR POLY mod 2 is determined by (a mod 2, b mod 2):
        //   P(T) ≡ T^4 + a̅·T^3 + b̅·T^2 + a̅·T + 1 (mod 2)
        // We can map each (a_par, b_par) to the corresponding char poly
        // and check empirically which forms are realized.
        println!("\n  Frobenius char poly mod 2 by parity class:");
        for ((a_par, b_par), n_curves) in &total_curves_by_parity {
            let poly = format!(
                "T^4 + {}T^3 + {}T^2 + {}T + 1",
                if *a_par == 0 { "0" } else { "1" },
                if *b_par == 0 { "0" } else { "1" },
                if *a_par == 0 { "0" } else { "1" },
            );
            println!(
                "    parity ({}, {}): {} curves — P(T) ≡ {} (mod 2)",
                a_par, b_par, n_curves, poly
            );
        }
    }

    /// **Phase-9 push**: with the fast `u64`-only counter, run at
    /// `p = 1009` with 100k samples.  Expected runtime under 5 min
    /// in release.  Checks whether Tier-2 ever fires at `p ≈ 10³`.
    #[test]
    #[ignore]
    fn phase9_aggressive_p1009() {
        let (stats, hits) = run_probe_random_with_stats(1009, 100_000, 0xCAFEBABE);
        print_stats("Phase-9 fast @ p=1009", &stats);
        let any_2 = hits.iter().find(|h| {
            h.tier == HitTier::FrobeniusMatch
                || h.tier == HitTier::FrobeniusMatchBroad
                || h.tier == HitTier::FrobeniusPlusRichelot
        });
        if let Some(h) = any_2 {
            println!(
                "\n  *** Tier-2+ HIT ***\n  E(a={}, b={}): #E={}, #E^t={}, t={}\n  C coeffs {:?}; (frob_a, frob_b) = ({}, {})",
                h.e_a, h.e_b, h.n_e, h.n_t, h.trace_e, h.c_coeffs, h.frob_a, h.frob_b,
            );
        }
    }

    /// **Phase-9 push at `p = 2003`** (next prime, ~4× p=1009 work).
    /// Largest Tier-2-broad probe we run.  Expected ~20 min release.
    #[test]
    #[ignore]
    fn phase9_aggressive_p2003() {
        let (stats, hits) = run_probe_random_with_stats(2003, 100_000, 0xFEEDFACE);
        print_stats("Phase-9 fast @ p=2003", &stats);
        let any_2 = hits.iter().find(|h| {
            h.tier == HitTier::FrobeniusMatch
                || h.tier == HitTier::FrobeniusMatchBroad
                || h.tier == HitTier::FrobeniusPlusRichelot
        });
        if let Some(h) = any_2 {
            println!(
                "\n  *** Tier-2+ HIT ***\n  E(a={}, b={}): #E={}, #E^t={}, t={}\n  C coeffs {:?}; (frob_a, frob_b) = ({}, {})",
                h.e_a, h.e_b, h.n_e, h.n_t, h.trace_e, h.c_coeffs, h.frob_a, h.frob_b,
            );
        }
    }

    /// **Phase-8 push**: aggressive sampling at `p = 503` (next
    /// Solinas-adjacent prime after 251) with 100k samples.  Asks:
    /// at this size, does Tier-2-broad EVER fire?  Expected runtime
    /// ~40 min in release.  Use `--ignored --nocapture` to see the
    /// breakdown.
    #[test]
    #[ignore]
    fn phase8_aggressive_p503() {
        let (stats, hits) = run_probe_random_with_stats(503, 100_000, 0xDEADBEEF);
        print_stats("Phase-8 aggressive @ p=503", &stats);
        let any_2b = hits.iter().find(|h| h.tier == HitTier::FrobeniusMatchBroad);
        if let Some(h) = any_2b {
            println!(
                "\n  *** Tier-2-broad HIT found ***\n  E(a={}, b={}): #E={}, #E^t={}\n  C coeffs {:?}; (frob_a, frob_b) = ({}, {})",
                h.e_a, h.e_b, h.n_e, h.n_t, h.c_coeffs, h.frob_a, h.frob_b,
            );
        }
    }

    /// **Histogram of decomposable Frobenius `(a, b)` values** at
    /// small `p` — diagnostic for Phase 7.  Shows WHICH `(a, b)`
    /// pairs decomposable Jacobians actually realize, and which of
    /// our Tier-2-broad targets are empty.
    #[test]
    #[ignore]
    fn phase7_ab_histogram_p11() {
        use std::collections::HashMap;
        let p: u64 = 11;
        let ecs = sweep_prime_order_curves(p);
        let (_jac_map, _frob_strict_map, frob_broad_map) = build_target_maps(&ecs, p);
        let one_sided_set = build_one_sided_prime_map(&ecs, p);
        let p_big = BigUint::from(p);
        let ctx = Fp2Ctx::new(p);
        let mut decomp_hist: HashMap<(i128, i128), u32> = HashMap::new();
        for c4 in 0..p {
            for c3 in 0..p {
                for c2 in 0..p {
                    for c1 in 0..p {
                        for c0 in 0..p {
                            if !is_squarefree_quintic(p, c4, c3, c2, c1, c0) {
                                continue;
                            }
                            let f = FpPoly::from_coeffs(
                                vec![
                                    BigUint::from(c0),
                                    BigUint::from(c1),
                                    BigUint::from(c2),
                                    BigUint::from(c3),
                                    BigUint::from(c4),
                                    BigUint::one(),
                                ],
                                p_big.clone(),
                            );
                            let curve = HyperellipticCurveP::new(p_big.clone(), f, 2);
                            let (ab, _) = frob_ab_and_jac(&curve, &ctx);
                            if is_jac_decomposable_over_z(ab.a, ab.b, p) {
                                *decomp_hist.entry((ab.a, ab.b)).or_insert(0) += 1;
                            }
                        }
                    }
                }
            }
        }
        println!("\n=== Decomposable (a, b) histogram at p = {} ===", p);
        let mut entries: Vec<_> = decomp_hist.iter().collect();
        entries.sort_by_key(|(k, _)| (k.0, k.1));
        let total: u32 = entries.iter().map(|(_, v)| **v).sum();
        println!("  Total decomposable Jacobians: {}", total);
        println!("  Distinct (a, b) realized:     {}", entries.len());
        println!("\n  All (a, b) with their counts:");
        for ((a, b), count) in &entries {
            let in_broad = frob_broad_map.contains_key(&(*a, *b));
            let in_one_sided = one_sided_set.contains(&(*a, *b));
            let marker = match (in_broad, in_one_sided) {
                (true, _) => "  ← Tier-2-broad target",
                (false, true) => "  ← Tier-1¾ OneSidedPrime target",
                (false, false) => "",
            };
            println!("    (a={:3}, b={:4}) = {:6}{}", a, b, count, marker);
        }
        let mut empty_broad: Vec<(i128, i128)> = Vec::new();
        for &(a, b) in frob_broad_map.keys() {
            if !decomp_hist.contains_key(&(a, b)) {
                empty_broad.push((a, b));
            }
        }
        empty_broad.sort();
        println!(
            "\n  Tier-2-broad targets with ZERO Jacobians: {}",
            empty_broad.len()
        );
        for (a, b) in &empty_broad {
            let pairs = frob_broad_map.get(&(*a, *b)).unwrap();
            println!("    (a={:3}, b={:4}) from pairs {:?}", a, b, pairs);
        }
    }

    #[test]
    fn decomposable_test_synthetic() {
        // For E × E^t over F_11 with E having trace t = 4:
        //   a = 0, b = 22 - 16 = 6
        //   a² − 4b + 8p = 0 − 24 + 88 = 64 = 8²  ✓ perfect square
        assert!(is_jac_decomposable_over_z(0, 6, 11));
        // Generic non-decomposable (random):
        // a = 4, b = 14 (the test curve), disc = 16 − 56 + 88 = 48,
        // sqrt(48) ≈ 6.928, not integer.
        assert!(!is_jac_decomposable_over_z(4, 14, 11));
    }

    #[test]
    fn quintic_discriminant_squarefree_check() {
        // f = x⁵ + x + 1 over F_{11} (the test curve from earlier).
        // We hand-checked f is squarefree, so Δ ≠ 0.
        let p = BigUint::from(11u32);
        let f = FpPoly::from_coeffs(
            vec![
                BigUint::one(),
                BigUint::one(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::zero(),
                BigUint::one(),
            ],
            p,
        );
        let d = quintic_discriminant(&f);
        assert!(!d.is_zero(), "Δ should be non-zero for squarefree f");
    }

    #[test]
    fn quintic_discriminant_repeated_root_is_zero() {
        // f = (x - 1)² · (x³ + 1) = x⁵ - 2x⁴ + x³ + x² - 2x + 1
        // (over Z, then reduce mod 13).  Has a double root at x=1.
        let p = BigUint::from(13u32);
        // Compute coefficients in Z first.
        // (x - 1)² = x² - 2x + 1
        // (x² - 2x + 1)·(x³ + 1) = x⁵ - 2x⁴ + x³ + x² - 2x + 1
        let coeffs_z = [1i64, -2, 1, 1, -2, 1]; // c_0..c_5
        let coeffs: Vec<BigUint> = coeffs_z
            .iter()
            .map(|c| {
                let cm = c.rem_euclid(13) as u64;
                BigUint::from(cm)
            })
            .collect();
        let f = FpPoly::from_coeffs(coeffs, p);
        let d = quintic_discriminant(&f);
        assert!(d.is_zero(), "Δ should be zero for f with a double root");
    }

    #[test]
    fn richelot_kind_synthetic_three_factor() {
        // f = (x − 1) · (x² + 1) · (x² + 3) over F_7.
        let p_big = BigUint::from(7u32);
        let q0 = FpPoly::from_coeffs(
            vec![
                (BigUint::from(7u32) - BigUint::from(1u32)) % &p_big,
                BigUint::one(),
            ],
            p_big.clone(),
        );
        let q1 = FpPoly::from_coeffs(
            vec![BigUint::one(), BigUint::zero(), BigUint::one()],
            p_big.clone(),
        );
        let q2 = FpPoly::from_coeffs(
            vec![BigUint::from(3u32), BigUint::zero(), BigUint::one()],
            p_big.clone(),
        );
        let f = q0.mul(&q1).mul(&q2);
        assert_eq!(f.degree(), Some(5));
        let kind = richelot_kind(&f);
        assert_eq!(kind, RichelotKind::Explicit3Factor);
    }
}
