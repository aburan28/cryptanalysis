//! **Canonical rank-2 elliptic net over `F_p`, derived without Stange's
//! seed formulas** (program §5.3b of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`).
//!
//! Stange's net needs explicit "mixed" initial values (`W(2,1)`, `W(1,2)`,
//! …; arXiv:0710.1316 Props 6.3/6.4) that could not be fetched in this
//! environment.  Instead we build the net from a *derivable* rank-2
//! generalisation of the rank-1 coordinate relation
//! `ψ_{a+1}ψ_{a−1}/ψ_a² = x(P) − x(aP)`:
//!
//! ```text
//!   W(a+1,b)·W(a−1,b) / W(a,b)²  =  x(P) − x(aP + bQ)            (REL-P)
//!   W(a,b+1)·W(a,b−1) / W(a,b)²  =  x(Q) − x(aP + bQ)            (REL-Q)
//! ```
//!
//! With the gauge `W(1,0)=W(0,1)=W(1,1)=1`, the axes `W(a,0)=ψ_a(P)`,
//! `W(0,b)=ψ_b(Q)`, and `x(aP+bQ)` from point arithmetic, these second-order
//! recurrences fill the whole grid.  We then **validate** the result against
//! the net recurrence which we *do* know exactly:
//!
//! ```text
//!   W(p+q)W(p−q)W(r)² = W(p+r)W(p−r)W(q)² − W(q+r)W(q−r)W(p)²    (NET)
//! ```
//!
//! If `(NET)` holds and the zero set is exactly `{(a,b) : aP+bQ = O}`, the
//! construction is a genuine elliptic net (in the gauge above) — and §5.3b is
//! unblocked.  For the ECDLP case `Q = [k]P` the net is *degenerate*
//! (everything lives in `⟨P⟩`), which is the point: its χ-pattern collapses
//! to the rank-1 decimation of §5.3a, so it gives no advantage over rank-1.

use crate::cryptanalysis::eds_tate::{ec_add, ec_mul, ec_order, eds_u64, Pt};

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
fn invm(x: u64, p: u64) -> u64 {
    powm(x, p - 2, p)
}
#[inline]
pub fn legendre(x: u64, p: u64) -> i8 {
    let x = x % p;
    if x == 0 {
        0
    } else if powm(x, (p - 1) / 2, p) == 1 {
        1
    } else {
        -1
    }
}

/// `x`-coordinate of `aP + bQ`, or `None` if that point is `O`.
fn x_of(a: i64, b: i64, pp: Pt, qq: Pt, ca: u64, p: u64) -> Option<u64> {
    let ap = if a >= 0 {
        ec_mul(a as u64, pp, ca, p)
    } else {
        ec_mul((-a) as u64, pp.map(|(x, y)| (x, (p - y) % p)), ca, p)
    };
    let bq = if b >= 0 {
        ec_mul(b as u64, qq, ca, p)
    } else {
        ec_mul((-b) as u64, qq.map(|(x, y)| (x, (p - y) % p)), ca, p)
    };
    ec_add(ap, bq, ca, p).map(|(x, _)| x)
}

/// A rank-2 net over the non-negative quadrant `[0,amax] × [0,bmax]`.
/// `w[b][a] = Some(W(a,b))`, or `None` if `aP+bQ = O` (a genuine zero) or the
/// row/column could not be continued past a zero.
pub struct Net {
    pub w: Vec<Vec<Option<u64>>>,
    pub amax: usize,
    pub bmax: usize,
    pub p: u64,
}

impl Net {
    pub fn get(&self, a: usize, b: usize) -> Option<u64> {
        self.w.get(b).and_then(|r| r.get(a)).copied().flatten()
    }
}

/// Build the canonical net for `(E: y²=x³+ca·x+cb, P, Q=[k]P)` over the
/// quadrant `[0,amax]×[0,bmax]`, using (REL-P)/(REL-Q).
pub fn build_net(
    ca: u64,
    cb: u64,
    p: u64,
    pp: (u64, u64),
    k: u64,
    amax: usize,
    bmax: usize,
) -> Net {
    let q = ec_mul(k, Some(pp), ca, p).expect("Q = [k]P ≠ O");
    build_net_pq(ca, cb, p, pp, q, amax, bmax)
}

/// Build the canonical net for an **arbitrary** pair `(P, Q)` over the
/// quadrant `[0,amax]×[0,bmax]` via (REL-P)/(REL-Q).  When `Q ∉ ⟨P⟩`
/// (non-cyclic group) this is a genuinely rank-2 net with a 2-D zero-lattice.
pub fn build_net_pq(
    ca: u64,
    cb: u64,
    p: u64,
    pp: (u64, u64),
    q: (u64, u64),
    amax: usize,
    bmax: usize,
) -> Net {
    let pt = Some(pp);
    let qq = Some(q);
    let (xp, xq) = (pp.0, q.0);

    let zero = |a: usize, b: usize| -> bool { x_of(a as i64, b as i64, pt, qq, ca, p).is_none() };

    let psi_p = eds_u64(ca, cb, pp.0, pp.1, p, amax + 3);
    let psi_q = eds_u64(ca, cb, q.0, q.1, p, bmax + 3);

    let mut w = vec![vec![None::<u64>; amax + 1]; bmax + 1];

    // axes
    for a in 0..=amax {
        w[0][a] = if psi_p[a] == 0 { None } else { Some(psi_p[a]) };
    }
    for b in 0..=bmax {
        w[b][0] = if psi_q[b] == 0 { None } else { Some(psi_q[b]) };
    }
    // column a=1 via (REL-Q): W(1,b+1) = (x_Q − x(P+bQ))·W(1,b)²/W(1,b−1)
    if amax >= 1 {
        w[0][1] = Some(1); // ψ_1(P)
        if bmax >= 1 {
            w[1][1] = Some(1); // gauge
            for b in 1..bmax {
                if zero(1, b + 1) {
                    w[b + 1][1] = None;
                    continue;
                }
                match (w[b][1], w[b - 1][1], x_of(1, b as i64, pt, qq, ca, p)) {
                    (Some(wb), Some(wbm1), Some(xm)) => {
                        let val = mulm(subm(xq, xm, p), mulm(mulm(wb, wb, p), invm(wbm1, p), p), p);
                        w[b + 1][1] = if val == 0 { None } else { Some(val) };
                    }
                    _ => w[b + 1][1] = None,
                }
            }
        }
    }
    // each row b: fill a≥1 via (REL-P): W(a+1,b) = (x_P − x(aP+bQ))·W(a,b)²/W(a−1,b)
    for b in 1..=bmax {
        for a in 1..amax {
            if zero(a + 1, b) {
                w[b][a + 1] = None;
                continue;
            }
            match (
                w[b][a],
                w[b][a - 1],
                x_of(a as i64, b as i64, pt, qq, ca, p),
            ) {
                (Some(wa), Some(wam1), Some(xm)) => {
                    let val = mulm(subm(xp, xm, p), mulm(mulm(wa, wa, p), invm(wam1, p), p), p);
                    w[b][a + 1] = if val == 0 { None } else { Some(val) };
                }
                _ => w[b][a + 1] = None,
            }
        }
    }

    Net { w, amax, bmax, p }
}

/// Check the net recurrence `(NET)` on a triple of index vectors (all six
/// combination indices must be inside the grid and the values present).
/// Returns `Some(true/false)` if checkable, `None` if indices fall outside.
pub fn check_net_relation(
    net: &Net,
    pv: (usize, usize),
    qv: (usize, usize),
    rv: (usize, usize),
) -> Option<bool> {
    let p = net.p;
    let add = |u: (usize, usize), v: (usize, usize)| (u.0 + v.0, u.1 + v.1);
    let sub = |u: (usize, usize), v: (usize, usize)| -> Option<(usize, usize)> {
        if u.0 >= v.0 && u.1 >= v.1 {
            Some((u.0 - v.0, u.1 - v.1))
        } else {
            None
        }
    };
    let g = |v: (usize, usize)| net.get(v.0, v.1);
    // need all of p±q, p±r, q±r, p, q, r
    let pq = add(pv, qv);
    let pmq = sub(pv, qv)?;
    let pr = add(pv, rv);
    let pmr = sub(pv, rv)?;
    let qr = add(qv, rv);
    let qmr = sub(qv, rv)?;
    let (wpq, wpmq, wpr, wpmr, wqr, wqmr) = (g(pq)?, g(pmq)?, g(pr)?, g(pmr)?, g(qr)?, g(qmr)?);
    let (wp, wq, wr) = (g(pv)?, g(qv)?, g(rv)?);
    // W(p+q)W(p−q)W(r)² = W(p+r)W(p−r)W(q)² − W(q+r)W(q−r)W(p)²
    let lhs = mulm(mulm(wpq, wpmq, p), mulm(wr, wr, p), p);
    let t1 = mulm(mulm(wpr, wpmr, p), mulm(wq, wq, p), p);
    let t2 = mulm(mulm(wqr, wqmr, p), mulm(wp, wp, p), p);
    let rhs = subm(t1, t2, p);
    Some(lhs == rhs)
}

/// Find a full-`ell`-torsion instance over `F_p` (`ell | p−1`): a curve and
/// two **independent** points `P, Q` of order `ell` (`Q ∉ ⟨P⟩`).  Returns
/// `(a, b, P, Q)`.
pub fn find_full_torsion(p: u64, ell: u64) -> Option<(u64, u64, (u64, u64), (u64, u64))> {
    let mut sqrt = vec![None::<u64>; p as usize];
    for y in 0..p {
        sqrt[((y * y) % p) as usize].get_or_insert(y);
    }
    for a in 0..120u64 {
        for b in 0..120u64 {
            let disc = (4 * mulm(mulm(a, a, p), a, p) + 27 * mulm(b, b, p)) % p;
            if disc == 0 {
                continue;
            }
            let mut pbase: Option<(u64, u64)> = None;
            let mut orbit: Vec<u64> = Vec::new();
            for x in 0..p {
                let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p;
                if rhs == 0 {
                    continue;
                }
                let y = match sqrt[rhs as usize] {
                    Some(y) if y != 0 => y,
                    _ => continue,
                };
                if ec_order(Some((x, y)), a, p, ell + 1) != Some(ell) {
                    continue;
                }
                match pbase {
                    None => {
                        pbase = Some((x, y));
                        for i in 1..ell {
                            if let Some((xx, _)) = ec_mul(i, Some((x, y)), a, p) {
                                orbit.push(xx);
                            }
                        }
                    }
                    Some(pp) => {
                        if !orbit.contains(&x) {
                            return Some((a, b, pp, (x, y)));
                        }
                    }
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::eds_tate::tate_pairing;

    /// Find a toy curve + point of order ≥ min_r over F_p (any odd prime).
    fn toy_instance(p: u64, min_r: u64) -> Option<(u64, u64, (u64, u64), u64)> {
        for a in 0..20u64 {
            for b in 0..20u64 {
                let disc = (4 * mulm(mulm(a, a, p), a, p) + 27 * mulm(b, b, p)) % p;
                if disc == 0 {
                    continue;
                }
                for x in 1..p.min(200) {
                    let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p;
                    // crude sqrt via scan (toy)
                    let mut y = 0;
                    for cand in 1..p {
                        if mulm(cand, cand, p) == rhs {
                            y = cand;
                            break;
                        }
                    }
                    if y == 0 {
                        continue;
                    }
                    if let Some(r) = ec_order(Some((x, y)), a, p, 2 * p + 4) {
                        if r >= min_r {
                            return Some((a, b, (x, y), r));
                        }
                    }
                }
            }
        }
        None
    }

    #[test]
    fn net_recurrence_holds_for_independent_p_q() {
        // Genuinely rank-2: find full ℓ-torsion (two independent order-ℓ
        // points) so Q ∉ ⟨P⟩ and the zero-lattice is 2-dimensional, then
        // verify the (REL-P)/(REL-Q) net still satisfies (NET).
        let p = 1009u64; // 7 | p−1 ⇒ full 7-torsion can be rational
        let ell = 7u64;
        // sqrt table for fast point finding.
        let mut sqrt = vec![None::<u64>; p as usize];
        for y in 0..p {
            sqrt[((y * y) % p) as usize].get_or_insert(y);
        }
        let mut found = None;
        'search: for a in 0..120u64 {
            for b in 0..120u64 {
                let disc = (4 * mulm(mulm(a, a, p), a, p) + 27 * mulm(b, b, p)) % p;
                if disc == 0 {
                    continue;
                }
                let mut pbase: Option<(u64, u64)> = None;
                let mut orbit: Vec<u64> = Vec::new();
                for x in 0..p {
                    let rhs = (mulm(mulm(x, x, p), x, p) + mulm(a, x, p) + b) % p;
                    if rhs == 0 {
                        continue;
                    }
                    let y = match sqrt[rhs as usize] {
                        Some(y) if y != 0 => y,
                        _ => continue,
                    };
                    if ec_order(Some((x, y)), a, p, ell + 1) != Some(ell) {
                        continue;
                    }
                    match pbase {
                        None => {
                            pbase = Some((x, y));
                            for i in 1..ell {
                                if let Some((xx, _)) = ec_mul(i, Some((x, y)), a, p) {
                                    orbit.push(xx);
                                }
                            }
                        }
                        Some(pp) => {
                            if !orbit.contains(&x) {
                                found = Some((a, b, pp, (x, y)));
                                break 'search;
                            }
                        }
                    }
                }
            }
        }
        let (ca, cb, pp, q) = found.expect("full 7-torsion instance over F_1009");
        // sanity: P, Q independent order-7.
        assert_eq!(ec_order(Some(pp), ca, p, 8), Some(7));
        assert_eq!(ec_order(Some(q), ca, p, 8), Some(7));

        let (amax, bmax) = (6usize, 6usize);
        let net = build_net_pq(ca, cb, p, pp, q, amax, bmax);

        // axis = rank-1 EDS of P
        let psi_p = eds_u64(ca, cb, pp.0, pp.1, p, amax + 1);
        for a in 1..=amax {
            assert_eq!(net.get(a, 0), Some(psi_p[a]));
        }
        // (NET) on triples with nonneg differences inside [0,6]².
        let triples = [
            ((3, 2), (2, 1), (1, 1)),
            ((4, 2), (2, 1), (1, 1)),
            ((4, 3), (2, 2), (1, 1)),
            ((3, 3), (2, 2), (1, 1)),
        ];
        let mut checked = 0;
        for (pv, qv, rv) in triples {
            if let Some(ok) = check_net_relation(&net, pv, qv, rv) {
                assert!(
                    ok,
                    "NET failed (independent P,Q) at {:?},{:?},{:?}",
                    pv, qv, rv
                );
                checked += 1;
            }
        }
        assert!(
            checked >= 3,
            "expected several checkable triples, got {}",
            checked
        );

        // genuinely rank-2 zero-lattice: aP+bQ=O ⟺ a≡b≡0 (mod 7).
        let pt = Some(pp);
        for a in 0..14usize {
            for b in 0..14usize {
                let is_o = ec_add(
                    ec_mul(a as u64, pt, ca, p),
                    ec_mul(b as u64, Some(q), ca, p),
                    ca,
                    p,
                )
                .is_none();
                assert_eq!(
                    is_o,
                    a % 7 == 0 && b % 7 == 0,
                    "zero-lattice at ({},{})",
                    a,
                    b
                );
            }
        }
    }

    #[test]
    fn tate_via_net_matches_miller() {
        // Stange's Tate-pairing-via-net formula, validated against the
        // independent Miller-based pairing on a non-degenerate net.
        //   τ_r(P,Q) = ( W(r+1,1)·W(1,0) / (W(r+1,0)·W(1,1)) )^{(p−1)/r}
        // For independent P,Q the row b=1 has no zeros, so W(r+1,1) is
        // reachable. p=1009, full 7-torsion (7 | p−1 ⇒ embedding degree 1).
        let p = 1009u64;
        let ell = 7u64;
        let (ca, cb, pp, q) = find_full_torsion(p, ell).expect("full 7-torsion");
        let r = ell;
        let net = build_net_pq(ca, cb, p, pp, q, (r + 1) as usize, 2);

        let w_r1_1 = net.get((r + 1) as usize, 1).expect("W(r+1,1) present");
        let w_r1_0 = net.get((r + 1) as usize, 0).expect("W(r+1,0) present");
        let w_1_0 = net.get(1, 0).unwrap();
        let w_1_1 = net.get(1, 1).unwrap();

        // raw ratio, then reduce.
        let num = mulm(w_r1_1, w_1_0, p);
        let den = mulm(w_r1_0, w_1_1, p);
        let raw = mulm(num, invm(den, p), p);
        let tau_net = powm(raw, (p - 1) / r, p);

        let tau_miller = tate_pairing(pp, q, r, ca, cb, p).expect("miller tate");

        // nondegenerate instance: the pairing is a primitive r-th root.
        assert_ne!(tau_miller, 1, "expected a nondegenerate pairing value");
        assert_eq!(powm(tau_miller, r, p), 1, "pairing must lie in μ_r");
        // the headline: Stange's net formula reproduces the Miller pairing.
        assert_eq!(
            tau_net, tau_miller,
            "Tate-via-net must equal Miller pairing"
        );
    }

    fn gcd(mut a: u64, mut b: u64) -> u64 {
        while b != 0 {
            let t = a % b;
            a = b;
            b = t;
        }
        a
    }

    #[test]
    fn net_satisfies_recurrence() {
        // Large order, k coprime to m and small ⇒ the band carries no zeros
        // (a+bk < m), so it fills completely and (NET) is fully checkable.
        let p = 1009u64;
        let (ca, cb, pp, m) = toy_instance(p, 300).expect("instance");
        let (amax, bmax) = (14usize, 10usize);
        let k = (7..m)
            .find(|&k| gcd(k, m) == 1 && (k * bmax as u64 + amax as u64) < m)
            .unwrap();
        let net = build_net(ca, cb, p, pp, k, amax, bmax);

        // Axis must equal the rank-1 EDS of P.
        let psi_p = eds_u64(ca, cb, pp.0, pp.1, p, amax + 1);
        for a in 1..=amax {
            assert_eq!(net.get(a, 0), Some(psi_p[a]), "W(a,0)=ψ_a(P) at a={}", a);
        }

        // (NET) on non-collinear triples with nonneg differences.
        let triples = [
            ((5, 4), (3, 1), (1, 1)),
            ((6, 3), (2, 1), (1, 1)),
            ((7, 5), (3, 2), (2, 1)),
            ((9, 6), (4, 2), (2, 1)),
        ];
        let mut checked = 0;
        for (pv, qv, rv) in triples {
            if let Some(ok) = check_net_relation(&net, pv, qv, rv) {
                assert!(ok, "NET failed at {:?},{:?},{:?}", pv, qv, rv);
                checked += 1;
            }
        }
        assert!(
            checked >= 3,
            "expected several checkable NET triples, got {}",
            checked
        );
    }

    #[test]
    fn net_zero_lattice_matches_point_arithmetic() {
        // Moderate order with a band reaching past the first lattice zero.
        let p = 1009u64;
        let (ca, cb, pp, m) = toy_instance(p, 40).expect("instance");
        let k = (3..m).find(|&k| gcd(k, m) == 1).unwrap();
        let (amax, bmax) = (m as usize + 2, 6usize);
        let net = build_net(ca, cb, p, pp, k, amax, bmax);
        let pt = Some(pp);
        let qq = ec_mul(k, pt, ca, p);
        // Every genuine zero aP+bQ=O must be None in the net.
        let mut zeros_seen = 0;
        for b in 0..=bmax {
            for a in 0..=amax {
                let is_o = ec_add(
                    ec_mul(a as u64, pt, ca, p),
                    ec_mul(b as u64, qq, ca, p),
                    ca,
                    p,
                )
                .is_none();
                if is_o {
                    assert!(net.get(a, b).is_none(), "missing zero at ({},{})", a, b);
                    zeros_seen += 1;
                }
            }
        }
        assert!(zeros_seen >= 3, "band should contain several lattice zeros");
    }
}
