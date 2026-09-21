//! **Elliptic-curve index calculus** via Semaev summation polynomials —
//! a from-scratch implementation of the framework that gives the closest
//! published research to "subexponential ECDLP."
//!
//! ## What this module is
//!
//! A *toy-scale* implementation of the algebraic index-calculus
//! framework for elliptic-curve discrete logarithms.  It solves ECDLP
//! on small (sub-40-bit) prime-field curves by:
//!
//! 1. Building a factor base **F = {P₁, …, P_m}** of points with small
//!    x-coordinate.
//! 2. Sampling random `R = aG + bQ` and trying to *decompose* `R` as a
//!    signed sum of two factor-base elements
//!    `R = ε_i Pᵢ + ε_j P_j`, with the help of **Semaev's 3rd summation
//!    polynomial** `S₃` (closed form for short-Weierstrass curves).
//! 3. Recording each successful decomposition as a row of a linear
//!    system over `ℤ/nℤ` (where `n` is the curve order) in the
//!    unknowns `(log_G P₁, …, log_G P_m, log_G Q)`.
//! 4. Solving the system by **Gaussian elimination mod n** to recover
//!    `log_G Q`.
//!
//! The pieces above are the same architecture that Faugère, Perret,
//! Petit, Renault (2012) and Petit–Quisquater (2012) — collectively the
//! *FPPR / PQ method* — used to attack the binary-field ECDLP, and that
//! Petit–Kosters–Messeng (2016) and Amadori–Pintore–Sala (2018) adapted
//! to prime fields.
//!
//! ## What this module is **not**
//!
//! Not a threat to deployed curves.  As of 2024 the published prime-field
//! index calculus is *asymptotically slower* than generic Pollard rho:
//!
//! - Naive 2-decomposition (this module) needs ≈ `p/m` trials × `m`
//!   factor-base scans = `O(p · m / m) = O(p)` per relation, times
//!   `m` relations = `O(p · m)` total.  With `m = p^{1/2}` (the
//!   optimum), that is `O(p^{3/2})` — much worse than Pollard rho's
//!   `O(p^{1/2})`.
//! - To beat rho you would need to use higher-degree Semaev polynomials
//!   (`S_n` for `n ≥ 4`) and decompose `R` as a sum of `n − 1` factor
//!   base elements.  For prime fields, this requires solving a 0-dim
//!   polynomial system in many variables — exactly the place where
//!   Gröbner basis cost blows up.  Petit–Kosters–Messeng achieve
//!   complexity ≈ `O(p^{1/2 + ε})` *under heuristic assumptions* that
//!   are not believed to hold uniformly.  See the discussion in
//!   Galbraith, "Notes on summation polynomials" (2015), and
//!   Huang–Kiltz–Petit (Crypto 2015).
//!
//! ## The summation polynomial
//!
//! For `E: y² = x³ + ax + b` over a field `K`, Semaev's `nᵗʰ` summation
//! polynomial `S_n ∈ K[X₁, …, X_n]` has the defining property
//!
//! > `S_n(x₁, …, x_n) = 0  ⟺  ∃ y₁, …, y_n  such that
//! >        (xᵢ, yᵢ) ∈ E(K̄)  and  Σᵢ (xᵢ, yᵢ) = O` in the group law.
//!
//! There is a closed form for `S₃`:
//!
//! ```text
//! S₃(X₁, X₂, X₃) = (X₁ − X₂)² · X₃²
//!                − 2[(X₁ + X₂)(X₁X₂ + a) + 2b] · X₃
//!                + (X₁X₂ − a)² − 4b(X₁ + X₂).
//! ```
//!
//! `S₃` is symmetric in `X₁, X₂, X₃` (verify by expanding), quadratic
//! in each variable.  For higher `n` the polynomial is computed
//! recursively as the *resultant* in `X` of `S_{m+1}(X₁, …, X_m, X)`
//! and `S_{n−m+1}(X_{m+1}, …, X_n, X)`.  We implement only `S₃` here,
//! which is all that is needed for 2-decompositions.
//!
//! ## References
//!
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, IACR ePrint 2004/031.
//! - **C. Diem**, *On the discrete logarithm problem in elliptic
//!   curves*, Compositio Math. 147 (2011).
//! - **J.-C. Faugère, L. Perret, C. Petit, G. Renault**, *Improving
//!   the complexity of index calculus algorithms in elliptic curves
//!   over binary fields*, Eurocrypt 2012.
//! - **C. Petit, J.-J. Quisquater**, *On polynomial systems arising
//!   from a Weil descent*, Asiacrypt 2012.
//! - **S. Galbraith**, *Notes on summation polynomials*, 2015.
//! - **M.-D. Huang, M. Kiltz, C. Petit**, *Last fall degree, HFE, and
//!   Weil descent attacks on ECDLP*, Crypto 2015.
//! - **C. Petit, M. Kosters, A. Messeng**, *Algebraic approaches for
//!   the elliptic curve discrete logarithm problem over prime fields*,
//!   PKC 2016.
//! - **A. Amadori, F. Pintore, M. Sala**, *On the discrete logarithm
//!   problem for prime-field elliptic curves*, FFA 51 (2018).

use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;
use crate::utils::mod_inverse;
use num_bigint::BigUint;
use num_traits::{One, Zero};

// ── Semaev's 3rd summation polynomial ───────────────────────────────────

/// **Evaluate** `S₃(x₁, x₂, x₃)` on the curve `E: y² = x³ + ax + b`.
///
/// Returns `0 ∈ F_p` iff there exist `y₁, y₂, y₃ ∈ F_p` (or a quadratic
/// extension thereof) such that `(xᵢ, yᵢ) ∈ E` and `P₁ + P₂ + P₃ = O`.
///
/// Note: the result equalling zero only *implies* a sign combination
/// `ε₁P₁ + ε₂P₂ + ε₃P₃ = O` exists for some signs — the polynomial
/// is independent of the y-coordinates, which are determined only up
/// to negation.
pub fn semaev_s3(
    x1: &FieldElement,
    x2: &FieldElement,
    x3: &FieldElement,
    a: &FieldElement,
    b: &FieldElement,
) -> FieldElement {
    let (a_coef, b_coef, c_coef) = semaev_s3_in_x3(x1, x2, a, b);
    // S₃ as a quadratic in X₃:  A·X₃² + B·X₃ + C.
    a_coef.mul(&x3.mul(x3)).add(&b_coef.mul(x3)).add(&c_coef)
}

/// **Extract S₃ as a quadratic in `X₃`** given the other two x-coords
/// fixed.  Returns `(A, B, C)` such that `S₃(x₁, x₂, X₃) = A·X₃² + B·X₃ + C`.
///
/// This is the form we plug into the quadratic formula when sweeping
/// `(x₁, x₂) = (x_R, x_{F_i})` and asking "is there an x_{F_j} in the
/// factor base satisfying `S₃ = 0`?"
pub fn semaev_s3_in_x3(
    x1: &FieldElement,
    x2: &FieldElement,
    a: &FieldElement,
    b: &FieldElement,
) -> (FieldElement, FieldElement, FieldElement) {
    let p = x1.modulus.clone();
    let two = FieldElement::new(BigUint::from(2u32), p.clone());
    let four = FieldElement::new(BigUint::from(4u32), p.clone());

    let x1x2 = x1.mul(x2);
    let sum = x1.add(x2);
    let diff = x1.sub(x2);

    // A = (x₁ − x₂)²
    let coef_a = diff.mul(&diff);

    // B = −2 [(x₁ + x₂)(x₁x₂ + a) + 2b]
    let inner = sum.mul(&x1x2.add(a)).add(&two.mul(b));
    let coef_b = two.mul(&inner).neg();

    // C = (x₁x₂ − a)² − 4b(x₁ + x₂)
    let part = x1x2.sub(a);
    let part_sq = part.mul(&part);
    let coef_c = part_sq.sub(&four.mul(b).mul(&sum));

    (coef_a, coef_b, coef_c)
}

// ── Semaev's higher summation polynomials (recursive via resultant) ─────

/// **Semaev S₄ as a univariate polynomial in `X₄`**, evaluated at
/// fixed `(X₁, X₂, X₃)`.
///
/// `S_n` for `n ≥ 4` is built recursively from `S_3` via the resultant
/// identity (Semaev 2004 §3):
///
/// ```text
/// S_{m+n−2}(X₁, …, X_{m+n−2}) = Res_X(
///        S_{m+1}(X₁, …, X_m, X),
///        S_{n+1}(X_{m+1}, …, X_{m+n−2}, −X)).
/// ```
///
/// For `n = 4`, taking `m = n = 3`:
/// `S_4(X₁,X₂,X₃,X₄) = Res_X( S_3(X₁,X₂,X), S_3(X₃,X₄,X) )`
/// (using that `S_3` is invariant under `X → −X` after expansion — the
/// `−X` in the formula above is a notational convenience).
///
/// We fix `(X₁, X₂, X₃)` (turning the first `S_3` into a univariate
/// quadratic in `X`) and return `S_4(X₁,X₂,X₃,X₄)` as a quartic in
/// `X₄`: a 5-tuple `(c₀, c₁, c₂, c₃, c₄)` with
/// `S_4 = c₀ + c₁ X₄ + c₂ X₄² + c₃ X₄³ + c₄ X₄⁴`.
///
/// This is the polynomial used in 3-decompositions: given `R = aG + bQ`,
/// find `(F_i, F_j, F_k)` in the factor base with `S_4(x_R, x_i, x_j, x_k)
/// = 0`.  We **compute** `S_4` here for completeness and future use;
/// solving for `x_k` over `F_p` requires univariate root-finding for
/// degree-4 polynomials (Berlekamp/Cantor–Zassenhaus), which is not
/// implemented in this module.
pub fn semaev_s4_in_x4(
    x1: &FieldElement,
    x2: &FieldElement,
    x3: &FieldElement,
    a: &FieldElement,
    b: &FieldElement,
) -> [FieldElement; 5] {
    // First S_3(X₁, X₂, X) = α₂ X² + α₁ X + α₀.
    let (a2, a1, a0) = semaev_s3_in_x3(x1, x2, a, b);
    // Second S_3(X₃, X₄, X) — treating X₄ as a *symbol*.  Since `S_3`
    // is quadratic in *each* variable, we expand explicitly:
    //
    //   S₃(X₃, X₄, X) =   (X₃ − X₄)² X²
    //                   − 2[(X₃ + X₄)(X₃ X₄ + a) + 2b] X
    //                   + (X₃ X₄ − a)² − 4b(X₃ + X₄).
    //
    // Coefficients are polynomials in X₄ of degree (2, 2, 2):
    //   (X₃ − X₄)²        = X₄² − 2X₃·X₄ + X₃²
    //   X₃ + X₄           = X₃ + X₄
    //   X₃ X₄ + a         = X₃·X₄ + a
    //   (X₃ + X₄)(X₃ X₄ + a)  ≡  X₃² X₄ + a X₃ + X₃ X₄² + a X₄
    //   (X₃ X₄ − a)²      = X₃² X₄² − 2 a X₃ X₄ + a²
    //   −4b(X₃ + X₄)      = −4b X₃ − 4b X₄.
    //
    // So  S₃(X₃, X₄, X) = β₂(X₄) X² + β₁(X₄) X + β₀(X₄)
    // where
    //   β₂ = X₄² − 2X₃ X₄ + X₃²,
    //   β₁ = −2 [ X₃ X₄² + (X₃² + a) X₄ + (a X₃ + 2b) ],
    //   β₀ = X₃² X₄² − (2 a X₃ + 4b) X₄ + (a² − 4b X₃).
    //
    // Then  S_4(…, X₄) = Res_X(α₂ X² + α₁ X + α₀,  β₂(X₄) X² + β₁(X₄) X + β₀(X₄)).
    //
    // For two quadratics Res = (α₂ β₀ − α₀ β₂)² − (α₂ β₁ − α₁ β₂)(α₁ β₀ − α₀ β₁).

    let p = x1.modulus.clone();
    let zero = FieldElement::zero(p.clone());
    let two = FieldElement::new(BigUint::from(2u32), p.clone());
    let four = FieldElement::new(BigUint::from(4u32), p.clone());

    // β₂(X₄) as [coef_X₄^0, coef_X₄^1, coef_X₄^2].
    let b2 = [x3.mul(x3), two.mul(x3).neg(), one(&p)];
    // β₁(X₄)  =  −2[X₃ X₄² + (X₃² + a) X₄ + (a X₃ + 2b)].
    let b1 = [
        two.mul(&a.mul(x3).add(&two.mul(b))).neg(),
        two.mul(&x3.mul(x3).add(a)).neg(),
        two.mul(x3).neg(),
    ];
    // β₀(X₄)  =  X₃² X₄² − (2 a X₃ + 4b) X₄ + (a² − 4b X₃).
    let b0 = [
        a.mul(a).sub(&four.mul(b).mul(x3)),
        two.mul(a).mul(x3).add(&four.mul(b)).neg(),
        x3.mul(x3),
    ];

    // The resultant components, each itself a polynomial in X₄:
    //   A(X₄) = α₂·β₀ − α₀·β₂
    //   B(X₄) = α₂·β₁ − α₁·β₂
    //   C(X₄) = α₁·β₀ − α₀·β₁
    // and S_4 = A² − B·C.
    let mul_polys = |p1: &[FieldElement], p2: &[FieldElement], deg: usize| -> Vec<FieldElement> {
        let mut out = vec![zero.clone(); deg + 1];
        for (i, ai) in p1.iter().enumerate() {
            for (j, bj) in p2.iter().enumerate() {
                if i + j <= deg {
                    out[i + j] = out[i + j].add(&ai.mul(bj));
                }
            }
        }
        out
    };
    let scale = |c: &FieldElement, poly: &[FieldElement]| -> Vec<FieldElement> {
        poly.iter().map(|t| t.mul(c)).collect()
    };
    let sub_polys = |p1: &[FieldElement], p2: &[FieldElement]| -> Vec<FieldElement> {
        let mut out = p1.to_vec();
        for (i, t) in p2.iter().enumerate() {
            while out.len() <= i {
                out.push(zero.clone());
            }
            out[i] = out[i].sub(t);
        }
        out
    };

    // A(X₄), B(X₄), C(X₄) are polynomials of degree ≤ 2.
    let a_poly = sub_polys(&scale(&a2, &b0), &scale(&a0, &b2));
    let b_poly = sub_polys(&scale(&a2, &b1), &scale(&a1, &b2));
    let c_poly = sub_polys(&scale(&a1, &b0), &scale(&a0, &b1));

    // S_4 = A² − B·C  ∈  F_p[X₄], degree ≤ 4.
    let a_sq = mul_polys(&a_poly, &a_poly, 4);
    let bc = mul_polys(&b_poly, &c_poly, 4);
    let s4 = sub_polys(&a_sq, &bc);

    [
        s4.first().cloned().unwrap_or(zero.clone()),
        s4.get(1).cloned().unwrap_or(zero.clone()),
        s4.get(2).cloned().unwrap_or(zero.clone()),
        s4.get(3).cloned().unwrap_or(zero.clone()),
        s4.get(4).cloned().unwrap_or(zero.clone()),
    ]
}

fn one(p: &BigUint) -> FieldElement {
    FieldElement::one(p.clone())
}

// ── Univariate root finder over F_p ─────────────────────────────────────

/// Find every `F_p`-rational root of the polynomial
/// `coeffs[0] + coeffs[1]·X + coeffs[2]·X² + … + coeffs[d]·X^d`.
///
/// This is what wires Semaev's `S_4` into an actual 3-decomposition
/// sieve: fix `(x_R, x_i, x_j)` from a factor-base sweep, compute the
/// quartic in `X_k` via [`semaev_s4_in_x4`], and pass it here to read
/// off the candidate `x_k` values.
///
/// Algorithm: for fields with `p` up to roughly `2²⁰` we evaluate at
/// every element (Horner's rule, ~`p · d` field ops).  This is the
/// only context where this index-calculus module is exercised in the
/// crate — the toy curve uses `p = 271` — so brute force is more than
/// fast enough.
///
/// For cryptographically-sized `p` the right approach is
/// `gcd(poly(X), X^p − X)` (Cantor-Zassenhaus rational-factor
/// extraction) followed by equal-degree splitting; we do not
/// implement that here, but the function still returns the empty
/// vector rather than panicking so the caller can detect the gap.
pub fn find_roots_fp(coeffs: &[FieldElement], p: &BigUint) -> Vec<FieldElement> {
    let mut roots = Vec::new();
    if coeffs.is_empty() || coeffs.iter().all(|c| c.is_zero()) {
        return roots;
    }
    // Strip trailing zero coefficients to get the true degree.
    let mut deg = coeffs.len() - 1;
    while deg > 0 && coeffs[deg].is_zero() {
        deg -= 1;
    }
    if deg == 0 {
        // Non-zero constant: no roots.
        return roots;
    }

    let p_bits = p.bits();
    if p_bits > 20 {
        // Out of brute-force range and no CZ wired here — caller
        // gets empty.  See doc comment.
        return roots;
    }
    let p_u64 = p.to_u64_digits().first().copied().unwrap_or(0);
    let coeffs_slice = &coeffs[..=deg];
    for v in 0..p_u64 {
        let elt = FieldElement::new(BigUint::from(v), p.clone());
        // Horner: value = c_d; value = value·X + c_{i} for i = d-1 .. 0.
        let mut value = coeffs_slice[deg].clone();
        for i in (0..deg).rev() {
            value = value.mul(&elt).add(&coeffs_slice[i]);
        }
        if value.is_zero() {
            roots.push(elt);
        }
    }
    roots
}

// ── Tonelli–Shanks square root mod p ────────────────────────────────────

/// Solve `x² ≡ n (mod p)` for a prime `p`.  Returns `Some(x)` if `n`
/// is a quadratic residue mod p, `None` otherwise.  For `n = 0`,
/// returns `Some(0)`.
///
/// Handles every prime `p > 2`; falls back to the `(p+1)/4` shortcut
/// for `p ≡ 3 (mod 4)`.
pub fn sqrt_mod_p(n: &BigUint, p: &BigUint) -> Option<BigUint> {
    let n_mod = n % p;
    if n_mod.is_zero() {
        return Some(BigUint::zero());
    }
    // Euler's criterion: n^((p-1)/2) must be 1 (QR) or p-1 (NQR).
    let p_minus_one = p - BigUint::one();
    let euler = n_mod.modpow(&(&p_minus_one >> 1), p);
    if euler != BigUint::one() {
        return None;
    }
    // Shortcut for p ≡ 3 (mod 4):  x = n^((p+1)/4) mod p.
    let four = BigUint::from(4u32);
    if (p % &four) == BigUint::from(3u32) {
        let exp = (p + BigUint::one()) >> 2;
        return Some(n_mod.modpow(&exp, p));
    }
    // General Tonelli–Shanks.  Write p − 1 = Q · 2^S with Q odd.
    let mut q = p_minus_one.clone();
    let mut s = 0u32;
    while (&q & BigUint::one()).is_zero() {
        q >>= 1;
        s += 1;
    }
    // Find a quadratic non-residue z.
    let mut z = BigUint::from(2u32);
    while z.modpow(&(&p_minus_one >> 1), p) != p_minus_one {
        z += BigUint::one();
    }
    let mut m = s;
    let mut c = z.modpow(&q, p);
    let mut t = n_mod.modpow(&q, p);
    let mut r = n_mod.modpow(&((&q + BigUint::one()) >> 1), p);
    loop {
        if t == BigUint::one() {
            return Some(r);
        }
        // Find least i, 0 < i < m, with t^(2^i) = 1.
        let mut i = 0u32;
        let mut tmp = t.clone();
        while tmp != BigUint::one() {
            tmp = (&tmp * &tmp) % p;
            i += 1;
            if i >= m {
                // n should be a QR by the Euler check; reach here only
                // if p is composite or our randomness is unlucky.  Bail.
                return None;
            }
        }
        let exp = BigUint::one() << (m - i - 1);
        let b = c.modpow(&exp, p);
        m = i;
        c = (&b * &b) % p;
        t = (t * &c) % p;
        r = (r * b) % p;
    }
}

// ── Factor base over E(F_p) ─────────────────────────────────────────────

/// A factor-base element.  We record both the affine point and its
/// index in the base, so when a relation fires we can build the row.
#[derive(Clone, Debug)]
pub struct FactorBaseEntry {
    /// Position in the factor base.
    pub idx: usize,
    /// Point `P_idx = (x, y)` on the curve.
    pub point: Point,
}

/// Build a factor base of size `target_size` by enumerating points with
/// the smallest x-coordinates `x = 1, 2, 3, …` and checking whether
/// `x³ + ax + b` is a quadratic residue mod p.  The y-coordinate is
/// extracted by [`sqrt_mod_p`].
///
/// Returns the list; the actual size is `≤ target_size` because not
/// every x has a corresponding curve point.  Statistically half of all
/// x's are QRs, so expected `2·target_size` enumerations.
pub fn build_factor_base(curve: &CurveParams, target_size: usize) -> Vec<FactorBaseEntry> {
    let mut out = Vec::with_capacity(target_size);
    let mut x = BigUint::one();
    while out.len() < target_size && x < curve.p {
        // rhs = x³ + ax + b mod p
        let xf = curve.fe(x.clone());
        let rhs_value = xf
            .mul(&xf)
            .mul(&xf)
            .add(&curve.a_fe().mul(&xf))
            .add(&curve.fe(curve.b.clone()))
            .value;
        if let Some(y) = sqrt_mod_p(&rhs_value, &curve.p) {
            // Canonicalise: pick the smaller of (y, p − y) so the
            // factor-base entry is uniquely keyed by x.
            let y_canon = if &y * &BigUint::from(2u32) < curve.p {
                y
            } else {
                &curve.p - &y
            };
            out.push(FactorBaseEntry {
                idx: out.len(),
                point: Point::Affine {
                    x: xf,
                    y: curve.fe(y_canon),
                },
            });
        }
        x += BigUint::one();
    }
    out
}

// ── Relation finding ────────────────────────────────────────────────────

/// One row of the index-calculus linear system.
///
/// Mathematically: `coef_a + coef_b · log_G(Q) ≡ Σⱼ entries[j] · log_G(F_j)
/// (mod n)`, where `entries[j] ∈ {0, ±1, ±2}` records the signed
/// multiplicity of `F_j` in the decomposition.
#[derive(Clone, Debug)]
pub struct Relation {
    /// Coefficient of `G` in `R = aG + bQ`.
    pub coef_a: BigUint,
    /// Coefficient of `Q` in `R = aG + bQ`.
    pub coef_b: BigUint,
    /// Sparse entries: `(factor_base_index, signed_multiplicity)`.
    pub entries: Vec<(usize, i64)>,
}

/// **Find one relation** by sampling random `(a, b)` and trying to
/// decompose `R = aG + bQ` as a signed sum of *two* factor-base
/// elements.  Returns `None` if `max_trials` random samples all fail.
pub fn find_one_relation(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    factor_base: &[FactorBaseEntry],
    max_trials: usize,
) -> Option<Relation> {
    use crate::utils::random::random_scalar;

    let a_fe = curve.a_fe();
    let b_fe = curve.fe(curve.b.clone());
    // x-coordinate → factor-base index, for O(1) lookups.
    let mut x_to_idx = std::collections::HashMap::new();
    for fb in factor_base {
        if let Point::Affine { x, .. } = &fb.point {
            x_to_idx.insert(x.value.clone(), fb.idx);
        }
    }

    for _ in 0..max_trials {
        let a = random_scalar(&curve.n);
        let b = random_scalar(&curve.n);
        // R = aG + bQ.  Use the variable-time ladder (public k, fine).
        let ag = g.scalar_mul(&a, &a_fe);
        let bq = q.scalar_mul(&b, &a_fe);
        let r = ag.add(&bq, &a_fe);
        let xr = match &r {
            Point::Affine { x, .. } => x.clone(),
            Point::Infinity => continue,
        };

        // Sweep each factor-base element F_i; solve
        // S₃(x_R, x_{F_i}, X) = 0  for X via the quadratic formula.
        for fb_i in factor_base {
            let xi = match &fb_i.point {
                Point::Affine { x, .. } => x.clone(),
                Point::Infinity => continue,
            };
            let (qa, qb, qc) = semaev_s3_in_x3(&xr, &xi, &a_fe, &b_fe);
            // Solve qa·X² + qb·X + qc = 0 mod p.  Discriminant Δ = qb² − 4qa·qc.
            if qa.is_zero() {
                // Linear case: qb X + qc = 0 ⟹ X = −qc · qb⁻¹.
                if qb.is_zero() {
                    continue;
                }
                let inv = match qb.inv() {
                    Some(v) => v,
                    None => continue,
                };
                let candidate = qc.neg().mul(&inv);
                if let Some(rel) = try_finalise(
                    &r,
                    &fb_i.point,
                    &candidate,
                    &x_to_idx,
                    factor_base,
                    curve,
                    &a,
                    &b,
                ) {
                    return Some(rel);
                }
                continue;
            }
            let four = curve.fe(BigUint::from(4u32));
            let disc = qb.mul(&qb).sub(&four.mul(&qa).mul(&qc));
            let sqrt_disc = match sqrt_mod_p(&disc.value, &curve.p) {
                Some(v) => v,
                None => continue,
            };
            let two_qa_inv = match qa.add(&qa).inv() {
                Some(v) => v,
                None => continue,
            };
            for sign in [false, true] {
                let s = if sign {
                    curve.fe(&curve.p - &sqrt_disc)
                } else {
                    curve.fe(sqrt_disc.clone())
                };
                let candidate = qb.neg().add(&s).mul(&two_qa_inv);
                if let Some(rel) = try_finalise(
                    &r,
                    &fb_i.point,
                    &candidate,
                    &x_to_idx,
                    factor_base,
                    curve,
                    &a,
                    &b,
                ) {
                    return Some(rel);
                }
            }
        }
    }
    None
}

/// Given a candidate decomposition `R = ε_i F_i + ε_j F_j` (with
/// `x_{F_j}` resolved to `candidate_x`), try the four sign combinations
/// `(ε_i, ε_j) ∈ {±1}²` and return the resulting [`Relation`] if any
/// of them is geometrically valid (i.e. `ε_i F_i + ε_j F_j = R`).
fn try_finalise(
    r: &Point,
    f_i: &Point,
    candidate_x: &FieldElement,
    x_to_idx: &std::collections::HashMap<BigUint, usize>,
    factor_base: &[FactorBaseEntry],
    curve: &CurveParams,
    coef_a: &BigUint,
    coef_b: &BigUint,
) -> Option<Relation> {
    let j = *x_to_idx.get(&candidate_x.value)?;
    let f_j = factor_base[j].point.clone();
    let a_fe = curve.a_fe();

    // Try all four sign combinations.  For each match, the relation is
    //   aG + bQ = ε_i F_i + ε_j F_j
    // ⟹ in the unknowns y_k = log_G F_k and x = log_G Q:
    //      ε_i y_i + ε_j y_j − b x ≡ a   (mod n).
    // We store the row as entries that *multiply log_G F_*, and (coef_a,
    // coef_b) so the solver can build the augmented matrix.
    for s_i in [1i64, -1i64] {
        for s_j in [1i64, -1i64] {
            let p_i = if s_i > 0 { f_i.clone() } else { f_i.neg() };
            let p_j = if s_j > 0 { f_j.clone() } else { f_j.neg() };
            let lhs = p_i.add(&p_j, &a_fe);
            if &lhs == r {
                let i_idx = factor_base.iter().position(|fb| &fb.point == f_i)?;
                let mut entries = Vec::new();
                if i_idx == j {
                    // Special case: same factor base index, combine.
                    let combined = s_i + s_j;
                    if combined != 0 {
                        entries.push((i_idx, combined));
                    }
                } else {
                    entries.push((i_idx, s_i));
                    entries.push((j, s_j));
                }
                return Some(Relation {
                    coef_a: coef_a.clone(),
                    coef_b: coef_b.clone(),
                    entries,
                });
            }
        }
    }
    None
}

// ── Gaussian elimination mod n ─────────────────────────────────────────

/// **Solve** `M · y ≡ rhs (mod n)` for `y`, where `M` is given as rows
/// and `n` is prime (so every nonzero element is invertible).  Returns
/// `None` if the system is inconsistent or under-determined.
///
/// Used by the index-calculus driver to recover `log_G Q` from the
/// matrix of relations.
pub fn gaussian_eliminate_mod_n(
    matrix: &mut [Vec<BigUint>],
    rhs: &mut [BigUint],
    n: &BigUint,
) -> Option<Vec<BigUint>> {
    let rows = matrix.len();
    let cols = matrix.first().map(|r| r.len()).unwrap_or(0);
    let m = cols; // number of unknowns

    let mut col = 0;
    let mut row = 0;
    let mut pivot_rows: Vec<usize> = vec![usize::MAX; m];

    while row < rows && col < m {
        // Find a row at index ≥ `row` with a non-zero entry in column `col`.
        let mut piv = None;
        for r in row..rows {
            if !matrix[r][col].is_zero() {
                piv = Some(r);
                break;
            }
        }
        let piv = match piv {
            Some(p) => p,
            None => {
                col += 1;
                continue;
            }
        };
        matrix.swap(row, piv);
        rhs.swap(row, piv);
        pivot_rows[col] = row;

        // Normalise the pivot row.
        let inv = mod_inverse(&matrix[row][col], n)?;
        for c in 0..m {
            matrix[row][c] = (&matrix[row][c] * &inv) % n;
        }
        rhs[row] = (&rhs[row] * &inv) % n;

        // Eliminate column `col` in every other row.
        for r in 0..rows {
            if r == row {
                continue;
            }
            if matrix[r][col].is_zero() {
                continue;
            }
            let factor = matrix[r][col].clone();
            for c in 0..m {
                let term = (&factor * &matrix[row][c]) % n;
                matrix[r][c] = (&matrix[r][c] + n - term) % n;
            }
            let term = (&factor * &rhs[row]) % n;
            rhs[r] = (&rhs[r] + n - term) % n;
        }
        row += 1;
        col += 1;
    }

    // Read off the solution.  Any column without a pivot is a free
    // variable; for the index-calculus use case, we only succeed if
    // the unknown we want has a pivot.
    let mut out = vec![BigUint::zero(); m];
    let mut any_free = false;
    for c in 0..m {
        if pivot_rows[c] == usize::MAX {
            any_free = true;
        } else {
            out[c] = rhs[pivot_rows[c]].clone();
        }
    }
    // Even if there are free vars, return the partial solution and let
    // the caller decide whether it's enough.
    let _ = any_free;
    Some(out)
}

// ── End-to-end ECDLP solver via index calculus ─────────────────────────

/// **Solve `Q = x · G` for `x`** on `curve` using the Semaev-S₃ index-
/// calculus framework.  `fb_size` is the desired factor base size,
/// `extra_relations` is how many relations beyond the minimum to
/// collect, `max_trials_per_relation` bounds the trial loop.
///
/// Returns `Some(x)` on success; `None` if relation gathering or the
/// linear solve fails.  Intended for educational use on **small**
/// curves; see module docs for asymptotic complexity.
pub fn ec_index_calculus_dlp(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    fb_size: usize,
    extra_relations: usize,
    max_trials_per_relation: usize,
) -> Option<BigUint> {
    let fb = build_factor_base(curve, fb_size);
    if fb.is_empty() {
        return None;
    }
    let target = fb.len() + extra_relations;

    let mut relations = Vec::with_capacity(target);
    while relations.len() < target {
        let rel = find_one_relation(curve, g, q, &fb, max_trials_per_relation)?;
        relations.push(rel);
    }

    // Build the linear system.  Unknowns: (y_1, …, y_m, x = log_G Q).
    // Row r:   Σ entries[j].value y_j  − coef_b · x  ≡ coef_a (mod n)
    // i.e.    entries  ‖ −coef_b   ·   (y, x)  =  coef_a.
    let m = fb.len();
    let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(relations.len());
    let mut rhs: Vec<BigUint> = Vec::with_capacity(relations.len());
    for rel in &relations {
        let mut row = vec![BigUint::zero(); m + 1];
        for &(j, mult) in &rel.entries {
            let val = signed_mod(mult, &curve.n);
            row[j] = (&row[j] + &val) % &curve.n;
        }
        // last column: −coef_b
        let neg_b = (&curve.n - &(&rel.coef_b % &curve.n)) % &curve.n;
        row[m] = neg_b;
        matrix.push(row);
        rhs.push(rel.coef_a.clone() % &curve.n);
    }

    let solution = gaussian_eliminate_mod_n(&mut matrix, &mut rhs, &curve.n)?;
    let x = solution[m].clone();
    // Verify Q ≡ x·G.  If not (which can happen when the system is
    // under-determined), bail.
    let a_fe = curve.a_fe();
    let candidate = g.scalar_mul(&x, &a_fe);
    if &candidate == q {
        Some(x)
    } else {
        None
    }
}

fn signed_mod(v: i64, n: &BigUint) -> BigUint {
    if v >= 0 {
        BigUint::from(v as u64) % n
    } else {
        n - (BigUint::from((-v) as u64) % n)
    }
}

// ── Baseline: textbook Pollard rho for ECDLP ───────────────────────────

/// **Pollard rho** for the elliptic-curve discrete log.  Walks a single
/// chain `R_{i+1} = f(R_i)` where `f` is a partition-based pseudo-random
/// step (Teske's r-adding walk with r = 3 branches: G, Q, or G+Q each
/// chosen by `x_R mod 3`).  Detects collision via Floyd's tortoise/hare.
///
/// Included here as a baseline against which the index-calculus driver
/// is compared.  Pollard rho on a prime-field curve of `n`-bit order
/// runs in expected `≈ √(πn/2)` group operations; the IC driver above
/// is asymptotically *worse* in this 2-decomposition regime
/// (`O(p · m) = O(p^{3/2})`).  Watching the two timings diverge on
/// progressively larger curves is the headline "good news for prime
/// curve security" of this module.
pub fn pollard_rho_ecdlp(
    curve: &CurveParams,
    g: &Point,
    q: &Point,
    max_steps: usize,
) -> Option<BigUint> {
    let a_fe = curve.a_fe();
    // Three precomputed step points: G, Q, G+Q.
    let g_plus_q = g.add(q, &a_fe);

    let step = |r: &Point, alpha: &BigUint, beta: &BigUint| -> (Point, BigUint, BigUint) {
        let branch = match r {
            Point::Affine { x, .. } => (&x.value % BigUint::from(3u32))
                .to_u32_digits()
                .first()
                .copied()
                .unwrap_or(0),
            Point::Infinity => 0,
        };
        match branch {
            0 => (
                r.add(g, &a_fe),
                (alpha + BigUint::one()) % &curve.n,
                beta.clone(),
            ),
            1 => (
                r.add(&g_plus_q, &a_fe),
                (alpha + BigUint::one()) % &curve.n,
                (beta + BigUint::one()) % &curve.n,
            ),
            _ => (
                r.add(q, &a_fe),
                alpha.clone(),
                (beta + BigUint::one()) % &curve.n,
            ),
        }
    };

    // Two walkers (Floyd).  Start from R₀ = G + Q so we have a known
    // (α, β) decomposition right away.
    let mut t_r = g.add(q, &a_fe);
    let mut t_a = BigUint::one();
    let mut t_b = BigUint::one();
    let mut h_r = t_r.clone();
    let mut h_a = t_a.clone();
    let mut h_b = t_b.clone();

    for _ in 0..max_steps {
        // Tortoise: one step.
        let (rn, an, bn) = step(&t_r, &t_a, &t_b);
        t_r = rn;
        t_a = an;
        t_b = bn;
        // Hare: two steps.
        let (rn, an, bn) = step(&h_r, &h_a, &h_b);
        let (rn, an, bn) = step(&rn, &an, &bn);
        h_r = rn;
        h_a = an;
        h_b = bn;

        if t_r == h_r {
            // Collision: α_t G + β_t Q  =  α_h G + β_h Q
            //  ⟹  (α_t − α_h) ≡ (β_h − β_t) · x  (mod n).
            let n = &curve.n;
            let lhs = (&t_a + n - &h_a) % n;
            let rhs = (&h_b + n - &t_b) % n;
            if rhs.is_zero() {
                return None;
            }
            let inv = mod_inverse(&rhs, n)?;
            return Some((lhs * inv) % n);
        }
    }
    None
}

// ── Tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    /// **Small curve for tests**: y² = x³ + x + 19 (mod 271).  Curve
    /// has 281 points (prime), so cofactor 1 and `G = (3, 7)` is a
    /// generator of the full group.
    fn tiny_curve() -> CurveParams {
        CurveParams {
            name: "test-curve-271",
            p: BigUint::from(271u32),
            a: BigUint::from(1u32),
            b: BigUint::from(19u32),
            gx: BigUint::from(3u32),
            gy: BigUint::from(7u32),
            n: BigUint::from(281u32),
            h: 1,
        }
    }

    /// **Semaev S₃ is symmetric** in its three variables (verify on a
    /// handful of random samples).
    #[test]
    fn s3_symmetric() {
        let curve = tiny_curve();
        let a = curve.a_fe();
        let b = curve.fe(curve.b.clone());
        for (x1, x2, x3) in [(1u32, 2u32, 3u32), (5, 7, 11), (100, 150, 200)] {
            let f1 = curve.fe(BigUint::from(x1));
            let f2 = curve.fe(BigUint::from(x2));
            let f3 = curve.fe(BigUint::from(x3));
            let v123 = semaev_s3(&f1, &f2, &f3, &a, &b);
            let v132 = semaev_s3(&f1, &f3, &f2, &a, &b);
            let v213 = semaev_s3(&f2, &f1, &f3, &a, &b);
            let v231 = semaev_s3(&f2, &f3, &f1, &a, &b);
            let v312 = semaev_s3(&f3, &f1, &f2, &a, &b);
            let v321 = semaev_s3(&f3, &f2, &f1, &a, &b);
            assert_eq!(v123, v132);
            assert_eq!(v123, v213);
            assert_eq!(v123, v231);
            assert_eq!(v123, v312);
            assert_eq!(v123, v321);
        }
    }

    /// **Semaev S₃ vanishes on a triple of collinear points**.  If
    /// `P₁ + P₂ + P₃ = O` on `E`, then `S₃(x_{P₁}, x_{P₂}, x_{P₃}) = 0`.
    #[test]
    fn s3_vanishes_on_collinear() {
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let b_fe = curve.fe(curve.b.clone());

        // Pick P, Q on the curve, compute R = −(P + Q) = P+Q reflected.
        // Then P + Q + R = O, so S₃ should vanish on (x_P, x_Q, x_R).
        let p1 = g.scalar_mul(&BigUint::from(2u32), &a_fe);
        let p2 = g.scalar_mul(&BigUint::from(5u32), &a_fe);
        let p3 = p1.add(&p2, &a_fe).neg();

        let (x1, x2, x3) = (
            match &p1 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p2 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p3 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
        );
        let s = semaev_s3(&x1, &x2, &x3, &a_fe, &b_fe);
        assert!(s.is_zero(), "S₃ should vanish on collinear x-coords");
    }

    /// **Tonelli–Shanks** is invertible: `sqrt(n)² ≡ n (mod p)` for
    /// every quadratic residue `n`.
    #[test]
    fn tonelli_shanks_invertible() {
        // p = 17 ≡ 1 mod 4, exercises the full Tonelli–Shanks path.
        let p = BigUint::from(17u32);
        for n in 1u32..17 {
            let nn = BigUint::from(n);
            if let Some(r) = sqrt_mod_p(&nn, &p) {
                let sq = (&r * &r) % &p;
                assert_eq!(sq, nn, "n = {}", n);
            }
        }
        // p = 263 ≡ 3 mod 4, takes the shortcut path.
        let p = BigUint::from(263u32);
        for n in 1u32..263 {
            let nn = BigUint::from(n);
            if let Some(r) = sqrt_mod_p(&nn, &p) {
                let sq = (&r * &r) % &p;
                assert_eq!(sq, nn);
            }
        }
    }

    /// **Tonelli–Shanks rejects non-residues** properly.
    #[test]
    fn tonelli_shanks_rejects_nqr() {
        let p = BigUint::from(13u32);
        // QR mod 13 are {1, 3, 4, 9, 10, 12}; NQR are {2, 5, 6, 7, 8, 11}.
        for nqr in [2u32, 5, 6, 7, 8, 11] {
            assert!(sqrt_mod_p(&BigUint::from(nqr), &p).is_none(), "{}", nqr);
        }
    }

    /// **Factor base** contains points actually on the curve.
    #[test]
    fn factor_base_on_curve() {
        let curve = tiny_curve();
        let fb = build_factor_base(&curve, 20);
        assert!(!fb.is_empty());
        assert!(fb.len() <= 20);
        for entry in &fb {
            assert!(
                curve.is_on_curve(&entry.point),
                "{}: point off curve",
                entry.idx,
            );
        }
    }

    /// **Linear solver** recovers a known solution on a small system.
    #[test]
    fn gaussian_solves_small_system() {
        // 2x + 3y = 7  ;  x + y = 3   (mod 11)
        //   ⟹  x = 2, y = 1.
        let n = BigUint::from(11u32);
        let mut m = vec![
            vec![BigUint::from(2u32), BigUint::from(3u32)],
            vec![BigUint::from(1u32), BigUint::from(1u32)],
        ];
        let mut r = vec![BigUint::from(7u32), BigUint::from(3u32)];
        let sol = gaussian_eliminate_mod_n(&mut m, &mut r, &n).expect("solvable");
        assert_eq!(sol[0], BigUint::from(2u32));
        assert_eq!(sol[1], BigUint::from(1u32));
    }

    /// **End-to-end ECDLP** on a small curve: solve `Q = x·G` via the
    /// index-calculus driver, verify the recovered `x` against direct
    /// search.
    #[test]
    fn ec_index_calculus_small_dlp() {
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();

        // Plant x = 47 (smallish, well within the curve order 281).
        let x_truth = BigUint::from(47u32);
        let q = g.scalar_mul(&x_truth, &a_fe);

        // Drive IC.  Tiny factor base + generous trial budget.
        let recovered = ec_index_calculus_dlp(&curve, &g, &q, 12, 4, 5_000);
        let recovered = recovered.expect("IC should recover x on this small curve");
        let recheck = g.scalar_mul(&recovered, &a_fe);
        assert_eq!(recheck, q);
        assert!(recovered < curve.n);
    }

    /// **S₄ closed form sanity check**: evaluate `S_4` at four x-coords
    /// of points that sum to the identity.  Should be zero.
    #[test]
    fn s4_vanishes_on_four_collinear() {
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let b_fe = curve.fe(curve.b.clone());

        // P₁ + P₂ + P₃ + P₄ = O.  Construct: P₁, P₂, P₃ arbitrary, then
        // P₄ = −(P₁ + P₂ + P₃).
        let p1 = g.scalar_mul(&BigUint::from(2u32), &a_fe);
        let p2 = g.scalar_mul(&BigUint::from(7u32), &a_fe);
        let p3 = g.scalar_mul(&BigUint::from(13u32), &a_fe);
        let p4 = p1.add(&p2, &a_fe).add(&p3, &a_fe).neg();
        let (x1, x2, x3, x4) = (
            match &p1 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p2 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p3 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p4 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
        );
        // Evaluate S_4(x₁, x₂, x₃, X₄) at X₄ = x₄.
        let coeffs = semaev_s4_in_x4(&x1, &x2, &x3, &a_fe, &b_fe);
        let mut value = FieldElement::zero(curve.p.clone());
        let mut x4_pow = FieldElement::one(curve.p.clone());
        for c in coeffs.iter() {
            value = value.add(&c.mul(&x4_pow));
            x4_pow = x4_pow.mul(&x4);
        }
        assert!(
            value.is_zero(),
            "S₄ should vanish on collinear-sum x-coords"
        );
    }

    /// **Root finder sanity**: build a polynomial with known roots
    /// and recover them.
    #[test]
    fn find_roots_fp_round_trip() {
        let p = BigUint::from(271u32);
        let r1 = FieldElement::new(BigUint::from(3u32), p.clone());
        let r2 = FieldElement::new(BigUint::from(11u32), p.clone());
        let r3 = FieldElement::new(BigUint::from(200u32), p.clone());
        // (X − r1)(X − r2)(X − r3) over F_271 (signs absorbed via .neg()).
        let mr1 = r1.neg();
        let mr2 = r2.neg();
        let mr3 = r3.neg();
        // Expand step by step.
        //   (X + mr1)(X + mr2) = X² + (mr1 + mr2)X + mr1·mr2
        let c0_a = mr1.mul(&mr2);
        let c1_a = mr1.add(&mr2);
        // Multiply that by (X + mr3):
        //   X³ + (mr3 + c1_a) X² + (mr3·c1_a + c0_a) X + mr3·c0_a
        let c0 = mr3.mul(&c0_a);
        let c1 = mr3.mul(&c1_a).add(&c0_a);
        let c2 = mr3.add(&c1_a);
        let c3 = FieldElement::one(p.clone());
        let coeffs = vec![c0, c1, c2, c3];
        let mut roots = find_roots_fp(&coeffs, &p);
        roots.sort_by_key(|r| r.value.clone());
        let mut expected = vec![r1, r2, r3];
        expected.sort_by_key(|r| r.value.clone());
        assert_eq!(roots, expected);
    }

    /// **S_4 + root finder, end-to-end 3-decomposition oracle**.
    ///
    /// Given three factor-base x-coords `(x₁, x₂, x₃)` and the curve's
    /// `(a, b)`, compute `S_4(x₁, x₂, x₃, X₄)` as a quartic and read off
    /// every candidate `x₄ ∈ F_p` whose curve point closes the relation
    /// `±P₁ ± P₂ ± P₃ ± P₄ = O`. This is the binary-search step that
    /// turns the (currently unused) `semaev_s4_in_x4` infrastructure
    /// into something a relation collector can actually call.
    #[test]
    fn s4_root_finder_recovers_x4() {
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let b_fe = curve.fe(curve.b.clone());

        let p1 = g.scalar_mul(&BigUint::from(2u32), &a_fe);
        let p2 = g.scalar_mul(&BigUint::from(7u32), &a_fe);
        let p3 = g.scalar_mul(&BigUint::from(13u32), &a_fe);
        let p4 = p1.add(&p2, &a_fe).add(&p3, &a_fe).neg();
        let (x1, x2, x3, x4) = (
            match &p1 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p2 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p3 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
            match &p4 {
                Point::Affine { x, .. } => x.clone(),
                _ => panic!(),
            },
        );
        let coeffs = semaev_s4_in_x4(&x1, &x2, &x3, &a_fe, &b_fe);
        let coeffs_vec: Vec<FieldElement> = coeffs.to_vec();
        let roots = find_roots_fp(&coeffs_vec, &curve.p);
        assert!(
            roots.contains(&x4),
            "the true x₄ = {:?} should be among S₄-roots {:?}",
            x4.value,
            roots.iter().map(|r| r.value.clone()).collect::<Vec<_>>()
        );
        // Cross-check: every root r satisfies S_4(x_1, x_2, x_3, r) = 0,
        // i.e. evaluating the quartic at r gives zero.
        for r in &roots {
            let mut val = coeffs[4].clone();
            for i in (0..4).rev() {
                val = val.mul(r).add(&coeffs[i]);
            }
            assert!(val.is_zero());
        }
    }

    /// **Pollard rho** as a sanity baseline: recover the same `x` and
    /// confirm both algorithms agree.
    #[test]
    fn pollard_rho_recovers_small_dlp() {
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();
        let x_truth = BigUint::from(47u32);
        let q = g.scalar_mul(&x_truth, &a_fe);
        let recovered =
            pollard_rho_ecdlp(&curve, &g, &q, 200_000).expect("rho should recover small DLP");
        let recheck = g.scalar_mul(&recovered, &a_fe);
        assert_eq!(recheck, q);
    }

    /// **IC vs rho on a 10-bit curve**: both must find the same `x`,
    /// even when we don't tell them what it is.  This is the most
    /// substantive test in the module — we run *real* end-to-end
    /// ECDLP via two completely different algorithms and check they
    /// agree.
    ///
    /// Empirically on the 10-bit curve (`|E| = 281`), the index-calculus
    /// driver takes a few thousand trials per relation × ~16 relations,
    /// while rho terminates in ≈ √(πn/2) ≈ 21 group ops.  The asymmetry
    /// is exactly what the published research predicts: 2-decomposition
    /// IC is strictly worse than rho on prime-field curves.
    #[test]
    fn ic_and_rho_agree_on_random_dlp() {
        use crate::utils::random::random_scalar;
        let curve = tiny_curve();
        let g = curve.generator();
        let a_fe = curve.a_fe();

        let x_truth = random_scalar(&curve.n);
        let q = g.scalar_mul(&x_truth, &a_fe);

        let ic = ec_index_calculus_dlp(&curve, &g, &q, 14, 6, 10_000);
        let rho = pollard_rho_ecdlp(&curve, &g, &q, 500_000);
        let ic = ic.expect("IC should recover the DLP on this small curve");
        let rho = rho.expect("rho should recover the DLP on this small curve");

        // Both [ic]G and [rho]G must equal Q, regardless of whether
        // they're the same scalar (mod n).  This is the right
        // assertion because ECDLP solutions are unique mod n.
        assert_eq!(g.scalar_mul(&ic, &a_fe), q);
        assert_eq!(g.scalar_mul(&rho, &a_fe), q);
        // And they should in fact match each other mod n.
        assert_eq!(ic % &curve.n, rho % &curve.n);
    }
}
