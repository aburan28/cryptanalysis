//! **Self-Tate pairing over `F_p` and its link to the EDS multiplier**
//! (program item 2 / §5.5 of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`).
//!
//! For a point `P` of order `r` with embedding degree 1 (`r | p−1`), the
//! reduced Tate–Lichtenbaum pairing lands in `μ_r ⊂ F_p^*`.  This module
//! implements it from scratch (Miller's algorithm + final exponentiation),
//! **validates it by bilinearity** (`⟨P,[c]P⟩ = ⟨P,P⟩^c` and `⟨P,P⟩^r = 1`),
//! and then tests the conjecture that the EDS shift-multiplier character
//! `χ(B)` (see `eds_residue` §5.5) equals `χ(⟨P,P⟩_r)`.
//!
//! Everything is `u64` (toy primes `p < 2^32`, products in `u128`).  The
//! Miller routine handles the loop-ending degeneracies (doubling a 2-torsion
//! point to `O`, adding inverse points) which are exactly the cases that
//! arise for even `r` — the regime where `χ(⟨P,P⟩)` is non-trivial.

use num_integer::Integer;

// ── modular helpers ────────────────────────────────────────────────────────

#[inline]
fn mulm(x: u64, y: u64, p: u64) -> u64 {
    ((x as u128 * y as u128) % p as u128) as u64
}
#[inline]
fn subm(x: u64, y: u64, p: u64) -> u64 {
    (x % p + p - y % p) % p
}
#[inline]
fn addm(x: u64, y: u64, p: u64) -> u64 {
    (x + y) % p
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
#[inline]
fn legendre(x: u64, p: u64) -> i8 {
    let x = x % p;
    if x == 0 {
        0
    } else if powm(x, (p - 1) / 2, p) == 1 {
        1
    } else {
        -1
    }
}
fn sqrt_mod(n: u64, p: u64) -> Option<u64> {
    let n = n % p;
    if n == 0 {
        return Some(0);
    }
    if powm(n, (p - 1) / 2, p) != 1 {
        return None;
    }
    if p % 4 == 3 {
        return Some(powm(n, (p + 1) / 4, p));
    }
    // Tonelli–Shanks
    let mut q = p - 1;
    let mut s = 0u32;
    while q.is_multiple_of(2) {
        q /= 2;
        s += 1;
    }
    let mut z = 2u64;
    while powm(z, (p - 1) / 2, p) != p - 1 {
        z += 1;
    }
    let (mut m, mut c, mut t, mut r) = (s, powm(z, q, p), powm(n, q, p), powm(n, q.div_ceil(2), p));
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

// ── EC over F_p (affine; None = point at infinity) ──────────────────────────

pub type Pt = Option<(u64, u64)>;

pub fn ec_add(p1: Pt, p2: Pt, a: u64, p: u64) -> Pt {
    match (p1, p2) {
        (None, x) | (x, None) => x,
        (Some((x1, y1)), Some((x2, y2))) => {
            if x1 == x2 {
                if (y1 + y2) % p == 0 {
                    return None; // P = −Q
                }
                // doubling
                let lam = mulm(
                    addm(mulm(3, mulm(x1, x1, p), p), a, p),
                    invm(mulm(2, y1, p), p),
                    p,
                );
                let x3 = subm(subm(mulm(lam, lam, p), x1, p), x1, p);
                let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
                Some((x3, y3))
            } else {
                let lam = mulm(subm(y2, y1, p), invm(subm(x2, x1, p), p), p);
                let x3 = subm(subm(mulm(lam, lam, p), x1, p), x2, p);
                let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
                Some((x3, y3))
            }
        }
    }
}

pub fn ec_mul(mut k: u64, mut pt: Pt, a: u64, p: u64) -> Pt {
    let mut acc: Pt = None;
    while k > 0 {
        if k & 1 == 1 {
            acc = ec_add(acc, pt, a, p);
        }
        pt = ec_add(pt, pt, a, p);
        k >>= 1;
    }
    acc
}

pub fn ec_order(pt: Pt, a: u64, p: u64, cap: u64) -> Option<u64> {
    let mut acc: Pt = None;
    for m in 1..=cap {
        acc = ec_add(acc, pt, a, p);
        if acc.is_none() {
            return Some(m);
        }
    }
    None
}

// ── Miller's algorithm: f_{r,P}(R) ──────────────────────────────────────────

/// Line-function step for doubling `T`: returns `(g_{T,T}(R), 2T)`, where
/// `g = l_{T,T}/v_{2T}`.  Handles the 2-torsion case (`2T = O`, vertical
/// tangent).  `None` if the evaluation hits a vertical zero (resample S).
fn step_double(t: (u64, u64), rr: (u64, u64), a: u64, p: u64) -> Option<(u64, Pt)> {
    let (x1, y1) = t;
    let (xr, _yr) = rr;
    if y1 == 0 {
        // 2T = O; tangent is vertical x − x1; v_O = 1.
        return Some((subm(xr, x1, p), None));
    }
    let lam = mulm(
        addm(mulm(3, mulm(x1, x1, p), p), a, p),
        invm(mulm(2, y1, p), p),
        p,
    );
    let x3 = subm(subm(mulm(lam, lam, p), x1, p), x1, p);
    let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
    let l = subm(subm(rr.1, y1, p), mulm(lam, subm(xr, x1, p), p), p);
    let v = subm(xr, x3, p);
    if v == 0 {
        return None;
    }
    Some((mulm(l, invm(v, p), p), Some((x3, y3))))
}

/// Line-function step for adding `P` to `T`: returns `(g_{T,P}(R), T+P)`.
fn step_add(t: Pt, pp: (u64, u64), rr: (u64, u64), a: u64, p: u64) -> Option<(u64, Pt)> {
    let (x1, y1) = match t {
        Some(v) => v,
        None => return Some((1, Some(pp))), // O + P = P
    };
    let (x2, y2) = pp;
    let (xr, _) = rr;
    if x1 == x2 {
        if (y1 + y2) % p == 0 {
            // T = −P; T+P = O; vertical x − x2.
            return Some((subm(xr, x2, p), None));
        }
        // T == P → really a doubling.
        return step_double((x1, y1), rr, a, p);
    }
    let lam = mulm(subm(y2, y1, p), invm(subm(x2, x1, p), p), p);
    let x3 = subm(subm(mulm(lam, lam, p), x1, p), x2, p);
    let y3 = subm(mulm(lam, subm(x1, x3, p), p), y1, p);
    let l = subm(subm(rr.1, y1, p), mulm(lam, subm(xr, x1, p), p), p);
    let v = subm(xr, x3, p);
    if v == 0 {
        return None;
    }
    Some((mulm(l, invm(v, p), p), Some((x3, y3))))
}

/// `f_{r,P}(R)` via Miller's algorithm (`div f = r(P) − r(O)` since `rP=O`).
/// `None` on a degenerate evaluation (caller resamples the auxiliary point).
fn miller_eval(pp: (u64, u64), rr: (u64, u64), r: u64, a: u64, p: u64) -> Option<u64> {
    let mut f = 1u64;
    let mut t: Pt = Some(pp);
    let nbits = 64 - r.leading_zeros();
    for i in (0..nbits - 1).rev() {
        let tc = t?; // current running point is affine until the final O
        let (gd, t2) = step_double(tc, rr, a, p)?;
        f = mulm(mulm(f, f, p), gd, p);
        t = t2;
        if (r >> i) & 1 == 1 {
            let (ga, t3) = step_add(t, pp, rr, a, p)?;
            f = mulm(f, ga, p);
            t = t3;
        }
    }
    Some(f)
}

/// Unreduced self-Miller value `f_{r,P}((Q+S)−(S)) ∈ F_p^*`, `Q=[c]P`, with
/// **no embedding-degree requirement** (the Miller function is `F_p`-rational
/// and evaluated at `F_p` points, so the value lies in `F_p` regardless of
/// where the *reduced* pairing would land).  Scans the auxiliary point `S`
/// from `xs_start`.  `None` if no usable `S` is found.
pub fn miller_self_raw(
    pp: (u64, u64),
    c: u64,
    r: u64,
    a: u64,
    b: u64,
    p: u64,
    xs_start: u64,
) -> Option<u64> {
    let q = ec_mul(c, Some(pp), a, p)?;
    for xs in xs_start..p {
        let rhs = (addm(addm(mulm(mulm(xs, xs, p), xs, p), mulm(a, xs, p), p), b, p)) % p;
        if rhs == 0 {
            continue;
        }
        let ys = match sqrt_mod(rhs, p) {
            Some(y) if y != 0 => y,
            _ => continue,
        };
        let s = Some((xs, ys));
        let qs = match ec_add(Some(q), s, a, p) {
            Some(v) => v,
            None => continue,
        };
        let sv = (xs, ys);
        if qs.0 == pp.0 || sv.0 == pp.0 {
            continue;
        }
        let num = match miller_eval(pp, qs, r, a, p) {
            Some(v) if v != 0 => v,
            _ => continue,
        };
        let den = match miller_eval(pp, sv, r, a, p) {
            Some(v) if v != 0 => v,
            _ => continue,
        };
        let raw = mulm(num, invm(den, p), p);
        if raw == 0 {
            continue;
        }
        return Some(raw);
    }
    None
}

/// `(reduced, raw)` self-pairing values: `raw = f_{r,P}((Q+S)−(S))` (the
/// *unreduced* Miller value) and `reduced = raw^{(p−1)/r} ∈ μ_r`.  Scans the
/// auxiliary point `S` from `xs_start`.  The raw value depends on `S` only up
/// to `(F_p*)^r`; in particular `χ(raw)` is `S`-independent when `r` is even.
pub fn self_tate_raw(
    pp: (u64, u64),
    c: u64,
    r: u64,
    a: u64,
    b: u64,
    p: u64,
    xs_start: u64,
) -> Option<(u64, u64)> {
    assert!(
        (p - 1).is_multiple_of(r),
        "embedding degree must be 1 (r | p−1)"
    );
    let raw = miller_self_raw(pp, c, r, a, b, p, xs_start)?;
    let t = powm(raw, (p - 1) / r, p);
    Some((t, raw))
}

/// Reduced Tate pairing `⟨P,Q⟩_r ∈ μ_r ⊂ F_p^*` for an **arbitrary** second
/// argument `Q` (not necessarily in `⟨P⟩`), embedding degree 1 (`r | p−1`).
pub fn tate_pairing(pp: (u64, u64), qq: (u64, u64), r: u64, a: u64, b: u64, p: u64) -> Option<u64> {
    assert!(
        (p - 1).is_multiple_of(r),
        "embedding degree must be 1 (r | p−1)"
    );
    let exp = (p - 1) / r;
    for xs in 1..p {
        let rhs = (addm(addm(mulm(mulm(xs, xs, p), xs, p), mulm(a, xs, p), p), b, p)) % p;
        if rhs == 0 {
            continue;
        }
        let ys = match sqrt_mod(rhs, p) {
            Some(y) if y != 0 => y,
            _ => continue,
        };
        let s = (xs, ys);
        let qs = match ec_add(Some(qq), Some(s), a, p) {
            Some(v) => v,
            None => continue,
        };
        if qs.0 == pp.0 || s.0 == pp.0 {
            continue;
        }
        let num = match miller_eval(pp, qs, r, a, p) {
            Some(v) if v != 0 => v,
            _ => continue,
        };
        let den = match miller_eval(pp, s, r, a, p) {
            Some(v) if v != 0 => v,
            _ => continue,
        };
        let t = powm(mulm(num, invm(den, p), p), exp, p);
        if t == 0 {
            continue;
        }
        return Some(t);
    }
    None
}

/// Reduced self-Tate pairing `⟨P,[c]P⟩_r ∈ μ_r ⊂ F_p^*`, for `r | p−1`.
pub fn self_tate(pp: (u64, u64), c: u64, r: u64, a: u64, b: u64, p: u64) -> Option<u64> {
    self_tate_raw(pp, c, r, a, b, p, 1).map(|(t, _)| t)
}

// ── EDS multiplier B over F_p (u64) ─────────────────────────────────────────

/// Integer-reduced EDS `W(0..count)` over `F_p` for `y²=x³+ax+b`, `P=(x,y)`.
pub fn eds_u64(a: u64, b: u64, x: u64, y: u64, p: u64, count: usize) -> Vec<u64> {
    let x2 = mulm(x, x, p);
    let x3 = mulm(x2, x, p);
    let x4 = mulm(x2, x2, p);
    let x6 = mulm(x3, x3, p);
    let a2 = mulm(a, a, p);
    let w2 = mulm(2, y, p);
    let w3 = {
        let t = addm(
            addm(mulm(3, x4, p), mulm(mulm(6, a, p), x2, p), p),
            mulm(mulm(12, b, p), x, p),
            p,
        );
        subm(t, a2, p)
    };
    let w4 = {
        let pos = addm(
            addm(x6, mulm(mulm(5, a, p), x4, p), p),
            mulm(mulm(20, b, p), x3, p),
            p,
        );
        let mut inner = subm(pos, mulm(mulm(5, a2, p), x2, p), p);
        inner = subm(inner, mulm(mulm(mulm(4, a, p), b, p), x, p), p);
        inner = subm(inner, mulm(8, mulm(b, b, p), p), p);
        inner = subm(inner, mulm(a2, a, p), p);
        mulm(mulm(4, y, p), inner, p)
    };
    let mut w = vec![0u64, 1, w2, w3, w4];
    let w2_inv = invm(w2, p);
    for k in 5..count {
        let val = if k % 2 == 1 {
            let n = (k - 1) / 2;
            subm(
                mulm(w[n + 2], mulm(mulm(w[n], w[n], p), w[n], p), p),
                mulm(w[n - 1], mulm(mulm(w[n + 1], w[n + 1], p), w[n + 1], p), p),
                p,
            )
        } else {
            let n = k / 2;
            let t1 = mulm(w[n + 2], mulm(w[n - 1], w[n - 1], p), p);
            let t2 = mulm(w[n - 2], mulm(w[n + 1], w[n + 1], p), p);
            mulm(mulm(w[n], subm(t1, t2, p), p), w2_inv, p)
        };
        w.push(val);
    }
    w
}

/// The EDS shift multiplier `B = W(r+2)/(W(2)·W(r+1))` over `F_p`.
pub fn eds_multiplier_b(a: u64, b: u64, x: u64, y: u64, r: u64, p: u64) -> Option<u64> {
    let w = eds_u64(a, b, x, y, p, r as usize + 3);
    if w[2] == 0 || w[r as usize + 1] == 0 {
        return None;
    }
    Some(mulm(
        w[r as usize + 2],
        invm(mulm(w[2], w[r as usize + 1], p), p),
        p,
    ))
}

// ── instance search & study ─────────────────────────────────────────────────

/// Find an embedding-degree-1 instance on a small curve over `F_p`: a point
/// `P` of order `r` with `r | p−1`, `r` even, `r ≥ min_r`.  Returns
/// `(a, b, P, r)`.
pub fn find_embedding1_instance(p: u64, min_r: u64) -> Option<(u64, u64, (u64, u64), u64)> {
    for a in 0..30u64 {
        for b in 0..30u64 {
            let disc = addm(
                mulm(4, mulm(mulm(a, a, p), a, p), p),
                mulm(27, mulm(b, b, p), p),
                p,
            );
            if disc == 0 {
                continue;
            }
            // first point G
            let mut g: Pt = None;
            for x in 1..p {
                let rhs = addm(addm(mulm(mulm(x, x, p), x, p), mulm(a, x, p), p), b, p);
                if let Some(y) = sqrt_mod(rhs, p) {
                    if y != 0 {
                        g = Some((x, y));
                        break;
                    }
                }
            }
            let g = match g {
                Some(v) => v,
                None => continue,
            };
            let n = match ec_order(Some(g), a, p, 2 * p + 4) {
                Some(v) => v,
                None => continue,
            };
            let gg = (n).gcd(&(p - 1)); // largest r dividing both n and p−1 is a divisor of this
                                        // pick the largest even divisor of `gg` that is ≥ min_r
            let mut r = 0u64;
            let mut d = 1u64;
            while d * d <= gg {
                if gg % d == 0 {
                    for cand in [d, gg / d] {
                        if cand % 2 == 0
                            && cand >= min_r
                            && cand > r
                            && (p - 1).is_multiple_of(cand)
                        {
                            r = cand;
                        }
                    }
                }
                d += 1;
            }
            if r == 0 {
                continue;
            }
            let pp = ec_mul(n / r, Some(g), a, p)?;
            let (px, py) = pp;
            if py != 0 {
                return Some((a, b, (px, py), r));
            }
        }
    }
    None
}

/// Enumerate several embedding-degree-1 instances on small curves over
/// `F_p` (point `P` of even order `r | p−1`, `r ≥ min_r`), up to
/// `max_instances`.
pub fn enumerate_embedding1(
    p: u64,
    min_r: u64,
    max_instances: usize,
) -> Vec<(u64, u64, (u64, u64), u64)> {
    let mut out = Vec::new();
    for a in 0..40u64 {
        for b in 0..40u64 {
            let disc = addm(
                mulm(4, mulm(mulm(a, a, p), a, p), p),
                mulm(27, mulm(b, b, p), p),
                p,
            );
            if disc == 0 {
                continue;
            }
            let mut g: Pt = None;
            for x in 1..p {
                let rhs = addm(addm(mulm(mulm(x, x, p), x, p), mulm(a, x, p), p), b, p);
                if let Some(y) = sqrt_mod(rhs, p) {
                    if y != 0 {
                        g = Some((x, y));
                        break;
                    }
                }
            }
            let g = match g {
                Some(v) => v,
                None => continue,
            };
            let n = match ec_order(Some(g), a, p, 2 * p + 4) {
                Some(v) => v,
                None => continue,
            };
            let gg = n.gcd(&(p - 1));
            let mut r = 0u64;
            let mut d = 1u64;
            while d * d <= gg {
                if gg % d == 0 {
                    for cand in [d, gg / d] {
                        if cand % 2 == 0
                            && cand >= min_r
                            && cand > r
                            && (p - 1).is_multiple_of(cand)
                        {
                            r = cand;
                        }
                    }
                }
                d += 1;
            }
            if r == 0 {
                continue;
            }
            if let Some((px, py)) = ec_mul(n / r, Some(g), a, p) {
                if py != 0 {
                    out.push((a, b, (px, py), r));
                    if out.len() >= max_instances {
                        return out;
                    }
                }
            }
        }
    }
    out
}

/// One self-pairing ↔ EDS-multiplier study record.
#[derive(Clone, Debug)]
pub struct TateStudy {
    pub p: u64,
    pub a: u64,
    pub b: u64,
    pub order: u64,
    pub tate_self: u64,
    pub chi_tate: i8,
    pub mult_b: u64,
    pub chi_b: i8,
    /// `⟨P,P⟩^r == 1`?
    pub in_mu_r: bool,
    /// bilinearity `⟨P,[c]P⟩ == ⟨P,P⟩^c` for c=2..5?
    pub bilinear: bool,
    /// Does `⟨P,P⟩_r == (B²)^{(p−1)/r}` hold? (the value-level EDS identity)
    pub tate_eq_b2_powered: bool,
}

/// Compute the self-Tate pairing and the EDS multiplier on one instance and
/// record their characters and the validation flags.
pub fn study(p: u64, a: u64, b: u64, pp: (u64, u64), r: u64) -> Option<TateStudy> {
    let t11 = self_tate(pp, 1, r, a, b, p)?;
    let in_mu_r = powm(t11, r, p) == 1;
    let mut bilinear = true;
    for c in 2..=5u64 {
        if c >= r {
            break;
        }
        match self_tate(pp, c, r, a, b, p) {
            Some(tc) => {
                if tc != powm(t11, c, p) {
                    bilinear = false;
                }
            }
            None => bilinear = false,
        }
    }
    let mult_b = eds_multiplier_b(a, b, pp.0, pp.1, r, p)?;
    // value-level candidate: (B²)^{(p−1)/r}
    let b2_powered = powm(mulm(mult_b, mult_b, p), (p - 1) / r, p);
    Some(TateStudy {
        p,
        a,
        b,
        order: r,
        tate_self: t11,
        chi_tate: legendre(t11, p),
        mult_b,
        chi_b: legendre(mult_b, p),
        in_mu_r,
        bilinear,
        tate_eq_b2_powered: b2_powered == t11,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v2(mut n: u64) -> u32 {
        let mut k = 0;
        while n.is_multiple_of(2) {
            n /= 2;
            k += 1;
        }
        k
    }

    #[test]
    fn bridge_holds_on_supersingular_curves() {
        // y²=x³+x over p≡3 (mod 4) is supersingular: #E = p+1, embedding
        // degree exactly 2 — the canonical MOV-weak / pairing family.  This is
        // the realest test of §5.8: χ(B)=χ(f_{r,P}) for embedding degree > 1,
        // computed entirely in F_p via the unreduced self-Miller value.
        let (a, b) = (1u64, 0u64);
        let (mut total, mut agree, mut sindep) = (0usize, 0usize, 0usize);
        for p in [1019u64, 1031, 2003, 2011, 4099, 1283] {
            assert_eq!(p % 4, 3, "y²=x³+x is supersingular only for p≡3 (mod 4)");
            let mut used_orders = std::collections::HashSet::new();
            for x in 1..p {
                let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p; // x³+x
                if rhs == 0 {
                    continue;
                }
                let y = match sqrt_mod(rhs, p) {
                    Some(y) if y != 0 => y,
                    _ => continue,
                };
                let r = match ec_order(Some((x, y)), a, p, 2 * p + 4) {
                    Some(r) if r % 2 == 0 && r >= 6 => r,
                    _ => continue,
                };
                // embedding degree exactly 2: r ∤ p−1 but r | p²−1.
                assert_ne!((p - 1) % r, 0, "expected embedding degree > 1");
                assert_eq!((p * p - 1) % r, 0, "expected embedding degree | 2");
                if !used_orders.insert(r) {
                    continue; // one representative per order
                }
                let bmul = match eds_multiplier_b(a, b, x, y, r, p) {
                    Some(v) => v,
                    None => continue,
                };
                let raw1 = match miller_self_raw((x, y), 1, r, a, b, p, 1) {
                    Some(v) => v,
                    None => continue,
                };
                total += 1;
                if legendre(raw1, p) == legendre(bmul, p) {
                    agree += 1;
                }
                if let Some(raw2) = miller_self_raw((x, y), 1, r, a, b, p, p / 2) {
                    if legendre(raw2, p) == legendre(raw1, p) {
                        sindep += 1;
                    }
                }
                if used_orders.len() >= 5 {
                    break;
                }
            }
        }
        assert!(total >= 12, "need supersingular instances, got {}", total);
        assert_eq!(
            agree, total,
            "χ(B)=χ(f_{{r,P}}) on supersingular (embedding degree 2)"
        );
        assert_eq!(sindep, total, "χ(f) must be S-independent on supersingular");
    }

    #[test]
    fn chi_b_equals_chi_self_tate_in_nondegenerate_regime() {
        // The refined bridge: χ(B) = χ(⟨P,P⟩_r) exactly when v2(r)=v2(p−1)
        // (so −1 ∈ μ_r and the self-Tate character is non-trivial); in the
        // forced regime v2(r)<v2(p−1) the pairing character is always +1.
        let (mut nd_total, mut nd_agree, mut forced_total, mut forced_pos) = (0, 0, 0, 0);
        for p in [1021u64, 1033, 2017, 4093, 1013, 2069] {
            for (a, b, pp, r) in enumerate_embedding1(p, 6, 12) {
                let s = match study(p, a, b, pp, r) {
                    Some(s) => s,
                    None => continue,
                };
                assert!(
                    s.in_mu_r && s.bilinear,
                    "pairing must be valid (p={},r={})",
                    p,
                    r
                );
                if v2(r) == v2(p - 1) {
                    nd_total += 1;
                    if s.chi_tate == s.chi_b {
                        nd_agree += 1;
                    }
                } else {
                    forced_total += 1;
                    if s.chi_tate == 1 {
                        forced_pos += 1;
                    }
                }
            }
        }
        assert!(nd_total >= 10, "need a populated nondegenerate regime");
        assert_eq!(
            nd_agree, nd_total,
            "χ(B)=χ(⟨P,P⟩) must hold in nondeg regime"
        );
        assert_eq!(forced_pos, forced_total, "forced regime ⇒ χ(⟨P,P⟩)=+1");
    }

    #[test]
    fn unreduced_self_miller_char_equals_chi_b_any_embedding_degree() {
        // Lift §5.7 to embedding degree > 1 (MOV regime). The unreduced
        // self-Miller value f_{r,P}(D_P) stays in F_p even when r ∤ p−1, so
        // χ(f) is still an F_p bit. Test whether χ(B) = χ(f) for even r with
        // embedding degree > 1 (r ∤ p−1), and whether χ(f) is S-independent.
        let (mut total, mut agree, mut sindep, mut hi_emb) = (0, 0, 0, 0);
        for p in [1009u64, 1013, 2003, 4099, 10007, 1019] {
            for a in 0..25u64 {
                for b in 0..25u64 {
                    let disc = (4 * mulm(mulm(a, a, p), a, p) + 27 * mulm(b, b, p)) % p;
                    if disc == 0 {
                        continue;
                    }
                    // first point P
                    let mut pp = None;
                    for x in 1..p.min(120) {
                        let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p;
                        if rhs == 0 {
                            continue;
                        }
                        if let Some(y) = sqrt_mod(rhs, p) {
                            if y != 0 {
                                pp = Some((x, y));
                                break;
                            }
                        }
                    }
                    let pp = match pp {
                        Some(v) => v,
                        None => continue,
                    };
                    let r = match ec_order(Some(pp), a, p, 2 * p + 4) {
                        Some(r) if r % 2 == 0 && r >= 6 => r,
                        _ => continue,
                    };
                    if (p - 1) % r == 0 {
                        continue; // embedding degree 1 — already handled by §5.7
                    }
                    let bmul = match eds_multiplier_b(a, b, pp.0, pp.1, r, p) {
                        Some(v) => v,
                        None => continue,
                    };
                    let raw1 = match miller_self_raw(pp, 1, r, a, b, p, 1) {
                        Some(v) => v,
                        None => continue,
                    };
                    total += 1;
                    hi_emb += 1;
                    if legendre(raw1, p) == legendre(bmul, p) {
                        agree += 1;
                    }
                    if let Some(raw2) = miller_self_raw(pp, 1, r, a, b, p, p / 2) {
                        if legendre(raw2, p) == legendre(raw1, p) {
                            sindep += 1;
                        }
                    }
                    if total >= 40 {
                        break;
                    }
                }
            }
        }
        assert!(
            hi_emb >= 20,
            "need embedding-degree>1 instances, got {}",
            hi_emb
        );
        assert_eq!(sindep, total, "χ(f) must be S-independent for even r");
        assert_eq!(
            agree, total,
            "χ(B)=χ(f_{{r,P}}) should lift to any embedding degree"
        );
    }

    #[test]
    fn unreduced_self_tate_char_equals_chi_b_all_even_r() {
        // Forced-regime resolution: for even r, χ of the *unreduced* Miller
        // value f_{r,P}(D_P) is S-independent and equals χ(B) in BOTH regimes
        // — unifying §5.6.  In the forced regime χ of the *reduced* pairing
        // is structurally +1 (loses the bit); the unreduced character keeps it.
        let (mut total, mut agree, mut sindep, mut forced) = (0, 0, 0, 0);
        for p in [1021u64, 1033, 2017, 4093, 1013, 2069, 3001] {
            for (a, b, pp, r) in enumerate_embedding1(p, 6, 12) {
                let bmul = match eds_multiplier_b(a, b, pp.0, pp.1, r, p) {
                    Some(v) => v,
                    None => continue,
                };
                let (t1, raw1) = match self_tate_raw(pp, 1, r, a, b, p, 1) {
                    Some(v) => v,
                    None => continue,
                };
                total += 1;
                let chi_b = legendre(bmul, p);
                // χ(unreduced) = χ(B)?
                if legendre(raw1, p) == chi_b {
                    agree += 1;
                }
                // χ(raw) S-independent (different auxiliary S)?
                if let Some((_, raw2)) = self_tate_raw(pp, 1, r, a, b, p, p / 2) {
                    if legendre(raw2, p) == legendre(raw1, p) {
                        sindep += 1;
                    }
                }
                // forced regime: reduced character is structurally trivial.
                if v2(r) < v2(p - 1) {
                    forced += 1;
                    assert_eq!(
                        legendre(t1, p),
                        1,
                        "forced ⇒ χ(reduced)=+1 (p={},r={})",
                        p,
                        r
                    );
                }
            }
        }
        assert!(total >= 20, "need many even-r instances, got {}", total);
        assert!(forced >= 5, "need forced-regime instances, got {}", forced);
        assert_eq!(
            agree, total,
            "χ(B)=χ(unreduced self-pairing) for all even r"
        );
        assert_eq!(sindep, total, "χ(unreduced) must be S-independent (r even)");
    }

    #[test]
    fn tate_pairing_is_valid() {
        // Build an embedding-degree-1 instance and check the pairing is a
        // genuine bilinear pairing into μ_r BEFORE drawing any conclusion.
        for p in [1021u64, 2017, 4093, 1013] {
            if let Some((a, b, pp, r)) = find_embedding1_instance(p, 6) {
                let s = study(p, a, b, pp, r).expect("study ok");
                assert!(s.in_mu_r, "⟨P,P⟩^r must be 1 (p={}, r={})", p, r);
                assert!(s.bilinear, "pairing must be bilinear (p={}, r={})", p, r);
            }
        }
    }
}
