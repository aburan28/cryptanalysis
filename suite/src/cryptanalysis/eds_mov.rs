//! **`F_{p²}` reduced pairing and a working MOV attack on supersingular
//! curves** — the one regime where the EDS/elliptic-net→pairing machinery
//! actually *breaks* the ECDLP (§5.10 of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`).
//!
//! For `y²=x³+x` over `p≡3 (mod 4)` (supersingular, `#E=p+1`, embedding
//! degree 2), the distortion map `φ(x,y) = (−x, iy)` with `i²=−1 ∈ F_{p²}`
//! sends `P ∈ E(F_p)` to an independent point in `E(F_{p²})`.  The modified
//! reduced Tate pairing `t_r(P, φ(P)) = f_{r,P}(φ(P))^{(p²−1)/r} ∈ μ_r ⊂
//! F_{p²}^*` is then **non-degenerate**, and bilinearity turns the ECDLP
//! `Q=[k]P` into a DLP in the small cyclic group `μ_r` (MOV / Frey–Rück).
//!
//! Everything is `u64` (`p` small so `p² < 2^64`).  `F_{p²} = F_p[i]/(i²+1)`,
//! elements `(a,b) = a+bi`.  The Miller routine evaluates the `F_p`-rational
//! function `f_{r,P}` at the `F_{p²}` point `φ(P)`, accumulating in `F_{p²}`.

use crate::cryptanalysis::eds_tate::{ec_mul, ec_order, Pt};

// ── F_p helpers ─────────────────────────────────────────────────────────────
#[inline]
fn mulm(x: u64, y: u64, p: u64) -> u64 {
    ((x as u128 * y as u128) % p as u128) as u64
}
#[inline]
fn addm(x: u64, y: u64, p: u64) -> u64 {
    (x + y) % p
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
fn invm(x: u64, p: u64) -> u64 {
    powm(x, p - 2, p)
}

// ── F_{p²} = F_p[i], i² = −1  (valid for p ≡ 3 mod 4) ───────────────────────
pub type Fp2 = (u64, u64);

#[cfg(test)]
#[inline]
fn f2_add(x: Fp2, y: Fp2, p: u64) -> Fp2 {
    (addm(x.0, y.0, p), addm(x.1, y.1, p))
}
#[inline]
fn f2_sub(x: Fp2, y: Fp2, p: u64) -> Fp2 {
    (subm(x.0, y.0, p), subm(x.1, y.1, p))
}
#[inline]
fn f2_mul(x: Fp2, y: Fp2, p: u64) -> Fp2 {
    let (a, b) = x;
    let (c, d) = y;
    // (a+bi)(c+di) = (ac − bd) + (ad + bc) i
    (
        subm(mulm(a, c, p), mulm(b, d, p), p),
        addm(mulm(a, d, p), mulm(b, c, p), p),
    )
}
fn f2_inv(x: Fp2, p: u64) -> Fp2 {
    let (a, b) = x;
    let n = addm(mulm(a, a, p), mulm(b, b, p), p); // norm = a²+b² (≠0 for p≡3 mod4)
    let ni = invm(n, p);
    (mulm(a, ni, p), mulm(subm(0, b, p), ni, p))
}
fn f2_pow(mut base: Fp2, mut e: u64, p: u64) -> Fp2 {
    let mut r = (1u64, 0u64);
    while e > 0 {
        if e & 1 == 1 {
            r = f2_mul(r, base, p);
        }
        base = f2_mul(base, base, p);
        e >>= 1;
    }
    r
}
#[inline]
fn f2_of(x: u64) -> Fp2 {
    (x, 0)
}

// ── Miller over F_{p²}: f_{r,P}(R), P ∈ E(F_p), R ∈ E(F_{p²}) ────────────────

/// Doubling step: `(g_{T,T}(R), 2T)`; `T` an `F_p` affine point, `R` an
/// `F_{p²}` point.  Returns `g ∈ F_{p²}` and `2T ∈ E(F_p)` (`None` = `O`).
fn step_double_fp2(t: (u64, u64), rx: Fp2, ry: Fp2, a: u64, p: u64) -> Option<(Fp2, Pt)> {
    let (x1, y1) = t;
    if y1 == 0 {
        // 2T = O; vertical tangent x − x1.
        return Some((f2_sub(rx, f2_of(x1), p), None));
    }
    let lam = mulm(
        addm(mulm(3, mulm(x1, x1, p), p), a, p),
        invm(mulm(2, y1, p), p),
        p,
    );
    let x3 = subm(subm(mulm(lam, lam, p), x1, p), x1, p);
    let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
    // l(R) = R_y − y1 − λ(R_x − x1)
    let l = f2_sub(
        f2_sub(ry, f2_of(y1), p),
        f2_mul(f2_of(lam), f2_sub(rx, f2_of(x1), p), p),
        p,
    );
    let v = f2_sub(rx, f2_of(x3), p);
    if v == (0, 0) {
        return None;
    }
    Some((f2_mul(l, f2_inv(v, p), p), Some((x3, y3))))
}

/// Addition step: `(g_{T,P}(R), T+P)`.
fn step_add_fp2(t: Pt, pp: (u64, u64), rx: Fp2, ry: Fp2, a: u64, p: u64) -> Option<(Fp2, Pt)> {
    let (x1, y1) = match t {
        Some(v) => v,
        None => return Some(((1, 0), Some(pp))),
    };
    let (x2, y2) = pp;
    if x1 == x2 {
        if (y1 + y2) % p == 0 {
            // T = −P; vertical x − x2.
            return Some((f2_sub(rx, f2_of(x2), p), None));
        }
        return step_double_fp2((x1, y1), rx, ry, a, p);
    }
    let lam = mulm(subm(y2, y1, p), invm(subm(x2, x1, p), p), p);
    let x3 = subm(subm(mulm(lam, lam, p), x1, p), x2, p);
    let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
    let l = f2_sub(
        f2_sub(ry, f2_of(y1), p),
        f2_mul(f2_of(lam), f2_sub(rx, f2_of(x1), p), p),
        p,
    );
    let v = f2_sub(rx, f2_of(x3), p);
    if v == (0, 0) {
        return None;
    }
    Some((f2_mul(l, f2_inv(v, p), p), Some((x3, y3))))
}

/// `f_{r,P}(R) ∈ F_{p²}` via Miller (`div f = r(P) − r(O)`, `rP=O`).
fn miller_fp2(pp: (u64, u64), rx: Fp2, ry: Fp2, r: u64, a: u64, p: u64) -> Option<Fp2> {
    let mut f = (1u64, 0u64);
    let mut t: Pt = Some(pp);
    let nbits = 64 - r.leading_zeros();
    for i in (0..nbits - 1).rev() {
        let tc = t?;
        let (gd, t2) = step_double_fp2(tc, rx, ry, a, p)?;
        f = f2_mul(f2_mul(f, f, p), gd, p);
        t = t2;
        if (r >> i) & 1 == 1 {
            let (ga, t3) = step_add_fp2(t, pp, rx, ry, a, p)?;
            f = f2_mul(f, ga, p);
            t = t3;
        }
    }
    Some(f)
}

/// Distortion map `φ(x,y) = (−x, iy)` for `y²=x³+x`: returns the `F_{p²}`
/// coordinates `(R_x, R_y)` of `φ(P)`.
fn distortion(pp: (u64, u64), p: u64) -> (Fp2, Fp2) {
    let (x, y) = pp;
    ((subm(0, x, p), 0), (0, y)) // (−x) + 0·i,  0 + y·i
}

/// Modified reduced Tate pairing `t_r(P', φ(P)) ∈ μ_r ⊂ F_{p²}^*`, where `P'`
/// is the Miller base point (use `P'=P` for the self/distortion pairing, or
/// `P'=Q` for `t_r(Q, φ(P))`).  `r | p+1` (supersingular ⇒ embedding deg 2).
pub fn modified_tate(base: (u64, u64), phi_of: (u64, u64), r: u64, a: u64, p: u64) -> Option<Fp2> {
    let (rx, ry) = distortion(phi_of, p);
    let f = miller_fp2(base, rx, ry, r, a, p)?;
    if f == (0, 0) {
        return None;
    }
    let exp = (p * p - 1) / r; // p² − 1 fits in u64 for toy p
    let t = f2_pow(f, exp, p);
    if t == (0, 0) {
        None
    } else {
        Some(t)
    }
}

// ── the MOV attack ──────────────────────────────────────────────────────────

/// Solve the supersingular ECDLP `Q = [k]P` (with `ord(P)=r`) by transferring
/// to a DLP in `μ_r ⊂ F_{p²}^*` via the distortion Tate pairing, then a
/// brute-force / generic DLP in the small group `μ_r`.  Returns `k mod r`.
pub fn mov_solve(pp: (u64, u64), qq: (u64, u64), r: u64, a: u64, p: u64) -> Option<u64> {
    // α = t_r(P, φ(P)),  β = t_r(Q, φ(P)) = α^k.
    let alpha = modified_tate(pp, pp, r, a, p)?;
    let beta = modified_tate(qq, pp, r, a, p)?;
    // DLP in μ_r: find k with α^k = β.
    let mut acc = (1u64, 0u64);
    for k in 0..r {
        if acc == beta {
            return Some(k);
        }
        acc = f2_mul(acc, alpha, p);
    }
    None
}

/// Find a point of exact order `target` on `y²=x³+ax+b` over `F_p`
/// (`p≡3 mod 4`, so `sqrt = rhs^{(p+1)/4}`).
pub fn point_of_order(p: u64, a: u64, b: u64, target: u64) -> Option<(u64, u64)> {
    for x in 0..p {
        let rhs = (addm(addm(mulm(mulm(x, x, p), x, p), mulm(a, x, p), p), b, p)) % p;
        if rhs == 0 {
            continue;
        }
        let y = powm(rhs, (p + 1) / 4, p);
        if mulm(y, y, p) != rhs || y == 0 {
            continue;
        }
        let pt = Some((x, y));
        let ord = ec_order(pt, a, p, 2 * p + 4)?;
        if ord % target == 0 {
            let red = ec_mul(ord / target, pt, a, p)?;
            if ec_order(Some(red), a, p, target + 1) == Some(target) {
                return Some(red);
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn distortion_point_is_on_curve_over_fp2() {
        // φ(P)=(−x, iy) must satisfy Y² = X³ + X over F_{p²}.
        let (p, a, b) = (1283u64, 1u64, 0u64);
        let pp = point_of_order(p, a, b, 107).expect("order-107 point");
        let (rx, ry) = distortion(pp, p);
        let lhs = f2_mul(ry, ry, p);
        let x3 = f2_mul(f2_mul(rx, rx, p), rx, p);
        let rhs = f2_add(x3, f2_mul(f2_of(a), rx, p), p); // X³ + X (b=0)
        assert_eq!(lhs, rhs, "φ(P) must lie on the curve over F_{{p²}}");
    }

    #[test]
    fn pairing_is_nondegenerate_and_bilinear() {
        let (p, a, b) = (1283u64, 1u64, 0u64);
        let r = 107u64; // 107 | p+1 = 1284
        let pp = point_of_order(p, a, b, r).expect("order-r point");
        let alpha = modified_tate(pp, pp, r, a, p).expect("pairing");
        // lands in μ_r, nondegenerate
        assert_eq!(f2_pow(alpha, r, p), (1, 0), "t^r = 1");
        assert_ne!(alpha, (1, 0), "distortion pairing must be non-degenerate");
        // bilinear: t([c]P, φ(P)) = α^c
        for c in 2..6u64 {
            let cp = ec_mul(c, Some(pp), a, p).unwrap();
            let tc = modified_tate(cp, pp, r, a, p).unwrap();
            assert_eq!(tc, f2_pow(alpha, c, p), "bilinearity at c={}", c);
        }
    }

    #[test]
    fn mov_attack_recovers_discrete_log() {
        // End-to-end: a working MOV break of a supersingular ECDLP.
        let (p, a, b) = (1283u64, 1u64, 0u64);
        let r = 107u64;
        let pp = point_of_order(p, a, b, r).expect("order-r point");
        for k_true in [2u64, 17, 53, 88, 106] {
            let qq = ec_mul(k_true, Some(pp), a, p).unwrap();
            let k = mov_solve(pp, qq, r, a, p).expect("MOV solved");
            assert_eq!(k % r, k_true % r, "MOV must recover the discrete log");
        }
    }
}
