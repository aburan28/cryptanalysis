//! **Elliptic divisibility sequences, elliptic nets, and the EDS-Residue
//! handle on the ECDLP** (Shipsey 2000, Stange 2007, Lauter–Stange 2008).
//!
//! This module is the runnable companion to `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.  It
//! builds the elliptic divisibility sequence (EDS) `W_{E,P}(n)` attached to
//! a point `P` on a short-Weierstrass curve over `F_p`, and measures the
//! structures that the Lauter–Stange equivalence chain hangs on:
//!
//! 1. **Rank of apparition.**  `W(n) = 0  ⟺  [n]P = O`, so the first zero
//!    of the sequence is exactly `ord(P)`.  This is the anchor that ties
//!    the sequence to the group, and we cross-check it against honest
//!    point arithmetic.
//! 2. **Periodicity.**  Over `F_p` the sequence `W(n) mod p` is purely
//!    periodic; we measure its period `π_W`.
//! 3. **The quadratic-residuosity / Legendre sequence** `χ(n) = (W(n) | p)`.
//!    The *EDS-Residue problem* (Lauter–Stange) is: given the curve, `P`,
//!    and `Q = [k]P` (but **not** `k`), decide whether `W_{E,P}(k)` is a
//!    quadratic residue.  We measure the period `π_χ`, the QR / NQR / zero
//!    balance, and whether the χ-pattern localises `k`.
//! 4. **The zero-lattice of the 2-D elliptic net.**  For the pair `(P, Q)`
//!    the net value `W(a, b)` vanishes iff `[a]P + [b]Q = O`.  When
//!    `Q = [k]P` the zero set is the sublattice `{(a,b) : a + bk ≡ 0
//!    (mod m)}`, whose slope *is* the discrete log.  We exhibit that
//!    lattice and recover `k` from it.
//!
//! ## The recurrence
//!
//! An EDS is a sequence with `W(0)=0`, `W(1)=1` satisfying Ward's relation
//!
//! ```text
//!   W(m+n)·W(m−n) = W(m+1)·W(m−1)·W(n)² − W(n+1)·W(n−1)·W(m)².
//! ```
//!
//! For the sequence attached to a curve, `W(n) = ψ_n(P)` where `ψ_n` is the
//! `n`-th division polynomial, so `W(2)=2y`, `W(3)=ψ_3(P)`, `W(4)=ψ_4(P)`.
//! We extend with the standard duplication formulas (valid for `W(1)=1`):
//!
//! ```text
//!   W(2n+1) = W(n+2)·W(n)³ − W(n−1)·W(n+1)³
//!   W(2n)·W(2) = W(n)·( W(n+2)·W(n−1)² − W(n−2)·W(n+1)² )
//! ```
//!
//! Both right-hand sides reference only strictly smaller indices, so the
//! array fills left-to-right in `O(n)` field operations.
//!
//! ## What this is and is not
//!
//! Lauter–Stange prove EDS-Residue is solvable in sub-exponential time iff
//! the ECDLP is — so **this is not a generic-beating attack**, and the
//! module does not claim one.  It is an instrument for the *structural*
//! question the equivalence leaves open: does the Legendre sequence carry
//! exploitable bias on special curves, and how cheaply does the QR pattern
//! of the net localise the zero-lattice in practice?  See the research doc
//! for the honest scorecard.

use crate::cryptanalysis::ec_index_calculus::sqrt_mod_p;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;
use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, Zero};

// ── small modular helpers (BigUint, fixed modulus p) ───────────────────────

#[inline]
fn m_mul(x: &BigUint, y: &BigUint, p: &BigUint) -> BigUint {
    (x * y) % p
}

#[inline]
fn m_sub(x: &BigUint, y: &BigUint, p: &BigUint) -> BigUint {
    // (x − y) mod p without signed arithmetic.
    ((x % p) + p - (y % p)) % p
}

#[inline]
fn m_pow(x: &BigUint, e: u32, p: &BigUint) -> BigUint {
    x.modpow(&BigUint::from(e), p)
}

/// Modular inverse via Fermat (p prime).  `None` for zero.
fn m_inv(x: &BigUint, p: &BigUint) -> Option<BigUint> {
    if (x % p).is_zero() {
        return None;
    }
    Some(x.modpow(&(p - BigUint::from(2u32)), p))
}

/// Legendre symbol `(w | p)` returned as `+1` (QR), `-1` (non-residue) or
/// `0` (w ≡ 0).  `p` is an odd prime.
pub fn legendre(w: &BigUint, p: &BigUint) -> i8 {
    let r = (w % p).modpow(&((p - BigUint::one()) >> 1), p);
    if r.is_zero() {
        0
    } else if r.is_one() {
        1
    } else {
        // r == p − 1
        -1
    }
}

// ── the elliptic divisibility sequence ─────────────────────────────────────

/// Build `W_{E,P}(0..count)` over `F_p` for the curve `y² = x³ + ax + b`
/// and the affine point `P = (x, y)` with `y ≠ 0`.
///
/// Returns the residues `W(n) mod p`.  Requires `count ≥ 5`.
pub fn eds_sequence(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    x: &BigUint,
    y: &BigUint,
    count: usize,
) -> Vec<BigUint> {
    assert!(count >= 5, "need at least the four seed terms");
    let x = x % p;
    let y = y % p;
    let a = a % p;
    let b = b % p;

    let two = BigUint::from(2u32);
    let three = BigUint::from(3u32);
    let four = BigUint::from(4u32);
    let five = BigUint::from(5u32);
    let six = BigUint::from(6u32);
    let twelve = BigUint::from(12u32);
    let twenty = BigUint::from(20u32);
    let eight = BigUint::from(8u32);

    // W(0)=0, W(1)=1, W(2)=2y.
    let mut w: Vec<BigUint> = Vec::with_capacity(count);
    w.push(BigUint::zero());
    w.push(BigUint::one());
    w.push(m_mul(&two, &y, p));

    // W(3) = 3x⁴ + 6a x² + 12b x − a².
    let x2 = m_pow(&x, 2, p);
    let x4 = m_pow(&x, 4, p);
    let w3a = m_mul(&three, &x4, p);
    let w3b = m_mul(&m_mul(&six, &a, p), &x2, p);
    let w3c = m_mul(&m_mul(&twelve, &b, p), &x, p);
    let w3d = m_pow(&a, 2, p);
    let w3 = m_sub(&((w3a + w3b + w3c) % p), &w3d, p);
    w.push(w3);

    // W(4) = 4y( x⁶ + 5a x⁴ + 20b x³ − 5a² x² − 4ab x − 8b² − a³ ).
    let x3 = m_pow(&x, 3, p);
    let x6 = m_pow(&x, 6, p);
    let a2 = m_pow(&a, 2, p);
    let t_x6 = x6;
    let t_5ax4 = m_mul(&m_mul(&five, &a, p), &x4, p);
    let t_20bx3 = m_mul(&m_mul(&twenty, &b, p), &x3, p);
    let t_5a2x2 = m_mul(&m_mul(&five, &a2, p), &x2, p);
    let t_4abx = m_mul(&m_mul(&m_mul(&four, &a, p), &b, p), &x, p);
    let t_8b2 = m_mul(&eight, &m_pow(&b, 2, p), p);
    let t_a3 = m_pow(&a, 3, p);
    let pos = (t_x6 + t_5ax4 + t_20bx3) % p;
    let mut inner = m_sub(&pos, &t_5a2x2, p);
    inner = m_sub(&inner, &t_4abx, p);
    inner = m_sub(&inner, &t_8b2, p);
    inner = m_sub(&inner, &t_a3, p);
    let w4 = m_mul(&m_mul(&four, &y, p), &inner, p);
    w.push(w4);

    let w2_inv = m_inv(&w[2], p).expect("W(2)=2y must be invertible (y≠0)");

    for k in 5..count {
        let val = if k % 2 == 1 {
            // W(2n+1) = W(n+2)·W(n)³ − W(n−1)·W(n+1)³
            let n = (k - 1) / 2;
            let lhs = m_mul(&w[n + 2], &m_pow(&w[n], 3, p), p);
            let rhs = m_mul(&w[n - 1], &m_pow(&w[n + 1], 3, p), p);
            m_sub(&lhs, &rhs, p)
        } else {
            // W(2n)·W(2) = W(n)·( W(n+2)·W(n−1)² − W(n−2)·W(n+1)² )
            let n = k / 2;
            let t1 = m_mul(&w[n + 2], &m_pow(&w[n - 1], 2, p), p);
            let t2 = m_mul(&w[n - 2], &m_pow(&w[n + 1], 2, p), p);
            let bracket = m_sub(&t1, &t2, p);
            let num = m_mul(&w[n], &bracket, p);
            m_mul(&num, &w2_inv, p)
        };
        w.push(val);
    }
    w
}

// ── honest point arithmetic (validation anchor) ────────────────────────────

fn fe(v: &BigUint, p: &BigUint) -> FieldElement {
    FieldElement::new(v.clone(), p.clone())
}

/// Order of `P`: smallest `m > 0` with `[m]P = O` (brute force, toy sizes).
pub fn point_order(x: &BigUint, y: &BigUint, a: &BigUint, p: &BigUint, cap: u64) -> Option<u64> {
    let base = Point::Affine {
        x: fe(x, p),
        y: fe(y, p),
    };
    let a_fe = fe(a, p);
    let mut acc = Point::Infinity; // [0]P
    for m in 1..=cap {
        acc = acc.add(&base, &a_fe); // acc = [m]P
        if let Point::Infinity = acc {
            return Some(m);
        }
    }
    None
}

/// Locate the first point on the curve with `x ≥ x_start`, `y ≠ 0`, whose
/// order is at least `min_order`.  Returns `(x, y, order)`.
pub fn find_toy_point(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    x_start: u64,
    min_order: u64,
) -> Option<(BigUint, BigUint, u64)> {
    let pu: u64 = p.try_into().ok()?;
    for xi in x_start..pu {
        let x = BigUint::from(xi);
        let rhs = (m_pow(&x, 3, p) + m_mul(a, &x, p) + b) % p;
        if rhs.is_zero() {
            continue; // y = 0 → 2-torsion, W(2)=0
        }
        if let Some(y) = sqrt_mod_p(&rhs, p) {
            if y.is_zero() {
                continue;
            }
            if let Some(ord) = point_order(&x, &y, a, p, pu + 2) {
                if ord >= min_order {
                    return Some((x, y, ord));
                }
            }
        }
    }
    None
}

// ── analysis report ────────────────────────────────────────────────────────

/// Result of analysing one `(E, P)` pair.
#[derive(Clone, Debug)]
pub struct EdsReport {
    pub p: BigUint,
    pub a: BigUint,
    pub b: BigUint,
    pub px: BigUint,
    pub py: BigUint,
    /// `ord(P)` from honest point arithmetic.
    pub order: u64,
    /// First `n>0` with `W(n) ≡ 0`; must equal `order`.
    pub rank_of_apparition: u64,
    /// Did the validation `W(n)=0 ⟺ [n]P=O` hold for all tested `n`?
    pub apparition_consistent: bool,
    /// The shift multiplier: over `F_p`, `W(n+r) = A · Bⁿ · W(n)` for all
    /// `n`, where `r = ord(P)`.  `(A, B)`.
    pub mult_a: BigUint,
    pub mult_b: BigUint,
    /// Did the multiplier law `W(n+r) = A·Bⁿ·W(n)` verify for all `n`?
    pub mult_law_holds: bool,
    /// Legendre characters of the multiplier: `(χ(A), χ(B))`.  These are the
    /// invariants the EDS-Residue period hangs on.
    pub chi_a: i8,
    pub chi_b: i8,
    /// Period of `W(n) mod p` = `r · j`, the smallest `j` closing the
    /// multiplier (`Bʲ=1` and `Aʲ·B^{r·j(j-1)/2}=1`).
    pub period_w: u64,
    /// Period of the Legendre sequence `χ(n)` = `r · j_χ`.
    pub period_chi: u64,
    /// `(#QR, #NQR, #zero)` over the apparition block `n ∈ [1, r]`.
    pub qr_balance: (u64, u64, u64),
}

/// `(±1)^e` from a sign `s ∈ {+1,-1}` and exponent parity.
#[inline]
fn pm_pow(s: i8, e_is_odd: bool) -> i8 {
    if s == 1 || !e_is_odd {
        1
    } else {
        -1
    }
}

/// Full analysis of the EDS attached to `P` on `y²=x³+ax+b / F_p`.
pub fn analyze(p: &BigUint, a: &BigUint, b: &BigUint, px: &BigUint, py: &BigUint) -> EdsReport {
    let pu: u64 = p.clone().try_into().expect("toy prime fits in u64");
    let order = point_order(px, py, a, p, pu + 2).expect("P has finite order");
    let r = order as usize;

    // Need ≥ 2 apparition blocks plus headroom to verify the multiplier law.
    let count = (2 * r + 4).max(8);
    let w = eds_sequence(p, a, b, px, py, count);

    // Rank of apparition: first zero.
    let rank = (1..count)
        .find(|&n| w[n].is_zero())
        .map(|n| n as u64)
        .unwrap_or(0);

    // Validate W(n)=0 ⟺ [n]P=O against honest point arithmetic.
    let a_fe = fe(a, p);
    let base = Point::Affine {
        x: fe(px, p),
        y: fe(py, p),
    };
    let mut consistent = true;
    let mut acc = Point::Infinity; // [0]P
    for wn in w.iter() {
        let is_identity = matches!(acc, Point::Infinity);
        if wn.is_zero() != is_identity {
            consistent = false;
            break;
        }
        acc = acc.add(&base, &a_fe);
    }

    // Shift multiplier (A, B) from W(n+r) = A·Bⁿ·W(n):
    //   B = W(r+2) / ( W(2)·W(r+1) ),   A = W(r+1) / B.
    let w2_inv = m_inv(&w[2], p).expect("W(2) invertible");
    let wr1_inv = m_inv(&w[r + 1], p).expect("W(r+1) nonzero (m ∤ r+1)");
    let mult_b = m_mul(&w[r + 2], &m_mul(&w2_inv, &wr1_inv, p), p);
    let b_inv = m_inv(&mult_b, p).expect("B nonzero");
    let mult_a = m_mul(&w[r + 1], &b_inv, p);

    // Verify the law across a full block.
    let mut mult_law_holds = true;
    let mut bn = BigUint::one(); // Bⁿ, starting n=0
    for n in 0..r {
        let predicted = m_mul(&mult_a, &m_mul(&bn, &w[n], p), p);
        if predicted != w[n + r] {
            mult_law_holds = false;
            break;
        }
        bn = m_mul(&bn, &mult_b, p);
    }

    let chi_a = legendre(&mult_a, p);
    let chi_b = legendre(&mult_b, p);

    // Period of W: smallest j with Bʲ=1 and Aʲ·B^{r·j(j-1)/2}=1.  π_W = r·j.
    let period_w = {
        let mut found = None;
        for j in 1u64..=pu {
            let bj = mult_b.modpow(&BigUint::from(j), p);
            if !bj.is_one() {
                continue;
            }
            // exponent r·j·(j-1)/2 (mod p−1 handled by modpow)
            let exp = BigUint::from(r as u64) * BigUint::from(j) * BigUint::from(j - 1) / 2u32;
            let lhs = m_mul(
                &mult_a.modpow(&BigUint::from(j), p),
                &mult_b.modpow(&exp, p),
                p,
            );
            if lhs.is_one() {
                found = Some(j);
                break;
            }
        }
        order * found.unwrap_or(0)
    };

    // Period of χ: smallest j with ε^j=1 and δ^j·ε^{r·j(j-1)/2}=1, χ-arithmetic.
    let period_chi = {
        let mut found = None;
        for j in 1u64..=8 {
            // coefficient of n: ε^j must be 1
            if pm_pow(chi_b, j % 2 == 1) != 1 {
                continue;
            }
            let exp_parity = {
                // parity of r·j·(j-1)/2
                let e = (r as u128) * (j as u128) * ((j as u128) - 1) / 2;
                e % 2 == 1
            };
            let lhs = pm_pow(chi_a, j % 2 == 1) * pm_pow(chi_b, exp_parity);
            if lhs == 1 {
                found = Some(j);
                break;
            }
        }
        order * found.unwrap_or(0)
    };

    // QR balance over the apparition block n ∈ [1, r].
    let (mut qr, mut nqr, mut zero) = (0u64, 0u64, 0u64);
    for n in 1..=r {
        match legendre(&w[n], p) {
            1 => qr += 1,
            -1 => nqr += 1,
            _ => zero += 1,
        }
    }

    EdsReport {
        p: p.clone(),
        a: a.clone(),
        b: b.clone(),
        px: px.clone(),
        py: py.clone(),
        order,
        rank_of_apparition: rank,
        apparition_consistent: consistent,
        mult_a,
        mult_b,
        mult_law_holds,
        chi_a,
        chi_b,
        period_w,
        period_chi,
        qr_balance: (qr, nqr, zero),
    }
}

// ── the 2-D net zero-lattice (DL recovery illustration) ────────────────────

/// For `P` of order `m` and `Q = [k]P`, the 2-D elliptic-net value
/// `W(a,b)` vanishes iff `[a]P + [b]Q = O`, i.e. iff `a + bk ≡ 0 (mod m)`.
/// Recover `k` from any net zero with `b` invertible mod `m`.
///
/// This uses honest point arithmetic to *locate* the vanishing locus (the
/// point of the net algorithm is that each `W(a,b)` is computable by the
/// recurrence without per-cell scalar multiplication; finding a zero is
/// still a search, which is why the whole construction is ECDLP-hard).
/// Returns `(k, the (a,b) zero used)`.
pub fn recover_dl_from_net_zeros(
    px: &BigUint,
    py: &BigUint,
    a: &BigUint,
    p: &BigUint,
    order: u64,
    k_true: u64,
    grid: u64,
) -> Option<(u64, (i64, i64))> {
    let a_fe = fe(a, p);
    let base = Point::Affine {
        x: fe(px, p),
        y: fe(py, p),
    };
    // Q = [k]P.
    let q = base.scalar_mul(&BigUint::from(k_true), &a_fe);

    for b_idx in 1..=(grid as i64) {
        for a_idx in 0..(grid as i64) {
            // [a]P + [b]Q
            let ap = if a_idx == 0 {
                Point::Infinity
            } else {
                base.scalar_mul(&BigUint::from(a_idx as u64), &a_fe)
            };
            let bq = match &q {
                Point::Infinity => Point::Infinity,
                _ => q.scalar_mul(&BigUint::from(b_idx as u64), &a_fe),
            };
            let sum = ap.add(&bq, &a_fe);
            if let Point::Infinity = sum {
                // a + b·k ≡ 0 (mod m)  ⇒  k ≡ −a · b⁻¹ (mod m)
                let m = BigUint::from(order);
                let b_big = BigUint::from(b_idx as u64) % &m;
                if let Some(b_inv) = m_inv(&b_big, &m) {
                    let neg_a = m_sub(&BigUint::zero(), &(BigUint::from(a_idx as u64) % &m), &m);
                    let k = (neg_a * b_inv) % &m;
                    let k_u: u64 = k.try_into().ok()?;
                    return Some((k_u, (a_idx, b_idx)));
                }
            }
        }
    }
    None
}

// ── markdown report ─────────────────────────────────────────────────────────

/// Render an [`EdsReport`] as a Markdown block for the research log.
pub fn format_report(r: &EdsReport) -> String {
    let (qr, nqr, zero) = r.qr_balance;
    let total = qr + nqr + zero;
    let bias = if (qr + nqr) > 0 {
        (qr as f64 - nqr as f64) / (qr + nqr) as f64
    } else {
        0.0
    };
    let sgn = |s: i8| match s {
        1 => "+1",
        -1 => "-1",
        _ => "0",
    };
    format!(
        "## EDS-Residue analysis\n\n\
         - Curve: `y² = x³ + {a}x + {b}  (mod {p})`\n\
         - Point `P = ({px}, {py})`, `ord(P) = {ord}`\n\
         - Rank of apparition (first `W(n)=0`): **{rank}**  {anchor}\n\
         - Apparition law `W(n)=0 ⟺ [n]P=O`: **{cons}**\n\
         - Shift multiplier `W(n+r) = A·Bⁿ·W(n)`: `A = {ma}`, `B = {mb}`  ({mlaw})\n\
         - Multiplier characters: `χ(A) = {ca}`, `χ(B) = {cb}`\n\
         - Period of `W(n) mod p`: `π_W = {pw}` = `{jw}·r`\n\
         - Period of Legendre seq `χ(n)`: `π_χ = {pc}` = `{jc}·r`\n\
         - QR balance over apparition block `[1,r]`: QR={qr}, NQR={nqr}, zero={zero} (n={total})\n\
         - Residue bias `(QR−NQR)/(QR+NQR)` = `{bias:+.4}`\n",
        a = r.a,
        b = r.b,
        p = r.p,
        px = r.px,
        py = r.py,
        ord = r.order,
        rank = r.rank_of_apparition,
        anchor = if r.rank_of_apparition == r.order {
            "✓ = ord(P)"
        } else {
            "✗ MISMATCH"
        },
        cons = if r.apparition_consistent {
            "✓ holds"
        } else {
            "✗ FAILS"
        },
        ma = r.mult_a,
        mb = r.mult_b,
        mlaw = if r.mult_law_holds {
            "✓ verified"
        } else {
            "✗ FAILS"
        },
        ca = sgn(r.chi_a),
        cb = sgn(r.chi_b),
        pw = r.period_w,
        jw = r.period_w.checked_div(r.order).unwrap_or(0),
        pc = r.period_chi,
        jc = r.period_chi.checked_div(r.order).unwrap_or(0),
        qr = qr,
        nqr = nqr,
        zero = zero,
        total = total,
        bias = bias,
    )
}

// ── EDS-Residue χ-localisation (rank-1, decimation identity) ────────────────
//
// The genuine 2-D net is blocked on Stange's mixed initial seeds (see
// research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md §5.3).  But the EDS-Residue question — how much the
// quadratic-residuosity of EDS terms leaks about the discrete log — is
// answerable in rank 1, fully canonically, via the decimation identity
//
//     ψ_{κn}(P) = ψ_n([κ]P) · ψ_κ(P)^{n²}                              (DEC)
//
// (Ward / Shipsey).  Taking Legendre symbols and using χ(·)^{n²}=χ(·)^{n}:
//
//     χ(ψ_n(Q)) = χ(ψ_{kn}(P)) · χ(ψ_k(P))^{n}     for Q = [k]P.       (DEC-χ)
//
// The left side is computable from Q's coordinates alone (no knowledge of k);
// each n therefore pins a constraint on k against the precomputed table
// T[j] = χ(ψ_j(P)).  The experiment measures the *minimal window* of n's
// whose residues uniquely identify k — i.e. the information content of the
// EDS-Residue signal.

/// `T[j] = χ(ψ_j(P)) = (W_{E,P}(j) | p)` for `j ∈ [0, upto)`.
pub fn chi_eds_table(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    px: &BigUint,
    py: &BigUint,
    upto: usize,
) -> Vec<i8> {
    let w = eds_sequence(p, a, b, px, py, upto.max(5));
    w.iter().map(|wn| legendre(wn, p)).collect()
}

/// `±1` raised to a parity (`n² ≡ n (mod 2)`): returns `s` if `n` is odd
/// (and `s≠0`), else `1`.
#[inline]
fn chi_pow_nsq(s: i8, n: usize) -> i8 {
    if n % 2 == 1 {
        s
    } else {
        1
    }
}

/// Result of one χ-localisation trial.
#[derive(Clone, Debug)]
pub struct LocalisationResult {
    pub order: u64,
    pub k: u64,
    /// Minimal window `W` (consecutive `n≥2`) after which every surviving
    /// candidate lies in `{k, m−k}` — i.e. `k` is pinned *up to sign*, the
    /// best any sign-symmetric residue signal can do.  `None` if not reached
    /// within budget.
    pub unique_window: Option<usize>,
    /// Number of candidates still matching at the largest tested window.
    pub residual_candidates: usize,
    /// Whether `m−k` is itself distinguishable from `k` by the residues
    /// (true ⇒ the window pins `k` exactly, not just up to sign).
    pub sign_resolved: bool,
    /// Did the observed `χ(ψ_n(Q))` match the decimation prediction (DEC-χ)?
    pub decimation_ok: bool,
}

/// Measure how many EDS-Residue bits identify the discrete log `k` for
/// `Q = [k]P`.  Fully self-contained and self-validating (checks DEC-χ).
/// Returns `None` if `Q` is the identity or 2-torsion.
pub fn localisation(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    px: &BigUint,
    py: &BigUint,
    order: u64,
    k: u64,
    max_window: usize,
) -> Option<LocalisationResult> {
    let m = order;
    // Q = [k]P.
    let a_fe = fe(a, p);
    let base = Point::Affine {
        x: fe(px, p),
        y: fe(py, p),
    };
    let q = base.scalar_mul(&BigUint::from(k), &a_fe);
    let (qx, qy) = match &q {
        Point::Affine { x, y } if !y.is_zero() => (x.value.clone(), y.value.clone()),
        _ => return None, // identity or 2-torsion ⇒ ψ_2(Q)=0, degenerate
    };

    // Observed residues from Q's own EDS: o[n] = χ(ψ_n(Q)).
    let o: Vec<i8> = chi_eds_table(p, a, b, &qx, &qy, max_window + 3);

    // Table over P, large enough for indices κ·n with κ<m, n≤max_window+1.
    let upto = (m as usize) * (max_window + 1) + 3;
    let t = chi_eds_table(p, a, b, px, py, upto);

    // Validate DEC-χ on the true k: o[n] == T[k·n]·χ(ψ_k(P))^{n}.
    let tk = t[k as usize];
    let mut decimation_ok = true;
    for n in 1..=(max_window + 1) {
        let pred = t[(k as usize) * n] * chi_pow_nsq(tk, n);
        if pred != o[n] {
            decimation_ok = false;
            break;
        }
    }

    // Candidate matching: minimal window after which survivors ⊆ {k, m−k}.
    let neg_k = (m - k % m) % m;
    let mut unique_window = None;
    let mut residual = m as usize - 1;
    let mut sign_resolved = false;
    for w in 1..=max_window {
        // window uses n ∈ [2, w+1]  (n=1 is χ(ψ_1)=+1, uninformative)
        let mut survivors: Vec<u64> = Vec::new();
        for kappa in 1..m {
            let tkap = t[kappa as usize];
            let mut ok = true;
            for n in 2..=(w + 1) {
                let pred = t[(kappa as usize) * n] * chi_pow_nsq(tkap, n);
                if pred != o[n] {
                    ok = false;
                    break;
                }
            }
            if ok {
                survivors.push(kappa);
            }
        }
        residual = survivors.len();
        if survivors.iter().all(|&c| c == k || c == neg_k) {
            unique_window = Some(w);
            sign_resolved = !survivors.contains(&neg_k) || neg_k == k;
            break;
        }
    }

    Some(LocalisationResult {
        order: m,
        k,
        unique_window,
        residual_candidates: residual,
        sign_resolved,
        decimation_ok,
    })
}

// The BigUint analysis path above is the validated reference; for sweeping
// thousands of curves we need a faster integer path.  Everything here works
// over odd primes `p < 2^32` so that products fit in `u128` (square roots via
// Tonelli–Shanks, so both `p ≡ 1` and `p ≡ 3 (mod 4)` are handled).

#[inline]
fn mulm(x: u64, y: u64, p: u64) -> u64 {
    ((x as u128 * y as u128) % p as u128) as u64
}

#[inline]
fn subm(x: u64, y: u64, p: u64) -> u64 {
    (x % p + p - y % p) % p
}

fn powm(mut x: u64, mut e: u64, p: u64) -> u64 {
    let mut r = 1u64;
    x %= p;
    while e > 0 {
        if e & 1 == 1 {
            r = mulm(r, x, p);
        }
        x = mulm(x, x, p);
        e >>= 1;
    }
    r
}

#[inline]
fn legendre_u64(w: u64, p: u64) -> i8 {
    let w = w % p;
    if w == 0 {
        return 0;
    }
    if powm(w, (p - 1) / 2, p) == 1 {
        1
    } else {
        -1
    }
}

#[inline]
fn invm(x: u64, p: u64) -> u64 {
    powm(x, p - 2, p)
}

/// Square root mod an odd prime `p` (Tonelli–Shanks), or `None` if `n` is a
/// non-residue.  Handles both `p ≡ 1` and `p ≡ 3 (mod 4)`.
fn sqrt_u64(n: u64, p: u64) -> Option<u64> {
    let n = n % p;
    if n == 0 {
        return Some(0);
    }
    if powm(n, (p - 1) / 2, p) != 1 {
        return None; // non-residue
    }
    if p % 4 == 3 {
        return Some(powm(n, (p + 1) / 4, p));
    }
    // p ≡ 1 (mod 4): full Tonelli–Shanks.
    let mut q = p - 1;
    let mut s = 0u32;
    while q.is_multiple_of(2) {
        q /= 2;
        s += 1;
    }
    // Smallest non-residue z.
    let mut z = 2u64;
    while powm(z, (p - 1) / 2, p) != p - 1 {
        z += 1;
    }
    let mut m = s;
    let mut c = powm(z, q, p);
    let mut t = powm(n, q, p);
    let mut r = powm(n, q.div_ceil(2), p);
    loop {
        if t == 1 {
            return Some(r);
        }
        let mut i = 0u32;
        let mut t2 = t;
        while t2 != 1 {
            t2 = mulm(t2, t2, p);
            i += 1;
            if i == m {
                return None;
            }
        }
        let b = powm(c, 1u64 << (m - i - 1), p);
        m = i;
        c = mulm(b, b, p);
        t = mulm(t, c, p);
        r = mulm(r, b, p);
    }
}

/// Aggregate of a χ-localisation sweep over many `k` on one `(E,P)`.
#[derive(Clone, Debug)]
pub struct LocalisationSweep {
    pub p: BigUint,
    pub order: u64,
    pub p_mod4: u64,
    pub tested: usize,
    /// `k` pinned to `{k, m−k}` within the window budget.
    pub pinned: usize,
    /// of the pinned, how many had the sign resolved (k exact).
    pub sign_resolved: usize,
    pub mean_window: f64,
    pub median_window: usize,
    pub max_window_seen: usize,
    pub decimation_ok: bool,
}

/// Efficient sweep: precompute `T` once, filter candidates incrementally
/// (`O(ord)` per `k`), sampling up to `max_k_samples` values of `k`.
pub fn localisation_sweep(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    px: &BigUint,
    py: &BigUint,
    order: u64,
    max_window: usize,
    max_k_samples: usize,
) -> LocalisationSweep {
    let m = order;
    let upto = (m as usize) * (max_window + 1) + 3;
    let t = chi_eds_table(p, a, b, px, py, upto);
    let a_fe = fe(a, p);
    let base = Point::Affine {
        x: fe(px, p),
        y: fe(py, p),
    };

    let ks: Vec<u64> = if (m.saturating_sub(2)) as usize <= max_k_samples {
        (2..m).collect()
    } else {
        (0..max_k_samples as u64)
            .map(|i| 2 + i * (m - 2) / max_k_samples as u64)
            .collect()
    };

    let mut windows: Vec<usize> = Vec::new();
    let mut tested = 0usize;
    let mut sign_resolved = 0usize;
    let mut decimation_ok = true;
    for k in ks {
        let q = base.scalar_mul(&BigUint::from(k), &a_fe);
        let (qx, qy) = match &q {
            Point::Affine { x, y } if !y.is_zero() => (x.value.clone(), y.value.clone()),
            _ => continue,
        };
        tested += 1;
        let o = chi_eds_table(p, a, b, &qx, &qy, max_window + 3);
        let tk = t[k as usize];
        for n in 1..=(max_window + 1) {
            if t[(k as usize) * n] * chi_pow_nsq(tk, n) != o[n] {
                decimation_ok = false;
                break;
            }
        }
        let neg_k = (m - k % m) % m;
        let mut survivors: Vec<u64> = (1..m).collect();
        for w in 1..=max_window {
            let n = w + 1; // new constraint
            survivors
                .retain(|&kap| t[(kap as usize) * n] * chi_pow_nsq(t[kap as usize], n) == o[n]);
            if survivors.iter().all(|&c| c == k || c == neg_k) {
                windows.push(w);
                if !survivors.contains(&neg_k) || neg_k == k {
                    sign_resolved += 1;
                }
                break;
            }
        }
    }

    windows.sort_unstable();
    let pinned = windows.len();
    let median = windows.get(pinned / 2).copied().unwrap_or(0);
    let max_seen = windows.last().copied().unwrap_or(0);
    let mean = if pinned > 0 {
        windows.iter().sum::<usize>() as f64 / pinned as f64
    } else {
        0.0
    };

    LocalisationSweep {
        p: p.clone(),
        order: m,
        p_mod4: (p % BigUint::from(4u32)).try_into().unwrap_or(0),
        tested,
        pinned,
        sign_resolved,
        mean_window: mean,
        median_window: median,
        max_window_seen: max_seen,
        decimation_ok,
    }
}

/// Per-curve census record.
#[derive(Clone, Debug)]
pub struct CurveBias {
    pub a: u64,
    pub b: u64,
    pub order: u64,
    pub qr: u64,
    pub nqr: u64,
    pub bias: f64,
    pub chi_a: i8,
    pub chi_b: i8,
}

/// Compute the apparition-block residue bias for `P=(x,y)` on
/// `y²=x³+ax+b / F_p` (requires `p ≡ 3 mod 4`, `y≠0`).  Walks the EDS until
/// the first zero (= ord(P)) or `cap`, then reads the multiplier characters
/// from the two terms past the zero.  Returns `None` if order > cap.
fn block_bias_u64(p: u64, a: u64, b: u64, x: u64, y: u64, cap: usize) -> Option<CurveBias> {
    // Seed terms W(0..4) (same formulas as eds_sequence, in u64).
    let x2 = mulm(x, x, p);
    let x3 = mulm(x2, x, p);
    let x4 = mulm(x2, x2, p);
    let x6 = mulm(x3, x3, p);
    let a2 = mulm(a, a, p);

    let w1 = 1u64;
    let w2 = mulm(2, y, p);
    let w3 = {
        let t = (mulm(3, x4, p) + mulm(mulm(6, a, p), x2, p) + mulm(mulm(12, b, p), x, p)) % p;
        subm(t, a2, p)
    };
    let w4 = {
        let pos = (x6 + mulm(mulm(5, a, p), x4, p) + mulm(mulm(20, b, p), x3, p)) % p;
        let mut inner = subm(pos, mulm(mulm(5, a2, p), x2, p), p);
        inner = subm(inner, mulm(mulm(mulm(4, a, p), b, p), x, p), p);
        inner = subm(inner, mulm(8, mulm(b, b, p), p), p);
        inner = subm(inner, mulm(a2, a, p), p);
        mulm(mulm(4, y, p), inner, p)
    };

    let mut w = vec![0u64, w1, w2, w3, w4];
    let w2_inv = invm(w2, p);

    let mut order = 0usize;
    let mut k = 5usize;
    loop {
        let val = if k % 2 == 1 {
            let n = (k - 1) / 2;
            let lhs = mulm(w[n + 2], mulm(mulm(w[n], w[n], p), w[n], p), p);
            let r1 = mulm(w[n + 1], w[n + 1], p);
            let rhs = mulm(w[n - 1], mulm(r1, w[n + 1], p), p);
            subm(lhs, rhs, p)
        } else {
            let n = k / 2;
            let t1 = mulm(w[n + 2], mulm(w[n - 1], w[n - 1], p), p);
            let t2 = mulm(w[n - 2], mulm(w[n + 1], w[n + 1], p), p);
            let bracket = subm(t1, t2, p);
            mulm(mulm(w[n], bracket, p), w2_inv, p)
        };
        w.push(val);
        if val == 0 && order == 0 {
            order = k; // first zero = ord(P)
        }
        // Need terms up to r+2 to read the multiplier; stop two past the zero.
        if order != 0 && k >= order + 2 {
            break;
        }
        if k > cap {
            return None; // order too large for the cap
        }
        k += 1;
    }
    let r = order;

    // Multiplier (A,B): B = W(r+2)/(W(2)·W(r+1)), A = W(r+1)/B.
    let wr1 = w[r + 1];
    let wr2 = w[r + 2];
    if wr1 == 0 {
        return None;
    }
    let mb = mulm(wr2, mulm(w2_inv, invm(wr1, p), p), p);
    if mb == 0 {
        return None;
    }
    let ma = mulm(wr1, invm(mb, p), p);

    // QR balance over the apparition block [1, r-1] (W(r)=0 excluded).
    let mut qr = 0u64;
    let mut nqr = 0u64;
    for &wn in &w[1..r] {
        match legendre_u64(wn, p) {
            1 => qr += 1,
            -1 => nqr += 1,
            _ => {}
        }
    }
    let bias = if qr + nqr > 0 {
        (qr as f64 - nqr as f64) / (qr + nqr) as f64
    } else {
        0.0
    };

    Some(CurveBias {
        a,
        b,
        order: r as u64,
        qr,
        nqr,
        bias,
        chi_a: legendre_u64(ma, p),
        chi_b: legendre_u64(mb, p),
    })
}

/// First curve point with small `x`, `y≠0` (any odd prime `p`).
fn first_point_u64(p: u64, a: u64, b: u64) -> Option<(u64, u64)> {
    for x in 1..p {
        let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p;
        if rhs == 0 {
            continue;
        }
        if let Some(y) = sqrt_u64(rhs, p) {
            if y != 0 {
                return Some((x, y));
            }
        }
    }
    None
}

/// Aggregate census result.
#[derive(Clone, Debug)]
pub struct CensusSummary {
    pub p: u64,
    pub curves: usize,
    pub mean_bias: f64,
    pub std_bias: f64,
    pub abs_mean: f64,
    pub max_abs: f64,
    /// Count of curves with |bias| above the noise band `2/sqrt(samples)`.
    pub heavy_tail: usize,
    /// Mean |bias| split by multiplier-character class (χA,χB):
    /// (++, +-, -+, --) with per-class counts.
    pub by_class: [(usize, f64); 4],
    pub min_order: u64,
}

fn class_index(chi_a: i8, chi_b: i8) -> usize {
    match (chi_a >= 0, chi_b >= 0) {
        (true, true) => 0,   // (+,+)
        (true, false) => 1,  // (+,-)
        (false, true) => 2,  // (-,+)
        (false, false) => 3, // (-,-)
    }
}

/// Sweep curves `y²=x³+ax+b` over `F_p` (any odd prime) for
/// `a ∈ [0, a_max), b ∈ [0, b_max)`, skipping singular curves, and
/// aggregate the apparition-block residue bias.  Only curves whose chosen
/// point has order ≥ `min_order` (and ≤ `cap`) are counted.
pub fn census(
    p: u64,
    a_max: u64,
    b_max: u64,
    min_order: u64,
    cap: usize,
) -> (CensusSummary, Vec<CurveBias>) {
    let mut recs: Vec<CurveBias> = Vec::new();
    for a in 0..a_max {
        for b in 0..b_max {
            // discriminant 4a³+27b² ≠ 0
            let disc = (mulm(4, mulm(mulm(a, a, p), a, p), p) + mulm(27, mulm(b, b, p), p)) % p;
            if disc == 0 {
                continue;
            }
            if let Some((x, y)) = first_point_u64(p, a, b) {
                if let Some(rec) = block_bias_u64(p, a, b, x, y, cap) {
                    if rec.order >= min_order {
                        recs.push(rec);
                    }
                }
            }
        }
    }

    let n = recs.len();
    let (mut sum, mut sum_abs, mut sum_sq, mut max_abs) = (0.0, 0.0, 0.0, 0.0f64);
    let mut by_class = [(0usize, 0.0f64); 4];
    let mut min_order = u64::MAX;
    for r in &recs {
        sum += r.bias;
        sum_abs += r.bias.abs();
        sum_sq += r.bias * r.bias;
        max_abs = max_abs.max(r.bias.abs());
        let ci = class_index(r.chi_a, r.chi_b);
        by_class[ci].0 += 1;
        by_class[ci].1 += r.bias.abs();
        min_order = min_order.min(r.order);
    }
    let mean = if n > 0 { sum / n as f64 } else { 0.0 };
    let var = if n > 0 {
        sum_sq / n as f64 - mean * mean
    } else {
        0.0
    };
    for c in by_class.iter_mut() {
        if c.0 > 0 {
            c.1 /= c.0 as f64;
        }
    }
    // Noise band: a fair ±1 block of length m has bias std ≈ 1/sqrt(m).
    let heavy_tail = recs
        .iter()
        .filter(|r| r.bias.abs() > 2.0 / ((r.qr + r.nqr).max(1) as f64).sqrt())
        .count();

    (
        CensusSummary {
            p,
            curves: n,
            mean_bias: mean,
            std_bias: var.max(0.0).sqrt(),
            abs_mean: if n > 0 { sum_abs / n as f64 } else { 0.0 },
            max_abs,
            heavy_tail,
            by_class,
            min_order: if n > 0 { min_order } else { 0 },
        },
        recs,
    )
}

/// Render a [`CensusSummary`] as Markdown.
pub fn format_census(s: &CensusSummary) -> String {
    let cls = |i: usize, name: &str| {
        format!(
            "  - `{}`: {} curves, mean|bias|={:.4}\n",
            name, s.by_class[i].0, s.by_class[i].1
        )
    };
    format!(
        "### Census p={p} ({n} curves, min order {mo})\n\n\
         - mean bias = `{mean:+.5}`  (expect ≈ 0 if unbiased)\n\
         - std(bias) = `{std:.5}`\n\
         - mean |bias| = `{am:.5}`\n\
         - max |bias| = `{mx:.4}`\n\
         - heavy tail (|bias| > 2/√m): **{ht}/{n}** = {htp:.1}%\n\
         - by multiplier class (χA,χB):\n{c0}{c1}{c2}{c3}",
        p = s.p,
        n = s.curves,
        mo = s.min_order,
        mean = s.mean_bias,
        std = s.std_bias,
        am = s.abs_mean,
        mx = s.max_abs,
        ht = s.heavy_tail,
        htp = 100.0 * s.heavy_tail as f64 / s.curves.max(1) as f64,
        c0 = cls(0, "(+,+)"),
        c1 = cls(1, "(+,-)"),
        c2 = cls(2, "(-,+)"),
        c3 = cls(3, "(-,-)"),
    )
}

// ── F_p ↔ Z bridge: integer EDS and Silverman–Stephens signs ────────────────
//
// The χ-period over F_p (§3) is an *arithmetic* invariant — the quadratic
// character of the mod-p multiplier.  Over Z, Silverman–Stephens (2006) show
// the *sign* of an integer EDS is governed by an *archimedean* invariant: the
// real elliptic logarithm of P / the real period.  This section computes the
// genuine integer EDS, validates it against OEIS A006769 (curve 37a, point
// (0,0)), measures its archimedean sign behaviour, and reduces it mod p to
// show the two "periods" are orthogonal objects, not a reduction of one
// another.

fn cube(x: &BigInt) -> BigInt {
    x * x * x
}
fn sq_i(x: &BigInt) -> BigInt {
    x * x
}

/// Integer EDS with `W(0)=0, W(1)=1` and the given `W(2),W(3),W(4)` seeds,
/// extended by the duplication formulas (exact over `Z`).  Panics if a
/// half-index division is not exact (i.e. the seeds are not a valid EDS).
pub fn eds_integer(w2: i64, w3: i64, w4: i64, count: usize) -> Vec<BigInt> {
    assert!(count >= 5);
    let d2 = BigInt::from(w2);
    let mut w = vec![
        BigInt::from(0),
        BigInt::from(1),
        d2.clone(),
        BigInt::from(w3),
        BigInt::from(w4),
    ];
    for k in 5..count {
        let val = if k % 2 == 1 {
            let n = (k - 1) / 2;
            &w[n + 2] * cube(&w[n]) - &w[n - 1] * cube(&w[n + 1])
        } else {
            let n = k / 2;
            let bracket = &w[n + 2] * sq_i(&w[n - 1]) - &w[n - 2] * sq_i(&w[n + 1]);
            let num = &w[n] * &bracket;
            let q = &num / &d2;
            debug_assert_eq!(&q * &d2, num, "non-exact EDS division at k={}", k);
            q
        };
        w.push(val);
    }
    w
}

/// Sign sequence of an integer EDS: `+1`, `-1`, or `0`.
pub fn signs(seq: &[BigInt]) -> Vec<i8> {
    seq.iter()
        .map(|w| match w.sign() {
            Sign::Plus => 1,
            Sign::Minus => -1,
            Sign::NoSign => 0,
        })
        .collect()
}

/// Smallest period `π ≤ max_period` of the sign sequence over the index
/// range `[start, len)`, or `None` if the signs are aperiodic up to that
/// bound (the Silverman–Stephens "irrational rotation number" case).
pub fn sign_period(s: &[i8], start: usize, max_period: usize) -> Option<usize> {
    let n = s.len();
    'p: for period in 1..=max_period.min(n - start - 1) {
        for i in start..(n - period) {
            if s[i] != s[i + period] {
                continue 'p;
            }
        }
        return Some(period);
    }
    None
}

/// Result of reducing an integer EDS mod `p` and reading its F_p structure.
#[derive(Clone, Debug)]
pub struct BridgeReduction {
    pub p: u64,
    /// Rank of apparition mod p (first zero) = ord(P mod p) for good p.
    pub order: u64,
    pub chi_a: i8,
    pub chi_b: i8,
    /// χ-period = r·j_χ from the §3 multiplier-character closed form.
    pub chi_period: u64,
}

/// χ-period multiplier `j_χ` from the multiplier characters (the §3 law,
/// valid for all `r`): smallest `j≥1` with `χ(B)^j=1` and
/// `χ(A)^j·χ(B)^{r·j(j-1)/2}=1`.
fn chi_period_mult(chi_a: i8, chi_b: i8, r: u64) -> u64 {
    for j in 1u64..=8 {
        if pm_pow(chi_b, j % 2 == 1) != 1 {
            continue;
        }
        let exp_odd = ((r as u128) * (j as u128) * ((j as u128) - 1) / 2) % 2 == 1;
        if pm_pow(chi_a, j % 2 == 1) * pm_pow(chi_b, exp_odd) == 1 {
            return j;
        }
    }
    0
}

/// Reduce an integer EDS mod `p`, find its rank of apparition and the
/// multiplier characters, and apply the §3 χ-period law.  `None` if the
/// sequence is too short (need ≥ r+3 terms) or degenerate mod p.
pub fn reduce_and_analyze(seq: &[BigInt], p: u64) -> Option<BridgeReduction> {
    let m = BigInt::from(p);
    let red: Vec<u64> = seq
        .iter()
        .map(|w| {
            let r = ((w % &m) + &m) % &m;
            let (_, digits) = r.to_u64_digits();
            digits.first().copied().unwrap_or(0)
        })
        .collect();
    // rank of apparition: first zero at index ≥ 1.
    let r = (1..red.len()).find(|&i| red[i] == 0)?;
    if r + 2 >= red.len() {
        return None;
    }
    let w2 = red[2];
    if w2 == 0 || red[r + 1] == 0 {
        return None;
    }
    // B = W(r+2)/(W(2)·W(r+1)), A = W(r+1)/B.
    let mb = mulm(red[r + 2], mulm(invm(w2, p), invm(red[r + 1], p), p), p);
    if mb == 0 {
        return None;
    }
    let ma = mulm(red[r + 1], invm(mb, p), p);
    let chi_a = legendre_u64(ma, p);
    let chi_b = legendre_u64(mb, p);
    let j = chi_period_mult(chi_a, chi_b, r as u64);
    Some(BridgeReduction {
        p,
        order: r as u64,
        chi_a,
        chi_b,
        chi_period: (r as u64) * j,
    })
}

// ── intrinsic multiplier characters (program item 2) ───────────────────────
//
// The §3 χ-period and §4.5 reflection law are governed by the two sign bits
// (χ(A), χ(B)) of the EDS shift multiplier W(n+r) = A·Bⁿ·W(n).  These bits
// are not opaque: from the extraction B = W(r+2)/(W(2)·W(r+1)) and
// A = W(r+1)/B = W(2)·W(r+1)²/W(r+2), and because W(r+1)² is a square,
//
//     χ(A) = χ( W(2)·W(r+2) ),
//     χ(B) = χ( W(2)·W(r+1)·W(r+2) ).                                  (CF)
//
// There is also the structural identity (derived from Ward's relation at the
// rank of apparition, using ψ_r(P)=0)
//
//     Bʳ = − W(r+1)·W(r−1),                                            (BR)
//
// which for *odd* r collapses (CF) to the curve-near-intrinsic form
// χ(B) = χ(−1)·χ(W(r+1))·χ(W(r−1)),  χ(A) = χ(−1)·χ(W(r−1)).
// The remaining genuinely-open step — expressing these without computing the
// O(r) sequence at all — runs through B² = −W(r+1)/W(r−1), conjecturally a
// self-pairing (Tate/Frey–Rück) value; see research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md §5.5.

/// Closed-form multiplier characters `(χ(A), χ(B))` computed directly from the
/// sequence values `W(2), W(r+1), W(r+2)` via `(CF)` — no inversion to recover
/// `A, B`.  `None` if `P` has no usable order.
pub fn multiplier_chars_closed_form(
    p: &BigUint,
    a: &BigUint,
    b: &BigUint,
    px: &BigUint,
    py: &BigUint,
) -> Option<(i8, i8)> {
    let pu: u64 = p.clone().try_into().ok()?;
    let r = point_order(px, py, a, p, pu + 2)? as usize;
    let w = eds_sequence(p, a, b, px, py, r + 3);
    let w2 = &w[2];
    let wr1 = &w[r + 1];
    let wr2 = &w[r + 2];
    let chi_a = legendre(&((w2 * wr2) % p), p);
    let chi_b = legendre(&((&((w2 * wr1) % p) * wr2) % p), p);
    Some((chi_a, chi_b))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A concrete toy curve: y² = x³ + 37x + 2 (mod 1009).
    fn toy() -> (BigUint, BigUint, BigUint) {
        (
            BigUint::from(1009u32),
            BigUint::from(37u32),
            BigUint::from(2u32),
        )
    }

    #[test]
    fn rank_of_apparition_equals_order() {
        let (p, a, b) = toy();
        let (px, py, ord) = find_toy_point(&p, &a, &b, 1, 7).expect("toy point exists");
        let r = analyze(&p, &a, &b, &px, &py);
        assert_eq!(r.order, ord);
        // The defining property: first zero of the EDS is exactly ord(P).
        assert_eq!(
            r.rank_of_apparition, r.order,
            "rank of apparition must equal ord(P)"
        );
    }

    #[test]
    fn apparition_law_holds() {
        let (p, a, b) = toy();
        let (px, py, _) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
        let r = analyze(&p, &a, &b, &px, &py);
        // W(n) = 0 ⟺ [n]P = O, checked against honest point arithmetic.
        assert!(
            r.apparition_consistent,
            "apparition law W(n)=0 ⟺ [n]P=O must hold"
        );
    }

    #[test]
    fn legendre_matches_euler() {
        let p = BigUint::from(1009u32);
        // 2 is a QR mod 1009? 1009 ≡ 1 (mod 8) ⇒ 2 is a QR.
        assert_eq!(legendre(&BigUint::from(0u32), &p), 0);
        // sanity: a square is always a QR.
        for v in 1u32..50 {
            let sq = (v * v) % 1009;
            assert_eq!(legendre(&BigUint::from(sq), &p), 1, "{} should be QR", sq);
        }
    }

    #[test]
    fn net_zero_lattice_recovers_discrete_log() {
        let (p, a, b) = toy();
        let (px, py, ord) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
        // Choose a non-trivial true discrete log and recover it from the
        // vanishing locus of the 2-D net.
        let k_true = (ord / 2).max(2) % ord;
        let grid = ord + 1;
        let (k_rec, (za, zb)) = recover_dl_from_net_zeros(&px, &py, &a, &p, ord, k_true, grid)
            .expect("found a net zero");
        assert_eq!(k_rec % ord, k_true % ord, "net zero must encode the DL");
        // Verify the recovered relation: za + zb·k ≡ 0 (mod ord).
        let lhs = (za as u64 + (zb as u64) * (k_true % ord)) % ord;
        assert_eq!(lhs, 0, "zero must lie on the slope-k lattice");
    }

    #[test]
    fn multiplier_law_and_periods() {
        let (p, a, b) = toy();
        let (px, py, _) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
        let r = analyze(&p, &a, &b, &px, &py);
        // The Ward/Lauter–Stange shift law must verify exactly.
        assert!(r.mult_law_holds, "W(n+r) = A·Bⁿ·W(n) must hold");
        // χ period must divide W period (χ is a function of W).
        assert!(r.period_w > 0 && r.period_chi > 0);
        assert_eq!(r.period_w % r.period_chi, 0, "π_χ must divide π_W");
        // Both periods are integer multiples of the rank of apparition.
        assert_eq!(r.period_w % r.order, 0);
        assert_eq!(r.period_chi % r.order, 0);
        // QR balance accounts for the whole apparition block [1, r].
        let (qr, nqr, zero) = r.qr_balance;
        assert_eq!(qr + nqr + zero, r.order);
        // χ(A), χ(B) are genuine signs.
        assert!(r.chi_a != 0 && r.chi_b != 0);
    }

    #[test]
    fn census_runs_and_is_sane() {
        // Small fast sweep on p=4099 (≡3 mod 4).
        let (s, recs) = census(4099, 12, 12, 50, 5000);
        assert!(
            s.curves >= 20,
            "expected a decent number of curves, got {}",
            s.curves
        );
        // Per-curve sanity: QR+NQR ≈ order-1 (block excludes the single zero).
        for r in &recs {
            assert_eq!(r.qr + r.nqr, r.order - 1);
            assert!(r.bias.abs() <= 1.0);
            assert!(r.chi_a != 0 && r.chi_b != 0);
        }
        // The u64 census must agree with the BigUint reference on a shared curve.
        // Find a census curve and re-derive its bias via analyze().
        let probe = &recs[0];
        let p = BigUint::from(4099u32);
        let a = BigUint::from(probe.a);
        let b = BigUint::from(probe.b);
        let (px, py, _) = find_toy_point(&p, &a, &b, 1, 50).unwrap();
        let rep = analyze(&p, &a, &b, &px, &py);
        // analyze counts the zero inside [1,r]; census excludes it — compare QR/NQR only.
        assert_eq!((rep.qr_balance.0, rep.qr_balance.1), (probe.qr, probe.nqr));
    }

    #[test]
    fn reflection_symmetry_law() {
        // For p ≡ 3 (mod 4), χ(−1) = −1, and the EDS reflection
        //   W(r−n) = −A·B^{−n}·W(n)
        // forces  χ(W(n))·χ(W(r−n)) = χ(−1)·χ(A)·χ(B)^n  for all n,
        // except the fixed point n = r/2 when r is even.
        let p = BigUint::from(4099u32);
        let chi_neg1 = legendre(&(&p - BigUint::from(1u32)), &p);
        assert_eq!(chi_neg1, -1, "p must be ≡ 3 (mod 4)");

        // a=2,b=7 is the heaviest-bias curve in the p=4099 census, class (−,+).
        let a = BigUint::from(2u32);
        let b = BigUint::from(7u32);
        let (px, py, ord) = find_toy_point(&p, &a, &b, 1, 80).unwrap();
        let rep = analyze(&p, &a, &b, &px, &py);
        let r = ord as usize;
        let w = eds_sequence(&p, &a, &b, &px, &py, 2 * r + 4);

        let mut bpow = rep.chi_b; // χ(B)^n, starting n=1
        for n in 1..r {
            if 2 * n != r {
                let lhs = legendre(&w[n], &p) * legendre(&w[r - n], &p);
                let rhs = chi_neg1 * rep.chi_a * bpow;
                assert_eq!(lhs, rhs, "reflection law failed at n={}", n);
            }
            bpow *= rep.chi_b;
        }
    }

    #[test]
    fn plus_plus_class_is_balanced() {
        // The (+,+) class must be (essentially) perfectly balanced, while
        // some other class carries real bias — the structural signature.
        let (s, recs) = census(4099, 30, 30, 80, 5000);
        let pp = s.by_class[0]; // (+,+)
        let mp = s.by_class[2]; // (−,+) — the reinforcing class
        assert!(pp.0 > 10 && mp.0 > 10, "need populated classes");
        assert!(pp.1 < 0.01, "(+,+) mean|bias| should be ~0, got {}", pp.1);
        assert!(mp.1 > pp.1, "(−,+) must carry more bias than (+,+)");
        // Every heavy-bias curve should be outside the (+,+) class.
        for r in recs.iter().filter(|r| r.bias.abs() > 0.1) {
            assert!(
                !(r.chi_a == 1 && r.chi_b == 1),
                "a (+,+) curve cannot have large bias: {:?}",
                r
            );
        }
    }

    #[test]
    fn reflection_law_holds_for_p_eq_1_mod_4() {
        // Same identity (◆), but now χ(−1) = +1, so the balanced class is
        // (−,+) instead of (+,+).  Verify (◆) term-by-term on a p≡1 curve.
        let p = BigUint::from(4093u32);
        let chi_neg1 = legendre(&(&p - BigUint::from(1u32)), &p);
        assert_eq!(chi_neg1, 1, "p must be ≡ 1 (mod 4)");
        let a = BigUint::from(3u32);
        let b = BigUint::from(9u32);
        let (px, py, ord) = find_toy_point(&p, &a, &b, 1, 80).unwrap();
        let rep = analyze(&p, &a, &b, &px, &py);
        let r = ord as usize;
        let w = eds_sequence(&p, &a, &b, &px, &py, 2 * r + 4);
        let mut bpow = rep.chi_b;
        for n in 1..r {
            if 2 * n != r {
                let lhs = legendre(&w[n], &p) * legendre(&w[r - n], &p);
                let rhs = chi_neg1 * rep.chi_a * bpow;
                assert_eq!(lhs, rhs, "reflection law (p≡1) failed at n={}", n);
            }
            bpow *= rep.chi_b;
        }
    }

    #[test]
    fn balanced_class_flips_for_p_eq_1_mod_4() {
        // The reflection law (◆) predicts the block is forced balanced iff
        //   χ(B)=+1  AND  χ(A) = −χ(−1).
        // For p ≡ 1 (mod 4), χ(−1)=+1, so the balanced class flips from
        // (+,+) (the p≡3 case) to (−,+).
        let p = 4093u64; // 4093 ≡ 1 (mod 4), prime
        assert_eq!(p % 4, 1);
        let (s, _recs) = census(p, 40, 40, 80, 5000);
        let pp = s.by_class[0]; // (+,+)
        let mp = s.by_class[2]; // (−,+)
        assert!(pp.0 > 10 && mp.0 > 10, "need populated classes");
        // (−,+) is now the balanced class.
        assert!(mp.1 < 0.01, "(−,+) should be ~0 for p≡1, got {}", mp.1);
        // and (+,+) now carries bias (it is no longer the balanced class).
        assert!(pp.1 > mp.1, "(+,+) must lose its balance at p≡1");
    }

    #[test]
    fn sqrt_u64_roundtrips_both_residues() {
        for &p in &[
            4099u64, /*≡3*/
            4093,    /*≡1*/
            10009,   /*≡1*/
            10007,   /*≡3*/
        ] {
            let mut squares = 0;
            for v in 1..200u64 {
                let sq = (v * v) % p;
                let r = sqrt_u64(sq, p).expect("square has a root");
                assert_eq!((r * r) % p, sq, "sqrt wrong for {} mod {}", sq, p);
                squares += 1;
            }
            assert!(squares > 0);
            // A guaranteed non-residue returns None.
            // (find one: smallest n with legendre = -1)
            let nqr = (2..p).find(|&n| legendre_u64(n, p) == -1).unwrap();
            assert!(sqrt_u64(nqr, p).is_none());
        }
    }

    #[test]
    fn decimation_identity_holds() {
        // ψ_{κn}(P) = ψ_n([κ]P)·ψ_κ(P)^{n²}, checked on residues for several κ.
        let (p, a, b) = toy();
        let (px, py, m) = find_toy_point(&p, &a, &b, 1, 30).unwrap();
        for k in [2u64, 3, 5, 7] {
            let r = localisation(&p, &a, &b, &px, &py, m, k, 24);
            if let Some(res) = r {
                assert!(res.decimation_ok, "DEC-χ must hold for k={}", k);
            }
        }
    }

    #[test]
    fn localisation_pins_the_true_k() {
        // The residue window must, for most k, narrow to a unique candidate,
        // and that candidate is the true k (DEC-χ verified along the way).
        let (p, a, b) = toy();
        let (px, py, m) = find_toy_point(&p, &a, &b, 1, 30).unwrap();
        let mut unique = 0;
        let mut total = 0;
        for k in 2..m.min(40) {
            if let Some(res) = localisation(&p, &a, &b, &px, &py, m, k, 40) {
                total += 1;
                assert!(res.decimation_ok);
                if res.unique_window.is_some() {
                    unique += 1;
                }
            }
        }
        assert!(total > 5, "need several valid k");
        // The residue pattern pins k up to sign for essentially every k.
        assert!(
            unique * 2 >= total,
            "expected most k to pin (up to ±), got {}/{}",
            unique,
            total
        );
    }

    #[test]
    fn localisation_sweep_sign_dichotomy_and_log_window() {
        // p ≡ 3 (mod 4): the sign is resolved (k exact), and the residue
        // window scales ~ log2(m).
        let p3 = BigUint::from(2003u32);
        let (px, py, m3) =
            find_toy_point(&p3, &BigUint::from(11u32), &BigUint::from(19u32), 1, 30).unwrap();
        let s3 = localisation_sweep(
            &p3,
            &BigUint::from(11u32),
            &BigUint::from(19u32),
            &px,
            &py,
            m3,
            48,
            120,
        );
        assert!(s3.decimation_ok);
        assert_eq!(s3.pinned, s3.tested, "every k pins up to ±");
        assert_eq!(s3.sign_resolved, s3.pinned, "p≡3 resolves the sign");
        // generous O(log m) bound on the window.
        assert!(
            (s3.max_window_seen as f64) <= 4.0 * (m3 as f64).log2(),
            "window {} should be ~log2(m={})",
            s3.max_window_seen,
            m3
        );

        // p ≡ 1 (mod 4): k pins, but only up to sign (sign never resolved).
        let p1 = BigUint::from(1009u32);
        let (qx, qy, m1) =
            find_toy_point(&p1, &BigUint::from(37u32), &BigUint::from(2u32), 1, 30).unwrap();
        let s1 = localisation_sweep(
            &p1,
            &BigUint::from(37u32),
            &BigUint::from(2u32),
            &qx,
            &qy,
            m1,
            48,
            120,
        );
        assert!(s1.decimation_ok);
        assert_eq!(s1.pinned, s1.tested, "every k pins up to ±");
        assert_eq!(s1.sign_resolved, 0, "p≡1 cannot resolve the sign");
    }

    /// OEIS A006769: integer EDS for curve 37a, point (0,0), n = 0..25.
    fn a006769() -> [i64; 26] {
        [
            0, 1, 1, -1, 1, 2, -1, -3, -5, 7, -4, -23, 29, 59, 129, -314, -65, 1529, -3689, -8209,
            -16264, 83313, 113689, -620297, 2382785, 7869898,
        ]
    }

    #[test]
    fn integer_eds_matches_oeis_a006769() {
        let w = eds_integer(1, -1, 1, 26);
        let known = a006769();
        for n in 0..26 {
            assert_eq!(w[n], BigInt::from(known[n]), "A006769 mismatch at n={}", n);
        }
    }

    #[test]
    fn integer_eds_signs_aperiodic_for_37a() {
        // 37a has Δ>0 (two real components) and an irrational rotation
        // number, so Silverman–Stephens ⇒ the sign sequence is aperiodic.
        let w = eds_integer(1, -1, 1, 220);
        let s = signs(&w);
        assert!(
            sign_period(&s, 1, 80).is_none(),
            "37a EDS signs should be aperiodic up to period 80"
        );
    }

    #[test]
    fn bridge_reduction_matches_group_order_and_chi_law() {
        // Reduce the integer EDS mod p and confirm: (a) its rank of
        // apparition equals ord(P mod p) computed independently by point
        // arithmetic on Y²=x³−x+1/4, P=(0,1/2); (b) the χ-period obeys the
        // §3 law (r or 2r).  This shows the F_p χ-structure is arithmetic,
        // unrelated to the archimedean sign behaviour above.
        let w = eds_integer(1, -1, 1, 140);
        for p in [7u64, 11, 13, 23, 29] {
            let br = reduce_and_analyze(&w, p).expect("reduction ok");
            let pp = BigUint::from(p);
            let a = BigUint::from(p - 1); // −1 mod p
            let _b = BigUint::from(invm(4, p)); // 1/4 mod p
            let px = BigUint::from(0u32);
            let py = BigUint::from(invm(2, p)); // 1/2 mod p
            let ord = point_order(&px, &py, &a, &pp, 2 * p + 4).expect("finite order");
            assert_eq!(
                br.order, ord,
                "apparition under reduction must equal ord(P mod {})",
                p
            );
            let j = br.chi_period / br.order;
            assert!(
                j == 1 || j == 2,
                "χ-period must be r or 2r, got j={} (p={})",
                j,
                p
            );
        }
    }

    #[test]
    fn multiplier_chars_closed_form_matches_extraction() {
        // (CF): χ(A)=χ(W2·W(r+2)), χ(B)=χ(W2·W(r+1)·W(r+2)) must agree with
        // the characters of the A,B extracted by inversion in analyze().
        for (pp, aa, bb) in [
            (1009u32, 37u32, 2u32),
            (1013, 5, 7),
            (2003, 11, 19),
            (4099, 5, 3),
            (2017, 7, 5),
        ] {
            let (p, a, b) = (BigUint::from(pp), BigUint::from(aa), BigUint::from(bb));
            let (px, py, _) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
            let rep = analyze(&p, &a, &b, &px, &py);
            let (ca, cb) = multiplier_chars_closed_form(&p, &a, &b, &px, &py).unwrap();
            assert_eq!((ca, cb), (rep.chi_a, rep.chi_b), "CF mismatch at p={}", pp);
        }
    }

    #[test]
    fn structural_identity_b_pow_r() {
        // (BR): Bʳ = −W(r+1)·W(r−1) (mod p), and the extraction relations
        // A·B = W(r+1),  B = W(r+2)/(W(2)·W(r+1)).
        for (pp, aa, bb) in [(1009u32, 37u32, 2u32), (2003, 11, 19), (4099, 5, 3)] {
            let (p, a, b) = (BigUint::from(pp), BigUint::from(aa), BigUint::from(bb));
            let (px, py, _) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
            let rep = analyze(&p, &a, &b, &px, &py);
            let r = rep.order as usize;
            let w = eds_sequence(&p, &a, &b, &px, &py, r + 3);
            // A·B = W(r+1)
            assert_eq!(
                (&rep.mult_a * &rep.mult_b) % &p,
                w[r + 1],
                "AB=W(r+1) p={}",
                pp
            );
            // Bʳ = −W(r+1)·W(r−1)
            let bpow = rep.mult_b.modpow(&BigUint::from(rep.order), &p);
            let rhs = m_sub(&BigUint::zero(), &((&w[r + 1] * &w[r - 1]) % &p), &p);
            assert_eq!(bpow, rhs, "Bʳ=−W(r+1)W(r−1) p={}", pp);
            // For odd r: χ(B) = χ(−1)·χ(W(r+1))·χ(W(r−1)).
            if r % 2 == 1 {
                let chi_neg1 = legendre(&(&p - BigUint::from(1u32)), &p);
                let pred = chi_neg1 * legendre(&w[r + 1], &p) * legendre(&w[r - 1], &p);
                assert_eq!(pred, rep.chi_b, "odd-r χ(B) form p={}", pp);
            }
        }
    }

    #[test]
    fn report_renders() {
        let (p, a, b) = toy();
        let (px, py, _) = find_toy_point(&p, &a, &b, 1, 7).unwrap();
        let r = analyze(&p, &a, &b, &px, &py);
        let md = format_report(&r);
        assert!(md.contains("EDS-Residue analysis"));
        assert!(md.contains("Shift multiplier"));
    }
}
